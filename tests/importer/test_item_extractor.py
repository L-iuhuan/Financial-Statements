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


class TestRowSkipping:
    """测试非数据行的跳过逻辑。"""

    def test_category_row_with_full_colon_skipped(self) -> None:
        """以全角冒号：结尾的分类行被跳过。"""
        raw = RawSheetData(
            name="资产负债表",
            headers=["项目", "期末余额"],
            rows=[
                {"_row": 2, "项目": "流动资产：", "期末余额": None},
                {"_row": 3, "项目": "货币资金", "期末余额": 1000000.0},
                {"_row": 4, "项目": "流动资产合计", "期末余额": 1000000.0},
            ],
        )
        items = extract_items(raw, ReportType.BALANCE_SHEET)
        keys = {item.key for item in items}
        assert "monetary_funds" in keys
        assert "current_assets" in keys
        assert len(items) == 2

    def test_category_row_with_half_colon_skipped(self) -> None:
        """以半角冒号:结尾的分类行被跳过。"""
        raw = RawSheetData(
            name="资产负债表",
            headers=["项目", "期末余额"],
            rows=[
                {"_row": 2, "项目": "流动资产:", "期末余额": None},
                {"_row": 3, "项目": "资产总计", "期末余额": 2000000.0},
            ],
        )
        items = extract_items(raw, ReportType.BALANCE_SHEET)
        assert len(items) == 1
        assert items[0].key == "asset_total"

    def test_note_row_skipped(self) -> None:
        """以"注"开头的备注行被跳过。"""
        raw = RawSheetData(
            name="资产负债表",
            headers=["项目", "期末余额"],
            rows=[
                {"_row": 2, "项目": "资产总计", "期末余额": 2000000.0},
                {"_row": 3, "项目": "注: 以上数据未经审计", "期末余额": None},
            ],
        )
        items = extract_items(raw, ReportType.BALANCE_SHEET)
        assert len(items) == 1
        assert items[0].key == "asset_total"

    def test_empty_name_row_skipped(self) -> None:
        """空名称行被跳过。"""
        raw = RawSheetData(
            name="资产负债表",
            headers=["项目", "期末余额"],
            rows=[
                {"_row": 2, "项目": "资产总计", "期末余额": 2000000.0},
                {"_row": 3, "项目": "", "期末余额": 999.0},
                {"_row": 4, "项目": "负债合计", "期末余额": 1000000.0},
            ],
        )
        items = extract_items(raw, ReportType.BALANCE_SHEET)
        assert len(items) == 2

    def test_prefixed_section_header_skipped(self) -> None:
        """带数字前缀的分类行(如 一、经营活动...)被跳过。"""
        raw = RawSheetData(
            name="现金流量表",
            headers=["项目", "本期金额"],
            rows=[
                {"_row": 2, "项目": "一、经营活动产生的现金流量：", "本期金额": None},
                {"_row": 3, "项目": "销售商品、提供劳务收到的现金", "本期金额": 500000.0},
                {"_row": 4, "项目": "二、投资活动产生的现金流量：", "本期金额": None},
                {"_row": 5, "项目": "投资活动产生的现金流量净额", "本期金额": -200000.0},
            ],
        )
        items = extract_items(raw, ReportType.CASH_FLOW_STATEMENT)
        keys = {item.key for item in items}
        assert "cash_received_from_sales" in keys
        assert "investing_net" in keys
        assert len(items) == 2


class TestSupplementarySection:
    """测试现金流量表补充资料区域的提取（不再跳过，改为 cf_notes_ 前缀）。"""

    def test_supplementary_items_extracted_with_cf_notes_prefix(self) -> None:
        """补充资料中的项目提取为 cf_notes_ 前缀的 key。"""
        raw = RawSheetData(
            name="现金流量表",
            headers=["项目", "本期金额"],
            rows=[
                {"_row": 2, "项目": "经营活动产生的现金流量净额", "本期金额": 500000.0},
                {"_row": 3, "项目": "期末现金及现金等价物余额", "本期金额": 2000000.0},
                {"_row": 4, "项目": "补充资料：", "本期金额": None},
                {"_row": 5, "项目": "净利润", "本期金额": 705000.0},
                {"_row": 6, "项目": "固定资产折旧", "本期金额": 200000.0},
                {"_row": 7, "项目": "经营活动产生的现金流量净额", "本期金额": 830000.0},
            ],
        )
        items = extract_items(raw, ReportType.CASH_FLOW_STATEMENT)
        keys = {item.key for item in items}
        # 主表项目保留原始 key
        assert "operating_net" in keys
        assert "ending_cash_equiv" in keys
        # 补充资料中的项目使用 cf_notes_ 前缀
        assert "cf_notes_net_profit" in keys
        assert "cf_notes_depreciation" in keys
        assert "cf_notes_operating_net" in keys
        # 主表 operating_net 取第一个出现的值
        operating_items = [i for i in items if i.key == "operating_net"]
        assert len(operating_items) == 1
        assert operating_items[0].amount == 500000.0

    def test_unknown_supplementary_item_skipped(self) -> None:
        """不在补充资料映射表中的项目在补充资料区被跳过。"""
        raw = RawSheetData(
            name="现金流量表",
            headers=["项目", "本期金额"],
            rows=[
                {"_row": 2, "项目": "补充资料：", "本期金额": None},
                {"_row": 3, "项目": "某个不在映射表中的科目", "本期金额": 999.0},
                {"_row": 4, "项目": "净利润", "本期金额": 705000.0},
            ],
        )
        items = extract_items(raw, ReportType.CASH_FLOW_STATEMENT)
        keys = {item.key for item in items}
        assert "cf_notes_net_profit" in keys
        # 不在映射表中的被跳过
        assert len(items) == 1

    def test_no_supplementary_section_normal_extraction(self) -> None:
        """无补充资料时正常提取所有项目。"""
        raw = RawSheetData(
            name="现金流量表",
            headers=["项目", "本期金额"],
            rows=[
                {"_row": 2, "项目": "经营活动产生的现金流量净额", "本期金额": 500000.0},
                {"_row": 3, "项目": "投资活动产生的现金流量净额", "本期金额": -200000.0},
            ],
        )
        items = extract_items(raw, ReportType.CASH_FLOW_STATEMENT)
        assert len(items) == 2

    def test_supplementary_category_row_skipped(self) -> None:
        """补充资料中的分类行（以:或无映射）被跳过。"""
        raw = RawSheetData(
            name="现金流量表",
            headers=["项目", "本期金额"],
            rows=[
                {"_row": 2, "项目": "补充资料：", "本期金额": None},
                {"_row": 3, "项目": "1.将净利润调节为经营活动现金流量：", "本期金额": None},
                {"_row": 4, "项目": "净利润", "本期金额": 705000.0},
            ],
        )
        items = extract_items(raw, ReportType.CASH_FLOW_STATEMENT)
        keys = {item.key for item in items}
        assert "cf_notes_net_profit" in keys


class TestDualColumnBalanceSheet:
    """测试资产负债表的左右双栏布局（资产 | 负债和所有者权益）。"""

    def test_extracts_right_side_liability_and_equity(self) -> None:
        """右栏的负债/权益项目同样被提取（列名带去重后缀）。"""
        raw = RawSheetData(
            name="资产负债表",
            headers=[
                "资   产", "行次", "期末余额", "年初余额",
                "负债和所有者权益", "行次#2", "期末余额#2", "年初余额#2",
            ],
            rows=[
                {
                    "_row": 2,
                    "资   产": "货币资金",
                    "行次": 38,
                    "期末余额": 100000.0,
                    "年初余额": 80000.0,
                    "负债和所有者权益": "负债合计",
                    "行次#2": 69,
                    "期末余额#2": 1000000.0,
                    "年初余额#2": 900000.0,
                },
                {
                    "_row": 3,
                    "资   产": "资产总计",
                    "行次": 38,
                    "期末余额": 2000000.0,
                    "年初余额": 1850000.0,
                    "负债和所有者权益": "所有者权益合计",
                    "行次#2": 82,
                    "期末余额#2": 1000000.0,
                    "年初余额#2": 950000.0,
                },
            ],
        )

        items = extract_items(raw, ReportType.BALANCE_SHEET)
        keys = {item.key for item in items}
        assert "monetary_funds" in keys
        assert "asset_total" in keys
        assert "liability_total" in keys
        assert "equity_total" in keys
        amounts = {item.key: item.amount for item in items}
        assert amounts["asset_total"] == 2000000.0
        assert amounts["liability_total"] == 1000000.0
        assert amounts["equity_total"] == 1000000.0

    def test_right_side_without_left_name_skipped(self) -> None:
        """右侧没有项目名时不产生项目。"""
        raw = RawSheetData(
            name="资产负债表",
            headers=["项目", "期末余额", "负债和所有者权益", "期末余额#2"],
            rows=[
                {"_row": 2, "项目": "资产总计", "期末余额": 2000000.0,
                 "负债和所有者权益": None, "期末余额#2": 999.0},
            ],
        )
        items = extract_items(raw, ReportType.BALANCE_SHEET)
        keys = {item.key for item in items}
        assert keys == {"asset_total"}


class TestCustomPeriodColumns:
    """测试自定义期间列（日期序列号 / 2026年1-6月 / 2025年1-12月）。"""

    def test_income_statement_ytd_column_selected(self) -> None:
        """本年累计列被识别为主金额列，上年全年列被识别为次金额列。"""
        raw = RawSheetData(
            name="利润表",
            headers=["项       目", "行次", "46174", "2026年1-6月", "2025年1-12月"],
            rows=[
                {
                    "_row": 2,
                    "项       目": "营业收入",
                    "行次": 1,
                    "46174": 100000.0,
                    "2026年1-6月": 600000.0,
                    "2025年1-12月": 500000.0,
                },
            ],
        )
        items = extract_items(raw, ReportType.INCOME_STATEMENT)
        assert len(items) == 1
        assert items[0].key == "revenue"
        assert items[0].amount == 600000.0
        assert items[0].column == "2026年1-6月"
        assert items[0].beginning_amount == 500000.0

    def test_suffix_in_item_name_is_normalized(self) -> None:
        """带括号注释的项目名仍能映射到标准 key。"""
        raw = RawSheetData(
            name="利润表",
            headers=["项目", "本期金额"],
            rows=[
                {"_row": 2, "项目": "四、净利润（净亏损以“-”号填列）", "本期金额": 405000.0},
            ],
        )
        items = extract_items(raw, ReportType.INCOME_STATEMENT)
        assert len(items) == 1
        assert items[0].key == "net_profit"

    def test_numeric_fallback_when_no_known_headers(self) -> None:
        """无已知列名时按数值内容回退选择金额列。"""
        raw = RawSheetData(
            name="利润表",
            headers=["项目", "本月", "累计"],
            rows=[
                {"_row": 2, "项目": "营业收入", "本月": 100.0, "累计": 600.0},
                {"_row": 3, "项目": "营业成本", "本月": 40.0, "累计": 240.0},
                {"_row": 4, "项目": "净利润", "本月": 60.0, "累计": 360.0},
            ],
        )
        items = extract_items(raw, ReportType.INCOME_STATEMENT)
        amounts = {item.key: item.amount for item in items}
        beginnings = {item.key: item.beginning_amount for item in items}
        assert len(items) == 3
        assert amounts["revenue"] == 100.0
        assert amounts["operating_cost"] == 40.0
        assert amounts["net_profit"] == 60.0
        assert beginnings["revenue"] == 600.0
        assert beginnings["net_profit"] == 360.0


class TestPrefixStrippedExtraction:
    """测试带前缀的科目名被正确提取。"""

    def test_is_items_with_chinese_num_prefix_extracted(self) -> None:
        """利润表中带 一、二、等前缀的科目名被正确提取。"""
        raw = RawSheetData(
            name="利润表",
            headers=["项目", "本期金额"],
            rows=[
                {"_row": 2, "项目": "一、营业收入", "本期金额": 5000000.0},
                {"_row": 3, "项目": "减：营业成本", "本期金额": 3000000.0},
                {"_row": 4, "项目": "二、营业利润", "本期金额": 920000.0},
                {"_row": 5, "项目": "三、利润总额", "本期金额": 940000.0},
                {"_row": 6, "项目": "四、净利润", "本期金额": 705000.0},
            ],
        )
        items = extract_items(raw, ReportType.INCOME_STATEMENT)
        key_to_amount = {item.key: item.amount for item in items}
        assert key_to_amount["revenue"] == 5000000.0
        assert key_to_amount["operating_cost"] == 3000000.0
        assert key_to_amount["operating_profit"] == 920000.0
        assert key_to_amount["total_profit"] == 940000.0
        assert key_to_amount["net_profit"] == 705000.0

    def test_bs_items_with_alias_extracted(self) -> None:
        """资产负债表中别名科目名被正确提取。"""
        raw = RawSheetData(
            name="资产负债表",
            headers=["项目", "期末余额"],
            rows=[
                {"_row": 2, "项目": "  现金及银行存款", "期末余额": 2000000.0},
                {"_row": 3, "项目": "  应收账款净额", "期末余额": 800000.0},
                {"_row": 4, "项目": "  预付账款", "期末余额": 200000.0},
                {"_row": 5, "项目": "  股本", "期末余额": 3000000.0},
            ],
        )
        items = extract_items(raw, ReportType.BALANCE_SHEET)
        key_to_amount = {item.key: item.amount for item in items}
        assert key_to_amount["monetary_funds"] == 2000000.0
        assert key_to_amount["accounts_receivable"] == 800000.0
        assert key_to_amount["prepayments"] == 200000.0
        assert key_to_amount["paid_in_capital"] == 3000000.0


class TestColumnNameVariants:
    """测试不同金额列名变体。"""

    def test_bs_期末数_column_found(self) -> None:
        """资产负债表使用"期末数"列名。"""
        raw = RawSheetData(
            name="资产负债表",
            headers=["项目", "行次", "期末数", "年初数"],
            rows=[
                {"_row": 2, "项目": "资产总计", "行次": 20, "期末数": 2000000.0, "年初数": 1850000.0},
            ],
        )
        items = extract_items(raw, ReportType.BALANCE_SHEET)
        assert len(items) == 1
        assert items[0].amount == 2000000.0
        assert items[0].column == "期末数"

    def test_is_本期数_column_found(self) -> None:
        """利润表使用"本期数"列名。"""
        raw = RawSheetData(
            name="利润表",
            headers=["项目", "行次", "本期数", "上期数"],
            rows=[
                {"_row": 2, "项目": "营业收入", "行次": 1, "本期数": 5000000.0, "上期数": 4500000.0},
            ],
        )
        items = extract_items(raw, ReportType.INCOME_STATEMENT)
        assert len(items) == 1
        assert items[0].amount == 5000000.0
        assert items[0].column == "本期数"


class TestNameColumnFallback:
    """测试项目名称列查找的容错。"""

    def test_name_column_项目名称_found(self) -> None:
        """表头为"项目名称"时能正确识别。"""
        raw = RawSheetData(
            name="资产负债表",
            headers=["项目名称", "行次", "期末余额"],
            rows=[
                {"_row": 2, "项目名称": "资产总计", "行次": 20, "期末余额": 2000000.0},
            ],
        )
        items = extract_items(raw, ReportType.BALANCE_SHEET)
        assert len(items) == 1
        assert items[0].key == "asset_total"

    def test_name_column_科目_found(self) -> None:
        """表头为"科目"时能正确识别。"""
        raw = RawSheetData(
            name="资产负债表",
            headers=["科目", "期末余额"],
            rows=[
                {"_row": 2, "科目": "资产总计", "期末余额": 2000000.0},
            ],
        )
        items = extract_items(raw, ReportType.BALANCE_SHEET)
        assert len(items) == 1
        assert items[0].key == "asset_total"

    def test_name_column_fallback_first_column(self) -> None:
        """无已知列名时回退到第一列作为名称列。"""
        raw = RawSheetData(
            name="资产负债表",
            headers=["报表项目", "期末余额"],
            rows=[
                {"_row": 2, "报表项目": "资产总计", "期末余额": 2000000.0},
            ],
        )
        items = extract_items(raw, ReportType.BALANCE_SHEET)
        assert len(items) == 1
        assert items[0].key == "asset_total"
        assert items[0].amount == 2000000.0


class TestDualColumnExtraction:
    """测试双金额列提取（期末/期初 或 本期/上期）。"""

    def test_bs_extracts_both_ending_and_beginning(self) -> None:
        """资产负债表同时提取期末余额和年初余额。"""
        raw = RawSheetData(
            name="资产负债表",
            headers=["项目", "期末余额", "年初余额"],
            rows=[
                {"_row": 2, "项目": "资产总计", "期末余额": 2000000.0, "年初余额": 1850000.0},
            ],
        )
        items = extract_items(raw, ReportType.BALANCE_SHEET)
        assert len(items) == 1
        assert items[0].amount == 2000000.0
        assert items[0].beginning_amount == 1850000.0

    def test_bs_beginning_amount_none_when_column_missing(self) -> None:
        """资产负债表无年初余额列时 beginning_amount 为 None。"""
        raw = RawSheetData(
            name="资产负债表",
            headers=["项目", "期末余额"],
            rows=[
                {"_row": 2, "项目": "资产总计", "期末余额": 2000000.0},
            ],
        )
        items = extract_items(raw, ReportType.BALANCE_SHEET)
        assert items[0].beginning_amount is None

    def test_bs_beginning_amount_none_when_cell_empty(self) -> None:
        """年初余额列为空时 beginning_amount 为 None。"""
        raw = RawSheetData(
            name="资产负债表",
            headers=["项目", "期末余额", "年初余额"],
            rows=[
                {"_row": 2, "项目": "资产总计", "期末余额": 2000000.0, "年初余额": None},
            ],
        )
        items = extract_items(raw, ReportType.BALANCE_SHEET)
        assert items[0].beginning_amount is None

    def test_bs_beginning_amount_negative_ok(self) -> None:
        """年初余额为负数正常。"""
        raw = RawSheetData(
            name="资产负债表",
            headers=["项目", "期末余额", "年初余额"],
            rows=[
                {"_row": 2, "项目": "未分配利润", "期末余额": 500000.0, "年初余额": -100000.0},
            ],
        )
        items = extract_items(raw, ReportType.BALANCE_SHEET)
        assert items[0].key == "undistributed_profit"
        assert items[0].beginning_amount == -100000.0

    def test_bs_beginning_amount_zero_ok(self) -> None:
        """年初余额为 0 正常。"""
        raw = RawSheetData(
            name="资产负债表",
            headers=["项目", "期末余额", "年初余额"],
            rows=[
                {"_row": 2, "项目": "库存股", "期末余额": 0.0, "年初余额": 0.0},
            ],
        )
        items = extract_items(raw, ReportType.BALANCE_SHEET)
        assert items[0].beginning_amount == 0.0

    def test_is_extracts_both_current_and_prior_period(self) -> None:
        """利润表同时提取本期金额和上期金额。"""
        raw = RawSheetData(
            name="利润表",
            headers=["项目", "本期金额", "上期金额"],
            rows=[
                {"_row": 2, "项目": "营业收入", "本期金额": 3000000.0, "上期金额": 2800000.0},
            ],
        )
        items = extract_items(raw, ReportType.INCOME_STATEMENT)
        assert items[0].amount == 3000000.0
        assert items[0].beginning_amount == 2800000.0

    def test_cf_extracts_both_current_and_prior_period(self) -> None:
        """现金流量表同时提取本期金额和上期金额。"""
        raw = RawSheetData(
            name="现金流量表",
            headers=["项目", "本期金额", "上期金额"],
            rows=[
                {"_row": 2, "项目": "经营活动产生的现金流量净额",
                 "本期金额": 500000.0, "上期金额": 450000.0},
            ],
        )
        items = extract_items(raw, ReportType.CASH_FLOW_STATEMENT)
        assert items[0].amount == 500000.0
        assert items[0].beginning_amount == 450000.0

    def test_bs_alternate_column_names_初_num(self) -> None:
        """资产负债表使用"期末数"和"年初数"列名。"""
        raw = RawSheetData(
            name="资产负债表",
            headers=["项目", "期末数", "年初数"],
            rows=[
                {"_row": 2, "项目": "资产总计", "期末数": 2000000.0, "年初数": 1850000.0},
            ],
        )
        items = extract_items(raw, ReportType.BALANCE_SHEET)
        assert items[0].amount == 2000000.0
        assert items[0].column == "期末数"
        assert items[0].beginning_amount == 1850000.0

    def test_supplementary_items_also_get_beginning_amount(self) -> None:
        """补充资料中的项目也提取期初金额。"""
        raw = RawSheetData(
            name="现金流量表",
            headers=["项目", "本期金额", "上期金额"],
            rows=[
                {"_row": 2, "项目": "补充资料：", "本期金额": None, "上期金额": None},
                {"_row": 3, "项目": "净利润", "本期金额": 705000.0, "上期金额": 650000.0},
            ],
        )
        items = extract_items(raw, ReportType.CASH_FLOW_STATEMENT)
        cf_notes = [i for i in items if i.key == "cf_notes_net_profit"]
        assert len(cf_notes) == 1
        assert cf_notes[0].amount == 705000.0
        assert cf_notes[0].beginning_amount == 650000.0
