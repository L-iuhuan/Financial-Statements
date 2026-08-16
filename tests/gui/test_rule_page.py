"""RulePage 规则管理页测试。"""

from __future__ import annotations

from fsa.core.models.rule import Severity
from fsa.gui.pages.rule_page import RuleCard, RulePage
from tests.gui.helpers import make_rule


class TestRuleCardTolerance:
    """测试 RuleCard 容差编辑。"""

    def test_tolerance_callback_called(self, qapp, qtbot) -> None:
        """编辑容差后回调被调用。"""
        calls = []

        def on_tol(rule_id: str, value: float) -> None:
            calls.append((rule_id, value))

        rule = make_rule(rule_id="A-001", tolerance=0.01)
        card = RuleCard(
            rule, True, False,
            lambda rid, checked: None, on_tol, lambda rid: None,
        )
        qtbot.addWidget(card)

        card._tol_input.setText("2.50")
        card._on_tol_changed()

        assert len(calls) == 1
        assert calls[0] == ("A-001", 2.5)

    def test_invalid_tolerance_ignored(self, qapp, qtbot) -> None:
        """无效容差文本被忽略。"""
        calls = []

        def on_tol(rule_id: str, value: float) -> None:
            calls.append((rule_id, value))

        rule = make_rule(rule_id="A-001", tolerance=0.01)
        card = RuleCard(
            rule, True, False,
            lambda rid, checked: None, on_tol, lambda rid: None,
        )
        qtbot.addWidget(card)

        card._tol_input.setText("abc")
        card._on_tol_changed()

        assert len(calls) == 0


class TestRuleCardSeverity:
    """测试 severity 标签显示。"""

    def test_error_severity_label(self, qapp, qtbot) -> None:
        from PySide6.QtWidgets import QLabel
        rule = make_rule(severity=Severity.ERROR)
        card = RuleCard(
            rule, True, False,
            lambda rid, checked: None, lambda rid, val: None, lambda rid: None,
        )
        qtbot.addWidget(card)
        assert card.findChild(QLabel, "RuleSeverityLabel") is not None


class TestRulePageDeleteConfirm:
    """测试删除自定义规则的二次确认 (C5-5)。"""

    def test_delete_cancelled_keeps_rule(self, qapp, qtbot, app_state) -> None:
        """确认框选"否"时不删除规则。"""
        from unittest.mock import patch

        from PySide6.QtWidgets import QMessageBox

        from tests.gui.helpers import make_registry

        app_state._registry = make_registry()
        app_state.registry.add_rule(make_rule(rule_id="CUST-001"))
        page = RulePage(app_state)
        qtbot.addWidget(page)

        with patch.object(
            QMessageBox, "question",
            lambda *args, **kwargs: QMessageBox.StandardButton.No,
        ):
            page._on_delete_rule("CUST-001")

        assert app_state.registry.get_by_id("CUST-001") is not None

    def test_delete_confirmed_removes_rule(self, qapp, qtbot, app_state) -> None:
        """确认框选"是"时删除自定义规则。"""
        from unittest.mock import patch

        from PySide6.QtWidgets import QMessageBox

        from tests.gui.helpers import make_registry

        app_state._registry = make_registry()
        app_state.registry.add_rule(make_rule(rule_id="CUST-002"))
        page = RulePage(app_state)
        qtbot.addWidget(page)

        with patch.object(
            QMessageBox, "question",
            lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
        ):
            page._on_delete_rule("CUST-002")

        assert app_state.registry.get_by_id("CUST-002") is None


class TestRulePageFilter:
    """测试规则页筛选。"""

    def test_search_filters_by_id(self, qapp, qtbot, app_state) -> None:
        page = RulePage(app_state)
        qtbot.addWidget(page)
        page._on_search("A-001")
        assert len(page._filtered_rules) == 1
        assert page._filtered_rules[0].rule_id == "A-001"

    def test_search_filters_by_name(self, qapp, qtbot, app_state) -> None:
        page = RulePage(app_state)
        qtbot.addWidget(page)
        page._on_search("测试规则")
        assert len(page._filtered_rules) == 3


class TestRuleTogglePersistence:
    """规则启停持久化测试 (审查报告 2026-08-16 终审 P2 补修: 此前仅改内存, 重启丢失)。"""

    @staticmethod
    def _swap_tmp_db(app_state, tmp_path) -> None:
        """把 AppState 的持久化层替换为临时数据库 (同 test_tolerance_persistence 模式)。"""
        from fsa.storage.database import Database
        from fsa.storage.override_repo import RuleOverrideRepo

        app_state._db.close()
        db = Database(tmp_path / "toggle.db")
        db.connect()
        db.init_schema()
        app_state._db = db
        app_state._override_repo = RuleOverrideRepo(db)

    def test_toggle_persists_to_override_repo(self, qapp, qtbot, app_state, tmp_path) -> None:
        """禁用规则写入覆写仓库, 内存注册表同步禁用。"""
        self._swap_tmp_db(app_state, tmp_path)
        page = RulePage(app_state)
        qtbot.addWidget(page)

        page._on_toggle("A-001", False)

        repo = app_state.override_repo
        assert repo is not None
        override = repo.get_all()["A-001"]
        assert override.enabled is False
        active_ids = {r.rule_id for r in app_state.registry.get_active()}
        assert "A-001" not in active_ids

    def test_toggle_applied_on_reload(self, qapp, qtbot, app_state, tmp_path) -> None:
        """重启后 (_apply_overrides 回放) 禁用状态恢复。"""
        from tests.gui.helpers import make_registry

        self._swap_tmp_db(app_state, tmp_path)
        page = RulePage(app_state)
        qtbot.addWidget(page)
        page._on_toggle("A-001", False)
        page._on_toggle("B-001", False)

        # 模拟重启: 全新注册表 + 回放覆写
        app_state._registry = make_registry()
        app_state._apply_overrides()

        active_ids = {r.rule_id for r in app_state.registry.get_active()}
        assert "A-001" not in active_ids
        assert "B-001" not in active_ids
        assert "C-001" in active_ids

    def test_toggle_without_repo_session_only(self, qapp, qtbot, app_state) -> None:
        """存储降级时启停仅内存生效, 并提示「仅本次会话生效」(沿用 B3-5 模式)。"""
        app_state._override_repo = None
        page = RulePage(app_state)
        qtbot.addWidget(page)
        toasts: list[tuple[str, str]] = []
        page._show_toast = lambda message, kind: toasts.append((message, kind))

        page._on_toggle("A-001", False)

        active_ids = {r.rule_id for r in app_state.registry.get_active()}
        assert "A-001" not in active_ids
        assert toasts
        message, kind = toasts[-1]
        assert "仅本次会话生效" in message
        assert kind == "warning"
