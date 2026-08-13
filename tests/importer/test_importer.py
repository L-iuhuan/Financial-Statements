"""ImportService 集成测试: 端到端从 Excel 文件导入 Report 对象。

测试内容: 单文件导入、多 sheet 导入、指定 sheet 导入、错误处理。
"""

from __future__ import annotations

import pytest

from fsa.core.importer.importer import ImportService
from fsa.core.models.report import ReportType


class TestImportFile:
    """测试 import_file 方法（导入整个文件，返回所有识别的报表）。"""

    def test_import_balance_sheet_returns_one_report(self) -> None:
        from tests.importer.conftest import make_balance_sheet_excel

        path = make_balance_sheet_excel()
        service = ImportService()
        reports = service.import_file(str(path))

        assert len(reports) == 1
        assert reports[0].report_type == ReportType.BALANCE_SHEET

    def test_import_balance_sheet_has_correct_source_file(self) -> None:
        from tests.importer.conftest import make_balance_sheet_excel

        path = make_balance_sheet_excel()
        service = ImportService()
        reports = service.import_file(str(path))

        assert reports[0].source_file == str(path)

    def test_import_balance_sheet_has_items(self) -> None:
        from tests.importer.conftest import make_balance_sheet_excel

        path = make_balance_sheet_excel()
        service = ImportService()
        reports = service.import_file(str(path))

        report = reports[0]
        assert len(report.items) > 0

    def test_import_balance_sheet_asset_total_correct(self) -> None:
        from tests.importer.conftest import make_balance_sheet_excel

        path = make_balance_sheet_excel()
        service = ImportService()
        reports = service.import_file(str(path))

        report = reports[0]
        amount = report.get_amount("asset_total")
        assert amount == 2000000.00

    def test_import_balance_sheet_equality_holds(self) -> None:
        """验证资产=负债+所有者权益的基本公式。"""
        from tests.importer.conftest import make_balance_sheet_excel

        path = make_balance_sheet_excel()
        service = ImportService()
        reports = service.import_file(str(path))

        report = reports[0]
        asset = report.get_amount("asset_total")
        liability = report.get_amount("liability_total")
        equity = report.get_amount("equity_total")
        assert asset is not None
        assert liability is not None
        assert equity is not None
        assert asset == liability + equity

    def test_import_income_statement_returns_one_report(self) -> None:
        from tests.importer.conftest import make_income_statement_excel

        path = make_income_statement_excel()
        service = ImportService()
        reports = service.import_file(str(path))

        assert len(reports) == 1
        assert reports[0].report_type == ReportType.INCOME_STATEMENT

    def test_import_income_statement_net_profit_correct(self) -> None:
        from tests.importer.conftest import make_income_statement_excel

        path = make_income_statement_excel()
        service = ImportService()
        reports = service.import_file(str(path))

        report = reports[0]
        amount = report.get_amount("net_profit")
        assert amount == 405000.00

    def test_import_cash_flow_returns_one_report(self) -> None:
        from tests.importer.conftest import make_cash_flow_excel

        path = make_cash_flow_excel()
        service = ImportService()
        reports = service.import_file(str(path))

        assert len(reports) == 1
        assert reports[0].report_type == ReportType.CASH_FLOW_STATEMENT

    def test_import_multi_sheet_returns_three_reports(self) -> None:
        from tests.importer.conftest import make_multi_sheet_excel

        path = make_multi_sheet_excel()
        service = ImportService()
        reports = service.import_file(str(path))

        assert len(reports) == 3
        types = {r.report_type for r in reports}
        assert ReportType.BALANCE_SHEET in types
        assert ReportType.INCOME_STATEMENT in types
        assert ReportType.CASH_FLOW_STATEMENT in types

    def test_import_multi_sheet_all_have_items(self) -> None:
        from tests.importer.conftest import make_multi_sheet_excel

        path = make_multi_sheet_excel()
        service = ImportService()
        reports = service.import_file(str(path))

        for report in reports:
            assert len(report.items) > 0

    def test_import_multi_sheet_all_have_source_file(self) -> None:
        from tests.importer.conftest import make_multi_sheet_excel

        path = make_multi_sheet_excel()
        service = ImportService()
        reports = service.import_file(str(path))

        for report in reports:
            assert report.source_file == str(path)


class TestImportSheet:
    """测试 import_sheet 方法（导入指定工作表）。"""

    def test_import_specific_sheet_by_name(self) -> None:
        from tests.importer.conftest import make_multi_sheet_excel

        path = make_multi_sheet_excel()
        service = ImportService()
        report = service.import_sheet(str(path), "资产负债表")

        assert report.report_type == ReportType.BALANCE_SHEET
        assert report.get_amount("asset_total") == 2000000.00

    def test_import_specific_sheet_income_statement(self) -> None:
        from tests.importer.conftest import make_multi_sheet_excel

        path = make_multi_sheet_excel()
        service = ImportService()
        report = service.import_sheet(str(path), "利润表")

        assert report.report_type == ReportType.INCOME_STATEMENT
        assert report.get_amount("net_profit") == 405000.00

    def test_import_sheet_not_found_raises_error(self) -> None:
        from tests.importer.conftest import make_balance_sheet_excel

        path = make_balance_sheet_excel()
        service = ImportService()

        with pytest.raises(ValueError):
            service.import_sheet(str(path), "不存在的工作表")


class TestImportErrors:
    """测试错误处理。"""

    def test_import_nonexistent_file_raises_error(self) -> None:
        service = ImportService()
        with pytest.raises(FileNotFoundError):
            service.import_file("nonexistent_file.xlsx")

    def test_import_empty_file_returns_empty_list(self) -> None:
        from tests.importer.conftest import make_empty_excel

        path = make_empty_excel()
        service = ImportService()
        reports = service.import_file(str(path))

        assert len(reports) == 0


class TestImportWithPeriod:
    """测试设置期间。"""

    def test_import_with_period_sets_on_all_reports(self) -> None:
        from tests.importer.conftest import make_multi_sheet_excel

        path = make_multi_sheet_excel()
        service = ImportService(period="2024-12")
        reports = service.import_file(str(path))

        for report in reports:
            assert report.period == "2024-12"


class TestImportServiceDefaultPeriod:
    """测试默认期间。"""

    def test_import_without_period_uses_empty(self) -> None:
        from tests.importer.conftest import make_balance_sheet_excel

        path = make_balance_sheet_excel()
        service = ImportService()
        reports = service.import_file(str(path))

        assert reports[0].period == ""
