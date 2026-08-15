"""AppState 异步持久化测试: results_changed 先于 persist 完成触发
 (FIX 1 - H2 异步持久化)。

验证:
- results_changed 在 persist 完成前触发 (UI 不阻塞)
- 持久化最终完成后 history_changed 触发
- persist 失败时 history_changed 不触发
- persist=False 路径不变 (同步)
- close() 等待后台线程 (不丢数据)
- 两次 persist 顺序执行 (不交错)
"""

from __future__ import annotations

import threading
import time
from unittest.mock import patch

from fsa.storage.database import Database
from tests.storage.conftest import make_summary


def _pump_until(predicate, timeout: float = 3.0) -> None:
    """泵 Qt 事件循环直到条件满足 (后台线程发出的信号经队列投递需事件循环)。"""
    from PySide6.QtCore import QCoreApplication

    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.01)


class TestAsyncPersistSignals:
    """results_changed 在 persist 完成前触发。"""

    def test_results_changed_fires_before_persist_completes(
        self, db_path, monkeypatch, qapp
    ) -> None:
        """results_changed 在 SQLite 写入完成前已触发。"""
        from fsa.gui.app_state import AppState

        monkeypatch.setattr(
            "fsa.gui.app_state.Database",
            lambda: _make_db(db_path),
        )

        app = AppState()
        app.load_registry()
        assert app._history_repo is not None

        capture_order: list[str] = []
        app.results_changed.connect(lambda: capture_order.append("results_changed"))
        app.history_changed.connect(lambda: capture_order.append("history_changed"))

        save_started = threading.Event()
        save_block = threading.Event()

        original_save = app._history_repo.save

        def slow_save(summary):
            save_started.set()
            save_block.wait(timeout=5.0)
            return original_save(summary)

        # patch the save method on the HistoryRepo instance
        with patch.object(app._history_repo, "save", side_effect=slow_save):
            summary = make_summary()
            app.set_results(summary, persist=True)

            # results_changed 应该在 persist 完成前触发
            assert "results_changed" in capture_order
            assert "history_changed" not in capture_order

            # 等 save 被调用
            assert save_started.wait(timeout=3.0)

            # 放行
            save_block.set()

            # 等待后台线程完成
            app.close()

        # history_changed 从后台线程经 Qt 队列投递, 需泵事件循环才能收到
        _pump_until(lambda: "history_changed" in capture_order)
        assert "history_changed" in capture_order
        ri = capture_order.index("results_changed")
        hi = capture_order.index("history_changed")
        assert ri < hi

    def test_persist_false_no_thread(self, db_path, monkeypatch) -> None:
        """persist=False 时不启动后台线程, 行为不变。"""
        from fsa.gui.app_state import AppState

        monkeypatch.setattr(
            "fsa.gui.app_state.Database",
            lambda: _make_db(db_path),
        )

        app = AppState()
        app.load_registry()

        capture_order: list[str] = []
        app.results_changed.connect(lambda: capture_order.append("results_changed"))
        app.history_changed.connect(lambda: capture_order.append("history_changed"))

        summary = make_summary()
        app.set_results(summary, persist=False)

        assert "results_changed" in capture_order
        assert "history_changed" not in capture_order


class TestAsyncPersistFailure:
    """persist 失败时静默降级, history_changed 不触发。"""

    def test_persist_failure_no_history_changed(self, db_path, monkeypatch) -> None:
        """SQLite 写入失败时 history_changed 不触发。"""
        from fsa.gui.app_state import AppState

        monkeypatch.setattr(
            "fsa.gui.app_state.Database",
            lambda: _make_db(db_path),
        )

        app = AppState()
        app.load_registry()
        assert app._history_repo is not None

        captured: list[str] = []
        app.results_changed.connect(lambda: captured.append("results_changed"))
        app.history_changed.connect(lambda: captured.append("history_changed"))

        with patch.object(app._history_repo, "save", side_effect=RuntimeError("模拟故障")):
            summary = make_summary()
            app.set_results(summary, persist=True)

            # results_changed 已触发
            assert "results_changed" in captured

            # 等待后台线程完成
            app.close()

        # history_changed 不应触发
        assert "history_changed" not in captured


class TestAsyncPersistClose:
    """close() 等待后台线程, 不丢数据。"""

    def test_close_during_pending_persist(self, db_path, monkeypatch) -> None:
        """close() 在 persist 进行中调用, 不崩溃且不丢数据。"""
        from fsa.gui.app_state import AppState

        monkeypatch.setattr(
            "fsa.gui.app_state.Database",
            lambda: _make_db(db_path),
        )

        app = AppState()
        app.load_registry()
        assert app._history_repo is not None

        captured: list[str] = []
        app.history_changed.connect(lambda: captured.append("history_changed"))

        save_started = threading.Event()
        save_block = threading.Event()

        original_save = app._history_repo.save

        def slow_save(summary):
            save_started.set()
            save_block.wait(timeout=5.0)
            return original_save(summary)

        with patch.object(app._history_repo, "save", side_effect=slow_save):
            summary = make_summary()
            app.set_results(summary, persist=True)

            # 等待 save 被调用
            assert save_started.wait(timeout=3.0)

            # 放行 save
            save_block.set()

            # close() 应等待后台线程完成
            app.close()

        # history_changed 经 Qt 队列投递, 需泵事件循环才能收到
        _pump_until(lambda: "history_changed" in captured)
        assert "history_changed" in captured

    def test_close_without_pending_persist(self, db_path, monkeypatch) -> None:
        """无后台 persist 时 close() 正常。"""
        from fsa.gui.app_state import AppState

        monkeypatch.setattr(
            "fsa.gui.app_state.Database",
            lambda: _make_db(db_path),
        )

        app = AppState()
        app.load_registry()
        summary = make_summary()
        app.set_results(summary, persist=True)
        # 等待片刻
        time.sleep(0.2)
        app.close()  # 不应崩溃


class TestAsyncPersistSerialization:
    """两次 persist 顺序执行, 不交错。"""

    def test_second_persist_waits_for_first(self, db_path, monkeypatch) -> None:
        """第二次 persist 在第一次完成后才执行。"""

        from fsa.gui.app_state import AppState

        monkeypatch.setattr(
            "fsa.gui.app_state.Database",
            lambda: _make_db(db_path),
        )

        app = AppState()
        app.load_registry()
        assert app._history_repo is not None

        execution_order: list[int] = []
        save_block = threading.Event()

        original_save = app._history_repo.save

        def slow_save_first(summary):
            execution_order.append(1)
            save_block.wait(timeout=5.0)
            return original_save(summary)

        def save_second(summary):
            execution_order.append(2)
            return original_save(summary)

        with patch.object(app._history_repo, "save", side_effect=slow_save_first):
            summary1 = make_summary(period="2024年1月")
            app.set_results(summary1, persist=True)
            # 短暂等待确保线程启动并获取锁
            time.sleep(0.1)

            # 替换为快速 save
            with patch.object(app._history_repo, "save", side_effect=save_second):
                summary2 = make_summary(period="2024年2月")
                app.set_results(summary2, persist=True)

                # 第二次还没执行 (被锁挡在门外)
                time.sleep(0.2)
                assert 2 not in execution_order

                # 放行第一次
                save_block.set()

                # 等待完成
                app.close()

        assert execution_order == [1, 2]


def _make_db(db_path):
    """创建已初始化 schema 的 Database 实例。"""
    db = Database(db_path)
    db.connect()
    db.init_schema()
    return db
