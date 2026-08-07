"""report_identifier 模块测试: 从工作表识别报表类型。

测试内容: 按工作表名识别、按内容识别、多 sheet、未识别、英文名。
"""

from __future__ import annotations

from fsa.core.models.report import ReportType
from fsa.core.importer.report_identifier import identify_reports


class TestIdentifyBySheetName:
    """测试通过工作表名称识别报表类型。"""

    def test_identify_balance_sheet_by_chinese_name(self) -> None:
        from tests.importer.conftest import make_balance_sheet_excel
        from fsa.core.importer.excel_reader import read_excel

        path = make_balance_sheet_excel()
        data = read_excel(str(path))
        results = identify_reports(data)

        assert len(results) == 1
        sheet_name, report_type = results[0]
        assert report_type == ReportType.BALANCE_SHEET
        assert sheet_name == "资产负债表"

    def test_identify_income_statement_by_chinese_name(self) -> None:
        from tests.importer.conftest import make_income_statement_excel
        from fsa.core.importer.excel_reader import read_excel

        path = make_income_statement_excel()
        data = read_excel(str(path))
        results = identify_reports(data)

        assert len(results) == 1
        _, report_type = results[0]
        assert report_type == ReportType.INCOME_STATEMENT

    def test_identify_cash_flow_by_chinese_name(self) -> None:
        from tests.importer.conftest import make_cash_flow_excel
        from fsa.core.importer.excel_reader import read_excel

        path = make_cash_flow_excel()
        data = read_excel(str(path))
        results = identify_reports(data)

        assert len(results) == 1
        _, report_type = results[0]
        assert report_type == ReportType.CASH_FLOW_STATEMENT


class TestIdentifyMultiSheet:
    """测试多工作表文件识别。"""

    def test_identify_all_three_sheets(self) -> None:
        from tests.importer.conftest import make_multi_sheet_excel
        from fsa.core.importer.excel_reader import read_excel

        path = make_multi_sheet_excel()
        data = read_excel(str(path))
        results = identify_reports(data)

        assert len(results) == 3
        types = {rt for _, rt in results}
        assert ReportType.BALANCE_SHEET in types
        assert ReportType.INCOME_STATEMENT in types
        assert ReportType.CASH_FLOW_STATEMENT in types


class TestIdentifyByContent:
    """测试通过工作表内容识别报表类型（当工作表名不匹配时）。"""

    def test_identify_by_balance_sheet_keywords_in_content(self) -> None:
        from fsa.core.importer.excel_reader import RawSheetData

        raw = RawSheetData(
            name="Sheet1",
            headers=["项目", "期末余额"],
            rows=[
                {"_row": 2, "项目": "资产总计", "期末余额": 1000000.0},
                {"_row": 3, "项目": "负债合计", "期末余额": 600000.0},
            ],
        )
        results = identify_reports({"Sheet1": raw})
        assert len(results) == 1
        _, report_type = results[0]
        assert report_type == ReportType.BALANCE_SHEET

    def test_identify_by_income_statement_keywords_in_content(self) -> None:
        from fsa.core.importer.excel_reader import RawSheetData

        raw = RawSheetData(
            name="Sheet1",
            headers=["项目", "本期金额"],
            rows=[
                {"_row": 2, "项目": "营业收入", "本期金额": 500000.0},
                {"_row": 3, "项目": "营业利润", "本期金额": 100000.0},
            ],
        )
        results = identify_reports({"Sheet1": raw})
        assert len(results) == 1
        _, report_type = results[0]
        assert report_type == ReportType.INCOME_STATEMENT

    def test_identify_by_cash_flow_keywords_in_content(self) -> None:
        from fsa.core.importer.excel_reader import RawSheetData

        raw = RawSheetData(
            name="Sheet1",
            headers=["项目", "本期金额"],
            rows=[
                {"_row": 2, "项目": "经营活动产生的现金流量净额", "本期金额": 100000.0},
            ],
        )
        results = identify_reports({"Sheet1": raw})
        assert len(results) == 1
        _, report_type = results[0]
        assert report_type == ReportType.CASH_FLOW_STATEMENT


class TestEdgeCases:
    """测试边界情况。"""

    def test_empty_sheet_returns_empty_list(self) -> None:
        from tests.importer.conftest import make_empty_excel
        from fsa.core.importer.excel_reader import read_excel

        path = make_empty_excel()
        data = read_excel(str(path))
        results = identify_reports(data)

        assert len(results) == 0

    def test_unrecognized_sheet_returns_empty_list(self) -> None:
        from fsa.core.importer.excel_reader import RawSheetData

        raw = RawSheetData(
            name="Unknown",
            headers=["A", "B"],
            rows=[{"_row": 2, "A": "something", "B": 123}],
        )
        results = identify_reports({"Unknown": raw})
        assert len(results) == 0

    def test_sheet_name_has_priority_over_content(self) -> None:
        """工作表名中的关键词优先级高于内容关键词。"""
        from fsa.core.importer.excel_reader import RawSheetData

        raw = RawSheetData(
            name="现金流量表",
            headers=["项目", "期末余额"],
            rows=[
                {"_row": 2, "项目": "资产总计", "期末余额": 1000000.0},
            ],
        )
        results = identify_reports({"现金流量表": raw})
        _, report_type = results[0]
        assert report_type == ReportType.CASH_FLOW_STATEMENT

    def test_multiple_mixed_sheets(self) -> None:
        """混合识别的和未识别的 sheet。"""
        from fsa.core.importer.excel_reader import RawSheetData

        data = {
            "资产负债表": RawSheetData(
                name="资产负债表", headers=["项目"], rows=[]
            ),
            "Unknown": RawSheetData(
                name="Unknown", headers=["A"], rows=[]
            ),
        }
        results = identify_reports(data)
        assert len(results) == 1
        _, report_type = results[0]
        assert report_type == ReportType.BALANCE_SHEET