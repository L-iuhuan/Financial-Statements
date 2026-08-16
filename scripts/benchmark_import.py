"""Excel 大文件导入基准: 生成 N 行序时账并计时 read_excel。

用法:
    python scripts/benchmark_import.py [行数] [输出xlsx路径]
默认 10 万行, 输出到临时目录。
"""

from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

from openpyxl import Workbook

from fsa.core.importer.excel_reader import read_excel


def main() -> int:
    rows = int(sys.argv[1]) if len(sys.argv) > 1 else 100_000
    output = Path(sys.argv[2]) if len(sys.argv) > 2 else (Path(tempfile.gettempdir()) / f"fsa_benchmark_{rows}.xlsx")

    start = time.perf_counter()
    wb = Workbook(write_only=True)
    ws = wb.create_sheet("序时账")
    ws.append(["日期", "凭证号", "科目名称", "摘要", "方向", "金额"])
    for index in range(rows):
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
    wb.save(output)
    write_seconds = time.perf_counter() - start

    start = time.perf_counter()
    data = read_excel(str(output))
    read_seconds = time.perf_counter() - start
    sheet = next(iter(data.values()))
    print(f"文件: {output} ({output.stat().st_size / 1024 / 1024:.1f} MB)")
    print(f"生成 {rows} 行: {write_seconds:.2f}s")
    print(f"读取 {len(sheet.rows)} 行: {read_seconds:.2f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
