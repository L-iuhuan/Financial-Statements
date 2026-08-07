"""excel_reader 模块测试: 读取 Excel 文件返回原始数据。

测试内容: 正常读取、文件不存在、空文件、合并单元格、多 sheet。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fsa.core.importer.excel_reader import RawSheetData, read_excel


class TestReadExcelNormal:
    """测试正常读取 Excel 文件。"""

    def test_read_balance_sheet_returns_correct_sheet_name(self) -> None:
        from tests.importer.conftest import make_balance_sheet_excel

        path = make_balance_sheet_excel()
        data = read_excel(str(path))

        assert "资产负债表" in data

    def test_read_balance_sheet_has_headers(self) -> None:
        from tests.importer.conftest import make_balance_sheet_excel

        path = make_balance_sheet_excel()
        data = read_excel(str(path))

        sheet = data["资产负债表"]
        assert "项目" in sheet.headers
        assert "期末余额" in sheet.headers
        assert "年初余额" in sheet.headers

    def test_read_balance_sheet_has_rows(self) -> None:
        from tests.importer.conftest import make_balance_sheet_excel

        path = make_balance_sheet_excel()
        data = read_excel(str(path))

        sheet = data["资产负债表"]
        assert len(sheet.rows) > 0

    def test_read_balance_sheet_row_has_correct_data(self) -> None:
        from tests.importer.conftest import make_balance_sheet_excel

        path = make_balance_sheet_excel()
        data = read_excel(str(path))

        sheet = data["资产负债表"]
        row = sheet.rows[0]
        assert row["项目"] == "流动资产合计"
        assert row["期末余额"] == 500000.00
        assert row["_row"] == 2

    def test_read_balance_sheet_asset_total_correct(self) -> None:
        from tests.importer.conftest import make_balance_sheet_excel

        path = make_balance_sheet_excel()
        data = read_excel(str(path))

        sheet = data["资产负债表"]
        asset_row = next(r for r in sheet.rows if r["项目"] == "资产总计")
        assert asset_row["期末余额"] == 2000000.00
        assert asset_row["年初余额"] == 1850000.00

    def test_read_income_statement_returns_correct_headers(self) -> None:
        from tests.importer.conftest import make_income_statement_excel

        path = make_income_statement_excel()
        data = read_excel(str(path))

        sheet = data["利润表"]
        assert "本期金额" in sheet.headers
        assert "上期金额" in sheet.headers

    def test_read_income_statement_net_profit_correct(self) -> None:
        from tests.importer.conftest import make_income_statement_excel

        path = make_income_statement_excel()
        data = read_excel(str(path))

        sheet = data["利润表"]
        np_row = next(r for r in sheet.rows if r["项目"] == "净利润")
        assert np_row["本期金额"] == 405000.00

    def test_read_cash_flow_statement_correct(self) -> None:
        from tests.importer.conftest import make_cash_flow_excel

        path = make_cash_flow_excel()
        data = read_excel(str(path))

        sheet = data["现金流量表"]
        operating_row = next(
            r for r in sheet.rows if r["项目"] == "经营活动产生的现金流量净额"
        )
        assert operating_row["本期金额"] == 500000.00

    def test_read_multi_sheet_returns_all_sheets(self) -> None:
        from tests.importer.conftest import make_multi_sheet_excel

        path = make_multi_sheet_excel()
        data = read_excel(str(path))

        assert "资产负债表" in data
        assert "利润表" in data
        assert "现金流量表" in data
        assert len(data) == 3

    def test_read_multi_sheet_each_has_data(self) -> None:
        from tests.importer.conftest import make_multi_sheet_excel

        path = make_multi_sheet_excel()
        data = read_excel(str(path))

        for sheet in data.values():
            assert len(sheet.rows) > 0
            assert len(sheet.headers) > 0


class TestReadExcelErrors:
    """测试错误处理。"""

    def test_read_nonexistent_file_raises_error(self) -> None:
        with pytest.raises(FileNotFoundError):
            read_excel("nonexistent_file.xlsx")

    def test_read_empty_excel_returns_empty_rows(self) -> None:
        from tests.importer.conftest import make_empty_excel

        path = make_empty_excel()
        data = read_excel(str(path))

        assert len(data) == 1
        sheet = list(data.values())[0]
        assert len(sheet.rows) == 0


class TestReadExcelMergedCells:
    """测试合并单元格处理。"""

    def test_read_merged_cells_still_returns_data(self) -> None:
        from tests.importer.conftest import make_excel_with_merged_cells

        path = make_excel_with_merged_cells()
        data = read_excel(str(path))

        sheet = data["资产负债表"]
        assert len(sheet.rows) > 0
        asset_row = next(r for r in sheet.rows if r["项目"] == "资产总计")
        assert asset_row["期末余额"] == 2000000.00
        # 合并单元格的行数据应从第3行开始
        assert asset_row["_row"] == 4


class TestRawSheetDataProperties:
    """测试 RawSheetData 属性。"""

    def test_name_property_returns_sheet_name(self) -> None:
        from tests.importer.conftest import make_balance_sheet_excel

        path = make_balance_sheet_excel()
        data = read_excel(str(path))

        sheet = data["资产负债表"]
        assert sheet.name == "资产负债表"

    def test_rows_with_zero_values(self) -> None:
        from tests.importer.conftest import make_balance_sheet_excel

        path = make_balance_sheet_excel()
        data = read_excel(str(path))

        sheet = data["资产负债表"]
        treasury_row = next(r for r in sheet.rows if r["项目"] == "库存股")
        assert treasury_row["期末余额"] == 0.0

    def test_rows_with_nonexistent_header_returns_none(self) -> None:
        from tests.importer.conftest import make_balance_sheet_excel

        path = make_balance_sheet_excel()
        data = read_excel(str(path))

        sheet = data["资产负债表"]
        row = sheet.rows[0]
        assert row.get("不存在的列") is None