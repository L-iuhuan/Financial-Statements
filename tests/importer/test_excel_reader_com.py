"""read_excel_com 与常规读取失败自动回退的测试。"""

from __future__ import annotations

from importlib.util import find_spec
from pathlib import Path

import pytest

from fsa.core.exceptions import FSAError
from fsa.core.importer.excel_reader import read_excel, read_excel_com


def test_read_excel_com_roundtrip(tmp_path: Path) -> None:
    """有 pywin32 且 Excel 可用时，COM 读取结果与常规读取一致。"""
    if find_spec("win32com.client") is None:
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
    if find_spec("win32com.client") is not None:
        pytest.skip("已安装 pywin32，跳过缺依赖分支")

    encrypted_like = tmp_path / "encrypted.xlsx"
    encrypted_like.write_bytes("该文件为密文".encode())

    with pytest.raises(FSAError, match="pywin32"):
        read_excel(str(encrypted_like))
