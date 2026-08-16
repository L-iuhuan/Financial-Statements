"""大文件读取基准回归 (slow 标记, 默认跳过; 发布前手动运行)。

用法: pytest -m slow tests/importer/test_excel_reader_large.py -q
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from openpyxl import Workbook

from fsa.core.importer import excel_reader
from fsa.core.importer.excel_reader import read_excel


@pytest.fixture(scope="module")
def large_journal_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """生成 10 万行序时账工作簿 (write_only 流式写入)。"""
    path = tmp_path_factory.mktemp("large") / "journal_100k.xlsx"
    wb = Workbook(write_only=True)
    ws = wb.create_sheet("序时账")
    ws.append(["日期", "凭证号", "科目名称", "摘要", "方向", "金额"])
    for index in range(100_000):
        ws.append(
            [
                f"2024-06-{index % 28 + 1:02d}",
                f"记-{index + 1:06d}",
                "银行存款",
                "性能基准数据",
                "借",
                100.0 + index,
            ]
        )
    wb.save(path)
    return path


@pytest.mark.slow
class TestLargeExcelImport:
    """10 万行合成文件导入时间基线 < 30 秒。"""

    def test_read_100k_rows_under_30_seconds(self, large_journal_path: Path) -> None:
        start = time.perf_counter()
        data = read_excel(str(large_journal_path))
        elapsed = time.perf_counter() - start

        sheet = next(iter(data.values()))
        assert len(sheet.rows) == 100_000
        assert elapsed < 30, f"导入耗时 {elapsed:.1f}s, 超过 30s 基线"

    def test_streaming_path_forced_by_threshold(self, large_journal_path: Path, monkeypatch) -> None:
        """强制流式读取路径 (read_only=True) 结果与普通读取一致。"""
        monkeypatch.setattr(excel_reader, "_LARGE_FILE_THRESHOLD", 1)
        data = read_excel(str(large_journal_path))

        sheet = next(iter(data.values()))
        assert len(sheet.rows) == 100_000
        assert sheet.rows[0]["凭证号"] == "记-000001"
        assert sheet.rows[-1]["金额"] == pytest.approx(100_099.0)
