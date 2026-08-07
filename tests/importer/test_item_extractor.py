"""item_extractor 模块测试: 从 RawSheetData 提取 ReportItem 对象。

测试内容: 正常提取、金额列选择、缺失项处理、零值、负值、未映射项。
"""

from __future__ import annotations

from fsa.core.models.report import ReportItem, ReportType
from fsa.core.importer.excel_reader import RawSheetData
from fsa.core.importer.item_extractor import extract_items


class TestExtractBalanceSheetItems:
    """测试资产负债表项目提取。"""

    def test_extract_asset_total_from_ending_balance(self) -> None:
        raw = RawSheetData(
            name="资产负债表",
            headers=["项目", "行次", "期末余额", "年初余额"],
            rows=[
                {"_row": 2, "项目": "资产总计", "行次": 20, "期末余额": 2000000.00, "年初余额": 1850000.00},
            ],
        )
        items = extract_items(raw, ReportType.BALANCE_SHEET)

        assert len(items) == 1
        item = items[0]
        assert item.key == "asset_total"
        assert item.name == "资产总计"
        assert item.amount == 2000000.00
        assert item.row == 2
        assert item.column == "期末余额"

    def test_extract_multiple_items_from_balance_sheet(self) -> None:
        raw = RawSheetData(
            name="资产负债表",
            headers=["项目", "期末余额", "年初余额"],
            rows=[
                {"_row": 2, "项目": "流动资产合计", "期末余额": 500000.00, "年初余额": 450000.00},
                {"_row": 3, "项目": "非流动资产合计", "期末余额": 1500000.00, "年初余额": 1400000.00},
                {"_row": 4, "项目": "资产总计", "期末余额": 2000000.00, "年初余额": 1850000.00},
                {"_row": 5, "项目": "负债合计", "期末余额": 1000000.00, "年初余额": 900000.00},
                {"_row": 6, "项目": "所有者权益合计", "期末余额": 1000000.00, "年初余额": 950000.00},
            ],
        )
        items = extract_items(raw, ReportType.BALANCE_SHEET)

        assert len(items) == 5
        keys = {item.key for item in items}
        assert "current_assets" in keys
        assert "non_current_assets" in keys
        assert "asset_total" in keys
        assert "liability_total" in keys
        assert "equity_total" in keys

    def test_extract_with_zero_amount(self) -> None:
        raw = RawSheetData(
            name="资产负债表",
            headers=["项目", "期末余额"],
            rows=[
                {"_row": 2, "项目": "库存股", "期末余额": 0.0},
            ],
        )
        items = extract_items(raw, ReportType.BALANCE_SHEET)

        assert len(items) == 1
        assert items[0].key == "treasury_stock"
        assert items[0].amount == 0.0

    def test_extract_with_negative_amount(self) -> None:
        raw = RawSheetData(
            name="资产负债表",
            headers=["项目", "期末余额"],
            rows=[
                {"_row": 2, "项目": "库存股", "期末余额": -50000.0},
            ],
        )
        items = extract_items(raw, ReportType.BALANCE_SHEET)

        assert len(items) == 1
        assert items[0].amount == -50000.0

    def test_extract_with_large_number(self) -> None:
        big_number = 1e15
        raw = RawSheetData(
            name="资产负债表",
            headers=["项目", "期末余额"],
            rows=[
                {"_row": 2, "项目": "资产总计", "期末余额": big_number},
            ],
        )
        items = extract_items(raw, ReportType.BALANCE_SHEET)

        assert items[0].amount == big_number


class TestExtractIncomeStatementItems:
    """测试利润表项目提取。"""

    def test_extract_uses_current_period_amount(self) -> None:
        raw = RawSheetData(
            name="利润表",
            headers=["项目", "本期金额", "上期金额"],
            rows=[
                {"_row": 2, "项目": "营业收入", "本期金额": 3000000.00, "上期金额": 2800000.00},
            ],
        )
        items = extract_items(raw, ReportType.INCOME_STATEMENT)

        assert len(items) == 1
        item = items[0]
        assert item.key == "revenue"
        assert item.amount == 3000000.00
        assert item.column == "本期金额"

    def test_extract_net_profit_from_income_statement(self) -> None:
        raw = RawSheetData(
            name="利润表",
            headers=["项目", "本期金额", "上期金额"],
            rows=[
                {"_row": 2, "项目": "营业利润", "本期金额": 545000.00, "上期金额": 484000.00},
                {"_row": 3, "项目": "利润总额", "本期金额": 540000.00, "上期金额": 479000.00},
                {"_row": 4, "项目": "净利润", "本期金额": 405000.00, "上期金额": 359250.00},
            ],
        )
        items = extract_items(raw, ReportType.INCOME_STATEMENT)

        keys = {item.key for item in items}
        assert "operating_profit" in keys
        assert "total_profit" in keys
        assert "net_profit" in keys

    def test_extract_detailed_income_statement_items(self) -> None:
        raw = RawSheetData(
            name="利润表",
            headers=["项目", "本期金额"],
            rows=[
                {"_row": 2, "项目": "税金及附加", "本期金额": 50000.00},
                {"_row": 3, "项目": "销售费用", "本期金额": 200000.00},
                {"_row": 4, "项目": "管理费用", "本期金额": 150000.00},
                {"_row": 5, "项目": "研发费用", "本期金额": 80000.00},
                {"_row": 6, "项目": "财务费用", "本期金额": 30000.00},
                {"_row": 7, "项目": "投资收益", "本期金额": 50000.00},
            ],
        )
        items = extract_items(raw, ReportType.INCOME_STATEMENT)

        keys = {item.key for item in items}
        assert "taxes_surcharges" in keys
        assert "selling_exp" in keys
        assert "admin_exp" in keys
        assert "rnd_exp" in keys
        assert "finance_exp" in keys
        assert "investment_income" in keys


class TestExtractCashFlowItems:
    """测试现金流量表项目提取。"""

    def test_extract_operating_net_from_cash_flow(self) -> None:
        raw = RawSheetData(
            name="现金流量表",
            headers=["项目", "本期金额", "上期金额"],
            rows=[
                {"_row": 2, "项目": "经营活动产生的现金流量净额", "本期金额": 500000.00, "上期金额": 450000.00},
            ],
        )
        items = extract_items(raw, ReportType.CASH_FLOW_STATEMENT)

        assert len(items) == 1
        assert items[0].key == "operating_net"
        assert items[0].amount == 500000.00

    def test_extract_all_cash_flow_activities(self) -> None:
        raw = RawSheetData(
            name="现金流量表",
            headers=["项目", "本期金额", "上期金额"],
            rows=[
                {"_row": 2, "项目": "经营活动产生的现金流量净额", "本期金额": 500000.00, "上期金额": 450000.00},
                {"_row": 3, "项目": "投资活动产生的现金流量净额", "本期金额": -200000.00, "上期金额": -150000.00},
                {"_row": 4, "项目": "筹资活动产生的现金流量净额", "本期金额": -100000.00, "上期金额": -80000.00},
                {"_row": 5, "项目": "现金及现金等价物净增加额", "本期金额": 205000.00, "上期金额": 223000.00},
            ],
        )
        items = extract_items(raw, ReportType.CASH_FLOW_STATEMENT)

        keys = {item.key for item in items}
        assert "operating_net" in keys
        assert "investing_net" in keys
        assert "financing_net" in keys
        assert "net_increase_cash" in keys


class TestMissingAndUnmappedItems:
    """测试缺失项和未映射项处理。"""

    def test_unmapped_item_is_skipped(self) -> None:
        raw = RawSheetData(
            name="资产负债表",
            headers=["项目", "期末余额"],
            rows=[
                {"_row": 2, "项目": "这是一个不存在的科目", "期末余额": 999.99},
            ],
        )
        items = extract_items(raw, ReportType.BALANCE_SHEET)
        assert len(items) == 0

    def test_row_with_none_amount_is_skipped(self) -> None:
        raw = RawSheetData(
            name="资产负债表",
            headers=["项目", "期末余额"],
            rows=[
                {"_row": 2, "项目": "资产总计", "期末余额": None},
            ],
        )
        items = extract_items(raw, ReportType.BALANCE_SHEET)
        assert len(items) == 0

    def test_row_without_item_name_is_skipped(self) -> None:
        raw = RawSheetData(
            name="资产负债表",
            headers=["项目", "期末余额"],
            rows=[
                {"_row": 2, "项目": None, "期末余额": 100.0},
            ],
        )
        items = extract_items(raw, ReportType.BALANCE_SHEET)
        assert len(items) == 0

    def test_empty_sheet_returns_empty_list(self) -> None:
        raw = RawSheetData(
            name="资产负债表",
            headers=["项目", "期末余额"],
            rows=[],
        )
        items = extract_items(raw, ReportType.BALANCE_SHEET)
        assert len(items) == 0

    def test_mixed_known_and_unknown_items(self) -> None:
        raw = RawSheetData(
            name="资产负债表",
            headers=["项目", "期末余额"],
            rows=[
                {"_row": 2, "项目": "资产总计", "期末余额": 2000000.00},
                {"_row": 3, "项目": "未知科目", "期末余额": 100.00},
                {"_row": 4, "项目": "负债合计", "期末余额": 1000000.00},
            ],
        )
        items = extract_items(raw, ReportType.BALANCE_SHEET)
        assert len(items) == 2
        keys = {item.key for item in items}
        assert "asset_total" in keys
        assert "liability_total" in keys


class TestDuplicateItems:
    """测试重复项目处理。"""

    def test_duplicate_item_name_uses_first(self) -> None:
        raw = RawSheetData(
            name="资产负债表",
            headers=["项目", "期末余额"],
            rows=[
                {"_row": 2, "项目": "资产总计", "期末余额": 2000000.00},
                {"_row": 3, "项目": "资产总计", "期末余额": 3000000.00},
            ],
        )
        items = extract_items(raw, ReportType.BALANCE_SHEET)
        assert len(items) == 1
        assert items[0].amount == 2000000.00
        assert items[0].row == 2


class TestFloatPrecision:
    """测试浮点精度处理。"""

    def test_extract_float_precision_value(self) -> None:
        raw = RawSheetData(
            name="资产负债表",
            headers=["项目", "期末余额"],
            rows=[
                {"_row": 2, "项目": "资产总计", "期末余额": 1.123456789},
            ],
        )
        items = extract_items(raw, ReportType.BALANCE_SHEET)
        assert items[0].amount == 1.123456789


class TestRowTraceability:
    """测试行号追溯。"""

    def test_items_have_correct_row_numbers(self) -> None:
        raw = RawSheetData(
            name="资产负债表",
            headers=["项目", "期末余额"],
            rows=[
                {"_row": 5, "项目": "流动资产合计", "期末余额": 500000.00},
                {"_row": 10, "项目": "非流动资产合计", "期末余额": 1500000.00},
                {"_row": 20, "项目": "资产总计", "期末余额": 2000000.00},
            ],
        )
        items = extract_items(raw, ReportType.BALANCE_SHEET)

        row_map = {item.key: item.row for item in items}
        assert row_map["current_assets"] == 5
        assert row_map["non_current_assets"] == 10
        assert row_map["asset_total"] == 20

    def test_items_have_correct_column_name(self) -> None:
        raw = RawSheetData(
            name="资产负债表",
            headers=["项目", "期末余额", "年初余额"],
            rows=[
                {"_row": 2, "项目": "资产总计", "期末余额": 2000000.00, "年初余额": 1850000.00},
            ],
        )
        items = extract_items(raw, ReportType.BALANCE_SHEET)
        assert items[0].column == "期末余额"