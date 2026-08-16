"""PDF 读取器测试: 测试 read_pdf 函数 + ImportService 集成。

测试内容: 读取 PDF, 验证 RawSheetData 结构, import_file 集成, 双列金额提取,
校验集成, 合并报表识别, 错误处理。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fsa.core.importer.excel_reader import RawSheetData
from fsa.core.models.report import ReportType

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "real_reports"
THREE_REPORTS_PDF = FIXTURE_DIR / "测试报表_三大报表.pdf"
MERGED_BS_PDF = FIXTURE_DIR / "测试报表_合并资产负债表.pdf"

# PDF 行号编码基数 (与 src/fsa/core/importer/pdf_reader.py 保持一致, D-01)
_PDF_ROW_BASE = 10_000_000


# ── mock pdfplumber 的辅助类 ──────────────────────────────


class _FakePage:
    """模拟 pdfplumber 页面, 仅提供 extract_tables。"""

    def __init__(
        self,
        table: list[list[str | None]],
        tables: list[list[list[str | None]]] | None = None,
    ) -> None:
        self._tables = tables if tables is not None else [table]

    def extract_tables(self) -> list[list[list[str | None]]]:
        return self._tables


class _FakePdf:
    """模拟 pdfplumber.open 返回的上下文管理器。"""

    def __init__(self, pages: list[_FakePage]) -> None:
        self.pages = pages

    def __enter__(self) -> _FakePdf:
        return self

    def __exit__(self, *exc: object) -> bool:
        return False


class _FakePdfModule:
    """模拟 pdfplumber 模块 (仅 open), 通过 monkeypatch 注入 pdf_reader。"""

    def __init__(self, pages: list[_FakePage]) -> None:
        self._pages = pages

    def open(self, path: str, **kwargs: object) -> _FakePdf:
        return _FakePdf(self._pages)


_BS_TABLE: list[list[str | None]] = [
    ["资产负债表", None, None],
    ["项目", "期末余额", "年初余额"],
    ["货币资金", "100", "80"],
    ["应收账款", "200", "150"],
    ["", "", ""],
    ["资产总计", "300", "230"],
    ["负债合计", "180", "130"],
    ["所有者权益合计", "120", "100"],
]

_IS_TABLE: list[list[str | None]] = [
    ["利润表", None, None],
    ["项目", "本期金额", "上期金额"],
    ["营业收入", "300", "250"],
    ["净利润", "100", "80"],
]


class TestReadPdf:
    """测试 read_pdf 函数的基本功能。"""

    def test_read_pdf_returns_three_sheets(self) -> None:
        """读取三大报表 PDF 应返回 3 个 RawSheetData。"""
        from fsa.core.importer.pdf_reader import read_pdf

        data = read_pdf(str(THREE_REPORTS_PDF))
        assert len(data) == 3

    def test_read_pdf_sheet_names_contain_report_titles(self) -> None:
        """每个 sheet 的 name 应包含报表标题关键词。"""
        from fsa.core.importer.pdf_reader import read_pdf

        data = read_pdf(str(THREE_REPORTS_PDF))
        names = list(data.keys())
        has_bs = any("资产负债" in n for n in names)
        has_is = any("利润" in n for n in names)
        has_cf = any("现金流量" in n or "现金" in n for n in names)
        assert has_bs, f"资产负债表未识别, names={names}"
        assert has_is, f"利润表未识别, names={names}"
        assert has_cf, f"现金流量表未识别, names={names}"

    def test_read_pdf_each_sheet_has_headers(self) -> None:
        """每个 sheet 应有 headers（项目列 + 金额列）。"""
        from fsa.core.importer.pdf_reader import read_pdf

        data = read_pdf(str(THREE_REPORTS_PDF))
        for name, raw in data.items():
            assert len(raw.headers) >= 2, f"「{name}」headers 不足: {raw.headers}"
            assert "项目" in raw.headers, f"「{name}」缺少'项目'列: {raw.headers}"

    def test_read_pdf_each_sheet_has_rows(self) -> None:
        """每个 sheet 应有数据行。"""
        from fsa.core.importer.pdf_reader import read_pdf

        data = read_pdf(str(THREE_REPORTS_PDF))
        for name, raw in data.items():
            assert len(raw.rows) > 0, f"「{name}」无数据行"

    def test_read_pdf_rows_have_item_and_amount(self) -> None:
        """每个 sheet 的数据行应包含'项目'列和金额列。"""
        from fsa.core.importer.pdf_reader import read_pdf

        data = read_pdf(str(THREE_REPORTS_PDF))
        for name, raw in data.items():
            row = raw.rows[0]
            assert "项目" in row, f"「{name}」第一行无'项目'键"
            # 至少有一个金额列
            amount_cols = [h for h in raw.headers if h != "项目"]
            assert len(amount_cols) >= 1, f"「{name}」无金额列"

    def test_read_pdf_rows_have_row_number(self) -> None:
        """每个数据行应有 _row 键。"""
        from fsa.core.importer.pdf_reader import read_pdf

        data = read_pdf(str(THREE_REPORTS_PDF))
        for name, raw in data.items():
            for row in raw.rows:
                assert "_row" in row, f"「{name}」行缺少 _row: {row}"


class TestReadPdfBalanceSheet:
    """测试资产负债表 PDF 的具体内容。"""

    def test_bs_has_dual_amount_columns(self) -> None:
        """资产负债表应有期末余额和年初余额两列。"""
        from fsa.core.importer.pdf_reader import read_pdf

        data = read_pdf(str(THREE_REPORTS_PDF))
        bs_name = _find_sheet(data, "资产负债")
        raw = data[bs_name]
        amount_cols = [h for h in raw.headers if h != "项目"]
        assert len(amount_cols) >= 2, (
            f"资产负债表应有双列金额, 实际: {amount_cols}"
        )

    def test_bs_contains_asset_total(self) -> None:
        """资产负债表应包含'资产总计'行。"""
        from fsa.core.importer.pdf_reader import read_pdf

        data = read_pdf(str(THREE_REPORTS_PDF))
        bs_name = _find_sheet(data, "资产负债")
        raw = data[bs_name]
        items = [str(row.get("项目", "")) for row in raw.rows]
        has_asset = any("资产总计" in item or "资产总" in item for item in items)
        assert has_asset, f"未找到资产总计, items: {items[:5]}..."


class TestImportPdf:
    """测试 ImportService.import_file 对 PDF 的集成。"""

    def test_import_pdf_returns_three_reports(self) -> None:
        """导入 PDF 应返回 3 个 Report 对象。"""
        from fsa.core.importer.importer import ImportService

        service = ImportService()
        reports = service.import_file(str(THREE_REPORTS_PDF))
        assert len(reports) == 3

    def test_import_pdf_correct_types(self) -> None:
        """导入的报表应有正确的类型。"""
        from fsa.core.importer.importer import ImportService

        service = ImportService()
        reports = service.import_file(str(THREE_REPORTS_PDF))
        types = {r.report_type for r in reports}
        assert ReportType.BALANCE_SHEET in types
        assert ReportType.INCOME_STATEMENT in types
        assert ReportType.CASH_FLOW_STATEMENT in types

    def test_import_pdf_bs_has_asset_total(self) -> None:
        """资产负债表导入后应有 asset_total 项目。"""
        from fsa.core.importer.importer import ImportService

        service = ImportService()
        reports = service.import_file(str(THREE_REPORTS_PDF))
        bs = _find_report(reports, ReportType.BALANCE_SHEET)
        amount = bs.get_amount("asset_total")
        assert amount is not None, "未找到 asset_total"
        assert amount == 2000000.00

    def test_import_pdf_bs_equality_holds(self) -> None:
        """资产 = 负债 + 所有者权益。"""
        from fsa.core.importer.importer import ImportService

        service = ImportService()
        reports = service.import_file(str(THREE_REPORTS_PDF))
        bs = _find_report(reports, ReportType.BALANCE_SHEET)
        asset = bs.get_amount("asset_total")
        liability = bs.get_amount("liability_total")
        equity = bs.get_amount("equity_total")
        assert asset is not None
        assert liability is not None
        assert equity is not None
        assert asset == liability + equity

    def test_import_pdf_is_has_net_profit(self) -> None:
        """利润表应有净利润。"""
        from fsa.core.importer.importer import ImportService

        service = ImportService()
        reports = service.import_file(str(THREE_REPORTS_PDF))
        is_report = _find_report(reports, ReportType.INCOME_STATEMENT)
        amount = is_report.get_amount("net_profit")
        assert amount is not None
        assert amount == 405000.00

    def test_import_pdf_cf_has_operating_net(self) -> None:
        """现金流量表应有经营活动现金流量净额。"""
        from fsa.core.importer.importer import ImportService

        service = ImportService()
        reports = service.import_file(str(THREE_REPORTS_PDF))
        cf = _find_report(reports, ReportType.CASH_FLOW_STATEMENT)
        amount = cf.get_amount("operating_net")
        assert amount is not None
        assert amount == 400000.00

    def test_import_pdf_sets_source_file(self) -> None:
        """所有报表的 source_file 应指向 PDF 路径。"""
        from fsa.core.importer.importer import ImportService

        service = ImportService()
        reports = service.import_file(str(THREE_REPORTS_PDF))
        for report in reports:
            assert report.source_file == str(THREE_REPORTS_PDF)

    def test_import_pdf_all_have_items(self) -> None:
        """所有报表应有项目。"""
        from fsa.core.importer.importer import ImportService

        service = ImportService()
        reports = service.import_file(str(THREE_REPORTS_PDF))
        for report in reports:
            assert len(report.items) > 0, (
                f"{report.report_type.value} 无项目"
            )


class TestDualColumnExtraction:
    """测试双列金额提取（期初/上期金额）。"""

    def test_bs_items_have_beginning_amount(self) -> None:
        """资产负债表项目应有期初金额。"""
        from fsa.core.importer.importer import ImportService

        service = ImportService()
        reports = service.import_file(str(THREE_REPORTS_PDF))
        bs = _find_report(reports, ReportType.BALANCE_SHEET)
        items_with_beginning = [
            item for item in bs.items if item.beginning_amount is not None
        ]
        assert len(items_with_beginning) > 0, (
            "没有项目包含期初金额"
        )

    def test_bs_monetary_funds_beginning(self) -> None:
        """货币资金的期初金额应为 80000。"""
        from fsa.core.importer.importer import ImportService

        service = ImportService()
        reports = service.import_file(str(THREE_REPORTS_PDF))
        bs = _find_report(reports, ReportType.BALANCE_SHEET)
        item = bs.get_item("monetary_funds")
        assert item is not None
        assert item.beginning_amount == 80000.00


class TestPdfErrors:
    """测试错误处理。"""

    def test_missing_file_raises_filenotfound(self) -> None:
        """不存在的文件应抛出 FileNotFoundError。"""
        from fsa.core.importer.importer import ImportService

        service = ImportService()
        with pytest.raises(FileNotFoundError):
            service.import_file("nonexistent_file.pdf")

    def test_missing_file_read_pdf_raises_filenotfound(self) -> None:
        """read_pdf 对不存在的文件应抛出 FileNotFoundError。"""
        from fsa.core.importer.pdf_reader import read_pdf

        with pytest.raises(FileNotFoundError):
            read_pdf("nonexistent_file.pdf")


class TestPdfValidation:
    """测试导入 PDF 后进行完整校验。"""

    def test_validation_bs_bal_001_passes(self) -> None:
        """BS-BAL-001 (资产=负债+所有者权益) 应通过。"""
        from fsa.core.engine.registry import RuleRegistry
        from fsa.core.importer.importer import ImportService
        from fsa.services.validation_service import ValidationService

        rules_path = Path(__file__).parent.parent.parent / "cas_gouji_rule_library.json"
        registry = RuleRegistry.from_json(str(rules_path))
        service = ImportService()
        reports = service.import_file(str(THREE_REPORTS_PDF))
        validation = ValidationService(registry)
        summary = validation.validate(reports, period="2024-12")

        bs_bal_001 = _find_result(summary.results, "BS-BAL-001")
        assert bs_bal_001 is not None, "未找到 BS-BAL-001 结果"
        assert bs_bal_001.passed, (
            f"BS-BAL-001 应通过, 实际: {bs_bal_001.message}"
        )


class TestMergedReport:
    """测试合并报表（含"合并"前缀）的识别。"""

    def test_merged_bs_identified_correctly(self) -> None:
        """合并资产负债表应被识别为 BALANCE_SHEET。"""
        from fsa.core.importer.importer import ImportService

        service = ImportService()
        reports = service.import_file(str(MERGED_BS_PDF))
        assert len(reports) == 1
        assert reports[0].report_type == ReportType.BALANCE_SHEET

    def test_merged_bs_has_asset_total(self) -> None:
        """合并资产负债表应有 asset_total。"""
        from fsa.core.importer.importer import ImportService

        service = ImportService()
        reports = service.import_file(str(MERGED_BS_PDF))
        bs = reports[0]
        amount = bs.get_amount("asset_total")
        assert amount is not None
        assert amount == 2000000.00

    def test_merged_bs_equality_holds(self) -> None:
        """合并资产负债表: 资产 = 负债 + 所有者权益。"""
        from fsa.core.importer.importer import ImportService

        service = ImportService()
        reports = service.import_file(str(MERGED_BS_PDF))
        bs = reports[0]
        asset = bs.get_amount("asset_total")
        liability = bs.get_amount("liability_total")
        equity = bs.get_amount("equity_total")
        assert asset is not None
        assert liability is not None
        assert equity is not None
        assert asset == liability + equity


class TestParseCellValue:
    """测试 PDF 单元格值解析（统一金额解析）。"""

    def test_thousands_separator_parsed_to_float(self) -> None:
        from fsa.core.importer.pdf_reader import _parse_cell_value

        assert _parse_cell_value("1,000,000.50") == 1000000.50

    def test_parenthesized_negative_parsed(self) -> None:
        from fsa.core.importer.pdf_reader import _parse_cell_value

        assert _parse_cell_value("(1,291,800.12)") == -1291800.12

    def test_placeholder_parsed_to_zero(self) -> None:
        from fsa.core.importer.pdf_reader import _parse_cell_value

        assert _parse_cell_value("-") == 0.0
        assert _parse_cell_value("—") == 0.0

    def test_scientific_notation_parsed(self) -> None:
        from fsa.core.importer.pdf_reader import _parse_cell_value

        assert _parse_cell_value("1.5e6") == 1500000.0

    def test_empty_returns_none(self) -> None:
        from fsa.core.importer.pdf_reader import _parse_cell_value

        assert _parse_cell_value(None) is None
        assert _parse_cell_value("") is None

    def test_unparsable_returns_original_text(self) -> None:
        from fsa.core.importer.pdf_reader import _parse_cell_value

        assert _parse_cell_value("货币资金") == "货币资金"


class TestPdfRowSemantics:
    """D-01: PDF 行号应为「页码+表内行」可定位语义。"""

    def test_same_page_multiple_tables_are_all_extracted(self, monkeypatch) -> None:
        """一页内多个报表表格都应被提取, 不再只取第一张表。"""
        from fsa.core.importer import pdf_reader

        monkeypatch.setattr(
            pdf_reader,
            "pdfplumber",
            _FakePdfModule(
                [_FakePage(_BS_TABLE, tables=[_BS_TABLE, _IS_TABLE])]
            ),
        )
        data = pdf_reader.read_pdf(str(THREE_REPORTS_PDF))
        assert "资产负债表" in data
        assert "利润表" in data

    def test_cross_page_table_without_title_is_merged(self, monkeypatch) -> None:
        """次页无标题的续表通过表头唯一匹配合并到已有报表。"""
        from fsa.core.importer import pdf_reader

        continuation = [
            ["项目", "期末余额", "年初余额"],
            ["固定资产", "500", "480"],
            ["", "", ""],
            ["非流动资产合计", "600", "550"],
        ]
        monkeypatch.setattr(
            pdf_reader,
            "pdfplumber",
            _FakePdfModule([_FakePage(_BS_TABLE), _FakePage(continuation)]),
        )
        data = pdf_reader.read_pdf(str(THREE_REPORTS_PDF))
        bs = data["资产负债表"]
        items = [str(r.get("项目", "")) for r in bs.rows]
        assert "固定资产" in items
        assert "非流动资产合计" in items
        # 次页行号按第 2 页编码
        fixed_assets = next(
            r for r in bs.rows if str(r.get("项目", "")) == "固定资产"
        )
        assert fixed_assets["_row"] == 2 * _PDF_ROW_BASE + 2

    def test_read_pdf_encodes_page_and_table_row(self, monkeypatch) -> None:
        """数据行 _row = 页码 * 基数 + 表内 1-based 行号。"""
        from fsa.core.importer import pdf_reader

        monkeypatch.setattr(
            pdf_reader, "pdfplumber", _FakePdfModule([_FakePage(_BS_TABLE), _FakePage(_IS_TABLE)])
        )
        data = pdf_reader.read_pdf(str(THREE_REPORTS_PDF))
        assert "资产负债表" in data
        assert "利润表" in data

        bs_rows = {str(r.get("项目", "")): r["_row"] for r in data["资产负债表"].rows}
        # 货币资金在表内第 3 行 (标题行1, 表头行2, 数据行3)
        assert bs_rows["货币资金"] == 1 * _PDF_ROW_BASE + 3
        # 空行被跳过, 但真实行号保留: 资产总计在表内第 6 行
        assert bs_rows["资产总计"] == 1 * _PDF_ROW_BASE + 6

        is_rows = {str(r.get("项目", "")): r["_row"] for r in data["利润表"].rows}
        # 第 2 页: 净利润在表内第 4 行
        assert is_rows["净利润"] == 2 * _PDF_ROW_BASE + 4

    def test_read_pdf_skips_empty_rows_but_preserves_table_index(self, monkeypatch) -> None:
        """空行不产出数据行, 但后续行的表内行号保持真实位置。"""
        from fsa.core.importer import pdf_reader

        monkeypatch.setattr(pdf_reader, "pdfplumber", _FakePdfModule([_FakePage(_BS_TABLE)]))
        data = pdf_reader.read_pdf(str(THREE_REPORTS_PDF))
        bs = data["资产负债表"]
        items = [str(r.get("项目", "")) for r in bs.rows]
        assert items == ["货币资金", "应收账款", "资产总计", "负债合计", "所有者权益合计"]

        rows = {str(r.get("项目", "")): r["_row"] for r in bs.rows}
        assert rows["资产总计"] == 1 * _PDF_ROW_BASE + 6
        assert rows["负债合计"] == 1 * _PDF_ROW_BASE + 7

    def test_import_pdf_trace_rows_are_page_encoded(self, monkeypatch) -> None:
        """导入 PDF 并校验后, trace 行号为页码编码, 可解码为「第X页表内第N行」。"""
        from fsa.core.engine.registry import RuleRegistry
        from fsa.core.importer import pdf_reader
        from fsa.core.importer.importer import ImportService
        from fsa.services.validation_service import ValidationService

        monkeypatch.setattr(pdf_reader, "pdfplumber", _FakePdfModule([_FakePage(_BS_TABLE)]))

        rules_path = Path(__file__).parent.parent.parent / "cas_gouji_rule_library.json"
        registry = RuleRegistry.from_json(str(rules_path))
        service = ImportService()
        reports = service.import_file(str(THREE_REPORTS_PDF))
        validation = ValidationService(registry)
        summary = validation.validate(reports, period="2024-12")

        result = _find_result(summary.results, "BS-BAL-001")
        assert result is not None, "未找到 BS-BAL-001 结果"
        trace = {t.key: t for t in result.trace}
        assert trace["asset_total"].row == 1 * _PDF_ROW_BASE + 6
        assert trace["liability_total"].row == 1 * _PDF_ROW_BASE + 7
        assert trace["equity_total"].row == 1 * _PDF_ROW_BASE + 8
        # 解码语义: divmod 还原「页码, 表内行」
        assert divmod(trace["asset_total"].row, _PDF_ROW_BASE) == (1, 6)

    def test_import_pdf_fixture_bs_rows_are_page_encoded(self) -> None:
        """真实 PDF 夹具: 资产负债表各项行号编码为第 1 页表内行。"""
        from fsa.core.importer.importer import ImportService

        service = ImportService()
        reports = service.import_file(str(THREE_REPORTS_PDF))
        bs = _find_report(reports, ReportType.BALANCE_SHEET)
        assert bs.get_item("asset_total").row == 1 * _PDF_ROW_BASE + 17
        assert bs.get_item("liability_total").row == 1 * _PDF_ROW_BASE + 30
        assert bs.get_item("equity_total").row == 1 * _PDF_ROW_BASE + 36

    def test_import_pdf_fixture_page_2_row_encoding(self) -> None:
        """真实 PDF 夹具: 利润表在第 2 页, 净利润行号编码为第 2 页表内行。"""
        from fsa.core.importer.importer import ImportService

        service = ImportService()
        reports = service.import_file(str(THREE_REPORTS_PDF))
        is_report = _find_report(reports, ReportType.INCOME_STATEMENT)
        item = is_report.get_item("net_profit")
        assert item is not None
        assert divmod(item.row, _PDF_ROW_BASE) == (2, 20)


# ── 辅助函数 ──────────────────────────────────────────────

def _find_sheet(data: dict[str, RawSheetData], keyword: str) -> str:
    """在 data 中查找名称包含 keyword 的 sheet。"""
    for name in data:
        if keyword in name:
            return name
    raise KeyError(f"未找到包含「{keyword}」的 sheet, 可用: {list(data.keys())}")


def _find_report(reports: list, report_type: ReportType):
    """在 reports 中查找指定类型的 Report。"""
    for r in reports:
        if r.report_type == report_type:
            return r
    raise ValueError(f"未找到 {report_type.value}")


def _find_result(results: list, rule_id: str):
    """在 results 中查找指定 rule_id 的结果。"""
    for r in results:
        if r.rule_id == rule_id:
            return r
    return None
