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
