"""read_excel_com 与常规读取失败自动回退的测试。"""

from __future__ import annotations

from importlib.util import find_spec
from pathlib import Path

import pytest

from fsa.core.exceptions import FSAError
from fsa.core.importer.excel_reader import read_excel, read_excel_com


def _has_pywin32() -> bool:
    """安全探测 pywin32 是否存在 (find_spec 子模块时父包缺失会抛异常)。"""
    try:
        return find_spec("win32com") is not None and find_spec("win32com.client") is not None
    except (ImportError, ModuleNotFoundError):
        return False


def test_read_excel_com_roundtrip(tmp_path: Path) -> None:
    """有 pywin32 且 Excel 可用时，COM 读取结果与常规读取一致。"""
    if not _has_pywin32():
        pytest.skip("未安装 pywin32")
    from tests.importer.conftest import make_multi_sheet_excel

    path = make_multi_sheet_excel(tmp_path)
    try:
        data = read_excel_com(str(path))
    except FSAError as error:
        pytest.skip(f"本机 Excel COM 不可用: {error}")

    assert set(data) == {"资产负债表", "利润表", "现金流量表"}
    assert "期末余额" in data["资产负债表"].headers
    assert len(data["资产负债表"].rows) > 0


def test_native_failure_falls_back_without_pywin32(tmp_path: Path) -> None:
    """常规读取失败且无 pywin32 时，回退给出可读的中文错误。"""
    if _has_pywin32():
        pytest.skip("已安装 pywin32，跳过缺依赖分支")

    encrypted_like = tmp_path / "encrypted.xlsx"
    encrypted_like.write_bytes("该文件为密文".encode())

    with pytest.raises(FSAError, match="pywin32"):
        read_excel(str(encrypted_like))


class TestComTimeoutWrapper:
    """read_excel_com 的线程超时包装 (不依赖真实 Excel)。"""

    @pytest.fixture(autouse=True)
    def _fake_win32(self, monkeypatch):
        import sys
        from types import ModuleType

        parent = ModuleType("win32com")
        client = ModuleType("win32com.client")
        monkeypatch.setitem(sys.modules, "win32com", parent)
        monkeypatch.setitem(sys.modules, "win32com.client", client)

    def test_timeout_raises_chinese_error(self, monkeypatch) -> None:
        import time

        import fsa.core.importer.excel_reader as reader

        def slow(path: str, progress_cb=None):
            time.sleep(0.3)
            return {}

        monkeypatch.setattr(reader, "_read_excel_com_sync", slow)
        with pytest.raises(FSAError, match="超时"):
            reader.read_excel_com("fake.xlsx", timeout=0.05)

    def test_progress_callback_is_forwarded(self, monkeypatch) -> None:
        import fsa.core.importer.excel_reader as reader

        def fake(path: str, progress_cb=None):
            if progress_cb is not None:
                progress_cb(0, 2)
                progress_cb(2, 2)
            return {"资产负债表": object()}

        monkeypatch.setattr(reader, "_read_excel_com_sync", fake)
        records: list[tuple[int, int]] = []
        result = reader.read_excel_com("fake.xlsx", timeout=2.0, progress_cb=lambda a, b: records.append((a, b)))
        assert list(result) == ["资产负债表"]
        assert records == [(0, 2), (2, 2)]


class TestComUsedRangeRowOffset:
    """UsedRange 左上角非 A1 时, _row 需叠加起始行偏移 (D2-1, 伪 COM 对象推演)。"""

    @pytest.fixture(autouse=True)
    def _fake_win32(self, monkeypatch):
        import sys
        from types import ModuleType

        parent = ModuleType("win32com")
        client = ModuleType("win32com.client")
        # 源码经 win32com.client.DispatchEx 访问, 父包需带 client 属性
        # (tests 不在 mypy 检查范围内, 直接赋值即可)
        parent.client = client
        monkeypatch.setitem(sys.modules, "win32com", parent)
        monkeypatch.setitem(sys.modules, "win32com.client", client)
        self.client = client

    def _fake_excel(self, used_range_row: int):
        class _UsedRange:
            Row = used_range_row
            Column = 1
            Value = (("项目", "期末余额"), ("货币资金", 100.0))

        class _Sheet:
            Name = "资产负债表"
            UsedRange = _UsedRange()

        class _Worksheets:
            Count = 1

            def __iter__(self):
                return iter([_Sheet()])

        class _Workbook:
            Worksheets = _Worksheets()

            def Close(self, SaveChanges: bool = False) -> None:
                pass

        class _Workbooks:
            def Open(self, *args, **kwargs):
                return _Workbook()

        class _Excel:
            Workbooks = _Workbooks()

            def Quit(self) -> None:
                pass

        return _Excel()

    def test_row_offset_applied(self, monkeypatch) -> None:
        """UsedRange 起始行为 5: 首条数据行 _row = 6 (5=表头), 而非 2。"""
        import fsa.core.importer.excel_reader as reader

        monkeypatch.setattr(
            self.client, "DispatchEx", lambda _prog: self._fake_excel(5), raising=False
        )
        result = reader._read_excel_com_sync("fake.xlsx")
        raw = result["资产负债表"]
        assert len(raw.rows) == 1
        assert raw.rows[0]["_row"] == 6

    def test_no_offset_when_used_range_starts_at_a1(self, monkeypatch) -> None:
        """UsedRange 起始行为 1: _row 与常规读取一致 (回归)。"""
        import fsa.core.importer.excel_reader as reader

        monkeypatch.setattr(
            self.client, "DispatchEx", lambda _prog: self._fake_excel(1), raising=False
        )
        result = reader._read_excel_com_sync("fake.xlsx")
        raw = result["资产负债表"]
        assert raw.rows[0]["_row"] == 2


class TestComSessionRecovery:
    """ExcelComSession 自愈回归 (2026-09-17 "每一个导入都失败"根因)。"""

    @pytest.fixture(autouse=True)
    def _fake_win32(self, monkeypatch):
        import sys
        from types import ModuleType

        parent = ModuleType("win32com")
        client = ModuleType("win32com.client")
        parent.client = client
        monkeypatch.setitem(sys.modules, "win32com", parent)
        monkeypatch.setitem(sys.modules, "win32com.client", client)
        self.client = client

    @staticmethod
    def _make_excel_factory(fail_first_open: bool):
        """生成假 Excel 工厂: fail_first_open=True 时首个实例的 Open 抛异常。"""
        counter = {"instances": 0}

        def factory(_prog: str):
            counter["instances"] += 1
            is_first = counter["instances"] == 1

            class _UsedRange:
                Row = 1
                Column = 1
                Value = (("项目", "期末余额"), ("货币资金", 100.0))

            class _Sheet:
                Name = "资产负债表"
                UsedRange = _UsedRange()

            class _Worksheets:
                Count = 1

                def __iter__(self):
                    return iter([_Sheet()])

            class _Workbook:
                Worksheets = _Worksheets()

                def Close(self, SaveChanges: bool = False) -> None:
                    pass

            class _Workbooks:
                def Open(self, *args, **kwargs):
                    if is_first and fail_first_open:
                        raise RuntimeError("模拟 Excel 进程死亡")
                    return _Workbook()

            class _Excel:
                Workbooks = _Workbooks()

                def Quit(self) -> None:
                    pass

            return _Excel()

        return factory, counter

    def test_session_retries_with_fresh_excel_when_broken(self, monkeypatch) -> None:
        """共享进程死亡: read_file 丢弃坏实例、重启新进程并重试, 最终成功。"""
        factory, counter = self._make_excel_factory(fail_first_open=True)
        monkeypatch.setattr(self.client, "DispatchEx", factory, raising=False)

        from fsa.core.importer.excel_reader import ExcelComSession

        with ExcelComSession() as session:
            result = session.read_file("fake.xlsx")

        assert "资产负债表" in result
        assert counter["instances"] == 2, "应丢弃死亡实例并重启新实例重试一次"

    def test_property_set_failure_is_best_effort(self, monkeypatch) -> None:
        """属性写入被拒 (Excel 启动繁忙) 不构成致命错误, 会话仍正常读取。"""

        class _UsedRange:
            Row = 1
            Column = 1
            Value = (("项目", "期末余额"), ("货币资金", 100.0))

        class _Sheet:
            Name = "资产负债表"
            UsedRange = _UsedRange()

        class _Worksheets:
            Count = 1

            def __iter__(self):
                return iter([_Sheet()])

        class _Workbook:
            Worksheets = _Worksheets()

            def Close(self, SaveChanges: bool = False) -> None:
                pass

        class _Workbooks:
            def Open(self, *args, **kwargs):
                return _Workbook()

        class _Excel:
            Workbooks = _Workbooks()

            def __setattr__(self, name: str, value: object) -> None:
                if name in ("Visible", "DisplayAlerts", "AskToUpdateLinks"):
                    raise AttributeError(
                        f"Property 'Excel.Application.{name}' can not be set."
                    )
                super().__setattr__(name, value)

            def Quit(self) -> None:
                pass

        monkeypatch.setattr(self.client, "DispatchEx", lambda _prog: _Excel(), raising=False)

        from fsa.core.importer.excel_reader import ExcelComSession

        with ExcelComSession() as session:
            result = session.read_file("fake.xlsx")

        assert "资产负债表" in result

    def test_broken_session_does_not_poison_batch(self, monkeypatch) -> None:
        """死亡实例被丢弃后, 批次内下一个文件用新实例正常读取。"""
        factory, counter = self._make_excel_factory(fail_first_open=True)
        monkeypatch.setattr(self.client, "DispatchEx", factory, raising=False)

        from fsa.core.importer.excel_reader import ExcelComSession

        with ExcelComSession() as session:
            first = session.read_file("a.xlsx")
            second = session.read_file("b.xlsx")

        assert "资产负债表" in first
        assert "资产负债表" in second
        assert counter["instances"] == 2, "死亡实例只重启一次, 第二个文件复用新实例"


class TestZombieExcelCleanup:
    """不可见僵尸 Excel 清理回归 (2026-09-17 "全部失败"根因)。"""

    def test_parse_tasklist_pids_extracts_pids(self) -> None:
        """tasklist CSV 输出解析出 PID 集合。"""
        from fsa.core.importer.excel_reader import _parse_tasklist_pids

        output = '"EXCEL.EXE","1234","Console","1","100,000 K"\n"EXCEL.EXE","5678","Console","1","200,000 K"\n'
        assert _parse_tasklist_pids(output) == {1234, 5678}

    def test_parse_tasklist_pids_ignores_garbage(self) -> None:
        """无任务/表头等噪声输出返回空集合。"""
        from fsa.core.importer.excel_reader import _parse_tasklist_pids

        assert _parse_tasklist_pids("INFO: No tasks are running which match the criteria.\n\n") == set()

    def test_cleanup_invisible_kills_only_invisible(self, monkeypatch) -> None:
        """清理只杀不可见实例, 可见 (用户) Excel 绝不动。"""
        import fsa.core.importer.excel_reader as reader

        monkeypatch.setattr(reader, "_snapshot_excel_pids", lambda: {1, 2, 3})
        monkeypatch.setattr(reader, "_visible_excel_pids", lambda: {1})
        killed: list[set[int]] = []

        def fake_kill(pids: set[int]) -> int:
            killed.append(set(pids))
            return len(pids)

        monkeypatch.setattr(reader, "_kill_pids", fake_kill)
        assert reader.cleanup_invisible_excel() == 2
        assert killed == [{2, 3}], "仅不可见 {2,3} 被清理"

    def test_cleanup_no_excel_returns_zero(self, monkeypatch) -> None:
        """无 Excel 进程时清理为空操作。"""
        import fsa.core.importer.excel_reader as reader

        monkeypatch.setattr(reader, "_snapshot_excel_pids", lambda: set())
        assert reader.cleanup_invisible_excel() == 0

    def test_own_zombies_guard_none_snapshot(self, monkeypatch) -> None:
        """会话从未启动时 (快照为 None) 不做任何进程操作。"""
        import fsa.core.importer.excel_reader as reader

        def boom() -> set[int]:
            raise AssertionError("快照为 None 时不应查询进程")

        monkeypatch.setattr(reader, "_snapshot_excel_pids", boom)
        session = reader.ExcelComSession()
        session._cleanup_own_zombies()  # 无异常即通过

    def test_read_file_escalates_to_global_cleanup(self, monkeypatch) -> None:
        """两次失败后清理全局僵尸并做第三次 (最后一次) 重试成功。"""
        import fsa.core.importer.excel_reader as reader

        calls = {"read": 0, "cleanup": 0}

        def fake_read(excel: object, path: str, progress_cb: object = None) -> dict:
            calls["read"] += 1
            if calls["read"] < 3:
                raise reader.FSAError(f"模拟失败 {calls['read']}")
            return {"资产负债表": object()}

        def fake_cleanup() -> int:
            calls["cleanup"] += 1
            return 1  # 清理到 1 个僵尸

        monkeypatch.setattr(reader, "_read_workbook_sheets", fake_read)
        monkeypatch.setattr(reader, "cleanup_invisible_excel", fake_cleanup)

        session = reader.ExcelComSession()
        session._ensure_started = lambda: None  # type: ignore[method-assign]
        session._reset_broken = lambda cause: None  # type: ignore[method-assign]
        result = session.read_file("fake.xlsx")
        assert "资产负债表" in result
        assert calls == {"read": 3, "cleanup": 1}

    def test_read_file_raises_when_no_zombies(self, monkeypatch) -> None:
        """两次失败且无僵尸可清时立即抛错 (不做无用第三次尝试)。"""
        import pytest

        import fsa.core.importer.excel_reader as reader

        calls = {"read": 0}

        def fake_read(excel: object, path: str, progress_cb: object = None) -> dict:
            calls["read"] += 1
            raise reader.FSAError("模拟失败")

        monkeypatch.setattr(reader, "_read_workbook_sheets", fake_read)
        monkeypatch.setattr(reader, "cleanup_invisible_excel", lambda: 0)

        session = reader.ExcelComSession()
        session._ensure_started = lambda: None  # type: ignore[method-assign]
        session._reset_broken = lambda cause: None  # type: ignore[method-assign]
        with pytest.raises(reader.FSAError, match="模拟失败"):
            session.read_file("fake.xlsx")
        assert calls["read"] == 2
