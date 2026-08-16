"""name_mapper 模块测试: 中文科目名到 snake_case key 的映射。

测试内容: 正向映射、反向查找、缺失处理、完整变量覆盖。
"""

from __future__ import annotations

import pytest

from fsa.core.importer.name_mapper import (
    KEY_TO_NAME,
    NAME_TO_KEY,
    get_key,
    get_name,
    get_supplementary_key,
    is_known,
)


class TestNameToKeyMapping:
    """测试中文名称 -> 英文 key 的正向映射。"""

    def test_map_asset_total_returns_asset_total(self) -> None:
        assert NAME_TO_KEY["资产总计"] == "asset_total"

    def test_map_liability_total_returns_liability_total(self) -> None:
        assert NAME_TO_KEY["负债合计"] == "liability_total"

    def test_map_equity_total_returns_equity_total(self) -> None:
        assert NAME_TO_KEY["所有者权益合计"] == "equity_total"

    def test_map_current_assets_returns_current_assets(self) -> None:
        assert NAME_TO_KEY["流动资产合计"] == "current_assets"

    def test_map_non_current_assets_returns_non_current_assets(self) -> None:
        assert NAME_TO_KEY["非流动资产合计"] == "non_current_assets"

    def test_map_current_liabilities_returns_current_liabilities(self) -> None:
        assert NAME_TO_KEY["流动负债合计"] == "current_liabilities"

    def test_map_non_current_liabilities_returns_non_current_liabilities(self) -> None:
        assert NAME_TO_KEY["非流动负债合计"] == "non_current_liabilities"

    def test_map_monetary_funds_returns_monetary_funds(self) -> None:
        assert NAME_TO_KEY["货币资金"] == "monetary_funds"

    def test_map_revenue_returns_revenue(self) -> None:
        assert NAME_TO_KEY["营业收入"] == "revenue"

    def test_map_operating_cost_returns_operating_cost(self) -> None:
        assert NAME_TO_KEY["营业成本"] == "operating_cost"

    def test_map_operating_profit_returns_operating_profit(self) -> None:
        assert NAME_TO_KEY["营业利润"] == "operating_profit"

    def test_map_net_profit_returns_net_profit(self) -> None:
        assert NAME_TO_KEY["净利润"] == "net_profit"

    def test_map_total_profit_returns_total_profit(self) -> None:
        assert NAME_TO_KEY["利润总额"] == "total_profit"

    def test_map_income_tax_expense_returns_income_tax_expense(self) -> None:
        assert NAME_TO_KEY["所得税费用"] == "income_tax_expense"

    def test_map_paid_in_capital_returns_paid_in_capital(self) -> None:
        assert NAME_TO_KEY["实收资本"] == "paid_in_capital"

    def test_map_capital_reserve_returns_capital_reserve(self) -> None:
        assert NAME_TO_KEY["资本公积"] == "capital_reserve"

    def test_map_surplus_reserve_returns_surplus_reserve(self) -> None:
        assert NAME_TO_KEY["盈余公积"] == "surplus_reserve"

    def test_map_undistributed_profit_returns_undistributed_profit(self) -> None:
        assert NAME_TO_KEY["未分配利润"] == "undistributed_profit"

    def test_map_treasury_stock_returns_treasury_stock(self) -> None:
        assert NAME_TO_KEY["库存股"] == "treasury_stock"

    def test_map_other_comprehensive_income_returns_other_comprehensive_income(
        self,
    ) -> None:
        assert NAME_TO_KEY["其他综合收益"] == "other_comprehensive_income"

    def test_map_operating_net_returns_operating_net(self) -> None:
        assert NAME_TO_KEY["经营活动产生的现金流量净额"] == "operating_net"

    def test_map_investing_net_returns_investing_net(self) -> None:
        assert NAME_TO_KEY["投资活动产生的现金流量净额"] == "investing_net"

    def test_map_financing_net_returns_financing_net(self) -> None:
        assert NAME_TO_KEY["筹资活动产生的现金流量净额"] == "financing_net"

    def test_map_net_increase_cash_returns_net_increase_cash(self) -> None:
        assert NAME_TO_KEY["现金及现金等价物净增加额"] == "net_increase_cash"


class TestGetKey:
    """测试 get_key 辅助函数（带默认值）。"""

    def test_get_key_known_name_returns_key(self) -> None:
        assert get_key("资产总计") == "asset_total"

    def test_get_key_unknown_name_returns_none(self) -> None:
        assert get_key("不存在的科目") is None

    def test_get_key_unknown_name_with_default_returns_default(self) -> None:
        assert get_key("不存在的科目", "fallback") == "fallback"


class TestGetName:
    """测试 get_name 反向查找函数。"""

    def test_get_name_known_key_returns_chinese_name(self) -> None:
        assert get_name("asset_total") == "资产总计"

    def test_get_name_unknown_key_returns_none(self) -> None:
        assert get_name("unknown_key") is None

    def test_get_name_unknown_key_with_default_returns_default(self) -> None:
        assert get_name("unknown_key", "未知科目") == "未知科目"


class TestIsKnown:
    """测试 is_known 函数。"""

    def test_is_known_known_name_returns_true(self) -> None:
        assert is_known("资产总计") is True

    def test_is_known_unknown_name_returns_false(self) -> None:
        assert is_known("不存在的科目") is False

    def test_is_known_empty_string_returns_false(self) -> None:
        assert is_known("") is False


class TestKeyToName:
    """测试英文 key -> 中文名称的反向映射。"""

    def test_reverse_mapping_asset_total(self) -> None:
        assert KEY_TO_NAME["asset_total"] == "资产总计"

    def test_reverse_mapping_liability_total(self) -> None:
        assert KEY_TO_NAME["liability_total"] == "负债合计"

    def test_reverse_mapping_equity_total(self) -> None:
        assert KEY_TO_NAME["equity_total"] == "所有者权益合计"


class TestCompleteCoverage:
    """测试所有规则库公式中的变量都有映射。"""

    def test_all_balance_sheet_variables_mapped(self) -> None:
        bs_vars = [
            "asset_total",
            "liability_total",
            "equity_total",
            "current_assets",
            "non_current_assets",
            "current_liabilities",
            "non_current_liabilities",
            "paid_in_capital",
            "capital_reserve",
            "other_comprehensive_income",
            "surplus_reserve",
            "undistributed_profit",
            "treasury_stock",
            "monetary_funds",
            "accounts_receivable",
            "accounts_payable",
            "other_receivable",
            "other_payable",
            "advance_from_customers",
            "prepayments",
            "construction_in_progress",
            "minority_interest",
            "parent_equity",
        ]
        for key in bs_vars:
            assert key in KEY_TO_NAME, f"缺少 key 映射: {key}"

    def test_all_income_statement_variables_mapped(self) -> None:
        is_vars = [
            "revenue",
            "operating_cost",
            "operating_profit",
            "net_profit",
            "total_profit",
            "taxes_surcharges",
            "selling_exp",
            "admin_exp",
            "rnd_exp",
            "finance_exp",
            "asset_impairment",
            "credit_impairment",
            "other_income",
            "investment_income",
            "fair_value_change",
            "asset_disposal_gain",
            "non_operating_income",
            "non_operating_expense",
            "income_tax_expense",
            "primary_revenue",
            "other_revenue",
            "total_comprehensive_income",
            "other_comprehensive_income_after_tax",
            "non_recurring_net_profit",
        ]
        for key in is_vars:
            assert key in KEY_TO_NAME, f"缺少 key 映射: {key}"

    def test_all_cash_flow_variables_mapped(self) -> None:
        cf_vars = [
            "net_increase_cash",
            "operating_net",
            "investing_net",
            "financing_net",
            "fx_effect",
            "cash_received_from_sales",
        ]
        for key in cf_vars:
            assert key in KEY_TO_NAME, f"缺少 key 映射: {key}"

    def test_aliases_map_to_same_key(self) -> None:
        """别名映射到与标准名相同的 key。"""
        alias_pairs = [
            ("现金及银行存款", "货币资金", "monetary_funds"),
            ("应收账款净额", "应收账款", "accounts_receivable"),
            ("预付账款", "预付款项", "prepayments"),
            ("预收账款", "预收款项", "advance_from_customers"),
            ("固定资产净值", "固定资产", "fixed_assets"),
            ("股本", "实收资本", "paid_in_capital"),
        ]
        for alias, standard, expected_key in alias_pairs:
            assert get_key(alias) == expected_key, f"别名「{alias}」未映射到 {expected_key}"
            assert get_key(standard) == expected_key, f"标准名「{standard}」未映射到 {expected_key}"

    def test_mapping_dict_is_immutable(self) -> None:
        """确保映射字典不可变。"""
        with pytest.raises(TypeError):
            NAME_TO_KEY["新科目"] = "new_key"  # type: ignore[index]


class TestPrefixStripping:
    """测试前缀清洗: 一、/减：/加：等前缀自动剥离。"""

    def test_chinese_num_prefix_stripped(self) -> None:
        """一、二、...等中文数字前缀被剥离。"""
        assert get_key("一、营业收入") == "revenue"
        assert get_key("二、营业利润") == "operating_profit"
        assert get_key("三、利润总额") == "total_profit"
        assert get_key("四、净利润") == "net_profit"
        assert get_key("五、期末现金及现金等价物余额") == "ending_cash_equiv"
        assert get_key("六、综合收益总额") == "total_comprehensive_income"

    def test_subtract_prefix_stripped(self) -> None:
        """减：前缀被剥离。"""
        assert get_key("减：营业成本") == "operating_cost"
        assert get_key("减：营业外支出") == "non_operating_expense"
        assert get_key("减：所得税费用") == "income_tax_expense"
        assert get_key("减：库存股") == "treasury_stock"

    def test_add_prefix_stripped(self) -> None:
        """加：前缀被剥离。"""
        assert get_key("加：其他收益") == "other_income"
        assert get_key("加：营业外收入") == "non_operating_income"
        assert get_key("加：期初现金及现金等价物余额") == "beginning_cash_equiv"

    def test_half_width_colon_prefix_stripped(self) -> None:
        """半角冒号前缀被剥离。"""
        assert get_key("减:营业成本") == "operating_cost"
        assert get_key("加:其他收益") == "other_income"

    def test_leading_whitespace_stripped(self) -> None:
        """前导空格被剥离。"""
        assert get_key("  货币资金") == "monetary_funds"
        assert get_key("  应收账款") == "accounts_receivable"
        assert get_key("    销售费用") == "selling_exp"

    def test_prefix_plus_alias_combined(self) -> None:
        """前缀清洗 + 别名查找组合工作。"""
        assert get_key("  现金及银行存款") == "monetary_funds"
        assert get_key("  应收账款净额") == "accounts_receivable"
        assert get_key("  预付账款") == "prepayments"
        assert get_key("  股本") == "paid_in_capital"

    def test_prefix_plus_whitespace_combined(self) -> None:
        """前缀 + 空格 + 标准名组合工作。"""
        assert get_key("    减：营业成本") == "operating_cost"
        assert get_key("        加：其他收益") == "other_income"
        assert get_key("  一、营业收入") == "revenue"


class TestExpandedStandardNames:
    """测试新增的标准 CAS 科目名。"""

    def test_bs_asset_names_mapped(self) -> None:
        names = [
            "交易性金融资产", "应收票据", "存货", "合同资产", "持有待售资产",
            "固定资产", "无形资产", "商誉", "长期待摊费用", "递延所得税资产",
        ]
        for name in names:
            assert get_key(name) is not None, f"缺少标准科目映射: {name}"

    def test_bs_liability_names_mapped(self) -> None:
        names = [
            "短期借款", "应付票据", "应付职工薪酬", "应交税费",
            "一年内到期的非流动负债", "长期借款", "应付债券",
            "租赁负债", "递延所得税负债",
        ]
        for name in names:
            assert get_key(name) is not None, f"缺少标准科目映射: {name}"

    def test_new_revenue_standard_names_mapped(self) -> None:
        """新收入准则科目：合同负债与使用权资产。"""
        assert get_key("合同负债") == "contract_liabilities"
        assert get_key("使用权资产") == "right_of_use_assets"
        assert get_name("contract_liabilities") == "合同负债"
        assert get_name("right_of_use_assets") == "使用权资产"

    def test_bs_total_names_mapped(self) -> None:
        assert get_key("负债和所有者权益总计") == "liability_equity_total"

    def test_cf_detailed_names_mapped(self) -> None:
        names = [
            "收到的税费返还", "收到其他与经营活动有关的现金",
            "经营活动现金流入小计", "购买商品、接受劳务支付的现金",
            "支付给职工以及为职工支付的现金", "支付的各项税费",
            "经营活动现金流出小计", "收回投资收到的现金",
            "取得投资收益收到的现金", "处置固定资产收回的现金净额",
            "投资活动现金流入小计", "购建固定资产支付的现金",
            "投资支付的现金", "投资活动现金流出小计",
            "取得借款收到的现金", "筹资活动现金流入小计",
            "偿还债务支付的现金", "分配股利支付现金",
            "筹资活动现金流出小计",
        ]
        for name in names:
            assert get_key(name) is not None, f"缺少现金流量表科目映射: {name}"

    def test_cf_long_form_names_mapped(self) -> None:
        """长格式现金流量项目映射到标准 key。"""
        assert (
            get_key("购建固定资产、无形资产和其他长期资产支付的现金")
            == "cash_paid_for_fixed_assets"
        )
        assert (
            get_key("处置固定资产、无形资产和其他长期资产收回的现金净额")
            == "cash_from_asset_disposal"
        )

    def test_alias_other_comprehensive_income_variant(self) -> None:
        """其他综合收益的税后净额 -> other_comprehensive_income_after_tax。"""
        assert get_key("其他综合收益的税后净额") == "other_comprehensive_income_after_tax"
        assert get_key("税后其他综合收益") == "other_comprehensive_income_after_tax"


class TestEdgeCases:
    """测试边界情况。"""

    def test_map_whitespace_only_name_returns_none(self) -> None:
        assert get_key("   ") is None

    def test_map_none_name_returns_none(self) -> None:
        assert get_key(None) is None  # type: ignore[arg-type]

    def test_unknown_name_with_prefix_returns_none(self) -> None:
        """未知名称带前缀也返回 None。"""
        assert get_key("一、不存在的科目") is None
        assert get_key("减：未知费用") is None

    def test_prefix_only_no_name_returns_none(self) -> None:
        """只有前缀没有实际名称返回 None。"""
        assert get_key("一、") is None
        assert get_key("减：") is None
        assert get_key("加：") is None

    def test_is_known_with_prefixed_name_returns_true(self) -> None:
        """带前缀的标准名 is_known 返回 True。"""
        assert is_known("一、营业收入") is True
        assert is_known("减：营业成本") is True
        assert is_known("  现金及银行存款") is True

    def test_is_known_with_unknown_prefixed_name_returns_false(self) -> None:
        """带前缀的未知名 is_known 返回 False。"""
        assert is_known("一、不存在的科目") is False

    def test_standard_name_without_prefix_still_works(self) -> None:
        """无前缀的标准名仍然正常工作（回归测试）。"""
        assert get_key("营业收入") == "revenue"
        assert get_key("资产总计") == "asset_total"
        assert get_key("经营活动产生的现金流量净额") == "operating_net"


class TestGetSupplementaryKey:
    """get_supplementary_key 测试: 补充资料科目名 -> cf_notes_ 前缀的 key。"""

    def test_net_profit_maps_to_cf_notes_net_profit(self) -> None:
        """净利润在补充资料中映射为 cf_notes_net_profit。"""
        assert get_supplementary_key("净利润") == "cf_notes_net_profit"

    def test_depreciation_maps_to_cf_notes_depreciation(self) -> None:
        """固定资产折旧映射为 cf_notes_depreciation。"""
        assert get_supplementary_key("固定资产折旧") == "cf_notes_depreciation"
        assert get_supplementary_key(
            "固定资产折旧、油气资产折耗、生产性生物资产折旧"
        ) == "cf_notes_depreciation"

    def test_amortization_maps_to_cf_notes_amortization(self) -> None:
        """无形资产摊销映射为 cf_notes_amortization。"""
        assert get_supplementary_key("无形资产摊销") == "cf_notes_amortization"

    def test_long_term_amortization_maps_to_cf_notes_key(self) -> None:
        """长期待摊费用摊销映射为 cf_notes_long_term_amortization。"""
        assert get_supplementary_key("长期待摊费用摊销") == "cf_notes_long_term_amortization"

    def test_impairment_maps_to_cf_notes_impairment(self) -> None:
        """资产减值准备映射为 cf_notes_impairment。"""
        assert get_supplementary_key("资产减值准备") == "cf_notes_impairment"

    def test_credit_impairment_maps_to_cf_notes_credit_impairment(self) -> None:
        """信用减值损失映射为 cf_notes_credit_impairment。"""
        assert get_supplementary_key("信用减值损失") == "cf_notes_credit_impairment"

    def test_disposal_loss_maps_correctly(self) -> None:
        """处置固定资产、无形资产和其他长期资产的损失映射。"""
        assert get_supplementary_key(
            "处置固定资产、无形资产和其他长期资产的损失"
        ) == "cf_notes_disposal_loss"

    def test_scrap_loss_maps_correctly(self) -> None:
        """固定资产报废损失映射为 cf_notes_scrap_loss。"""
        assert get_supplementary_key("固定资产报废损失") == "cf_notes_scrap_loss"

    def test_fair_value_loss_maps_correctly(self) -> None:
        """公允价值变动损失映射为 cf_notes_fair_value_loss。"""
        assert get_supplementary_key("公允价值变动损失") == "cf_notes_fair_value_loss"

    def test_finance_expense_maps_correctly(self) -> None:
        """财务费用映射为 cf_notes_finance_expense。"""
        assert get_supplementary_key("财务费用") == "cf_notes_finance_expense"

    def test_investment_loss_maps_correctly(self) -> None:
        """投资损失映射为 cf_notes_investment_loss。"""
        assert get_supplementary_key("投资损失") == "cf_notes_investment_loss"

    def test_deferred_tax_asset_decrease_maps_correctly(self) -> None:
        """递延所得税资产减少映射。"""
        assert get_supplementary_key(
            "递延所得税资产减少"
        ) == "cf_notes_deferred_tax_asset_decrease"

    def test_deferred_tax_liab_increase_maps_correctly(self) -> None:
        """递延所得税负债增加映射。"""
        assert get_supplementary_key(
            "递延所得税负债增加"
        ) == "cf_notes_deferred_tax_liab_increase"

    def test_inventory_decrease_maps_correctly(self) -> None:
        """存货的减少映射为 cf_notes_inventory_decrease。"""
        assert get_supplementary_key("存货的减少") == "cf_notes_inventory_decrease"

    def test_operating_receivable_decrease_maps_correctly(self) -> None:
        """经营性应收项目的减少映射。"""
        assert get_supplementary_key(
            "经营性应收项目的减少"
        ) == "cf_notes_operating_receivable_decrease"

    def test_operating_payable_increase_maps_correctly(self) -> None:
        """经营性应付项目的增加映射。"""
        assert get_supplementary_key(
            "经营性应付项目的增加"
        ) == "cf_notes_operating_payable_increase"

    def test_operating_net_in_supplementary_uses_cf_notes_prefix(self) -> None:
        """经营活动产生的现金流量净额在补充资料中使用 cf_notes_ 前缀。"""
        assert get_supplementary_key(
            "经营活动产生的现金流量净额"
        ) == "cf_notes_operating_net"

    def test_net_increase_cash_in_supplementary_uses_cf_notes_prefix(self) -> None:
        """现金及现金等价物净增加额在补充资料中使用 cf_notes_ 前缀。"""
        assert get_supplementary_key(
            "现金及现金等价物净增加额"
        ) == "cf_notes_net_increase_cash"

    def test_ending_cash_in_supplementary_uses_cf_notes_prefix(self) -> None:
        """现金的期末余额映射为 cf_notes_ending_cash。"""
        assert get_supplementary_key("现金的期末余额") == "cf_notes_ending_cash"

    def test_beginning_cash_in_supplementary_uses_cf_notes_prefix(self) -> None:
        """现金的期初余额映射为 cf_notes_beginning_cash。"""
        assert get_supplementary_key("现金的期初余额") == "cf_notes_beginning_cash"

    def test_unknown_name_returns_none(self) -> None:
        """不在补充资料映射表中的名称返回 None。"""
        assert get_supplementary_key("不存在的补充科目") is None

    def test_none_returns_none(self) -> None:
        """None 输入返回 None。"""
        assert get_supplementary_key(None) is None


class TestSuffixStripping:
    """测试行尾括号注释的剥离（报表常见的多余字符）。"""

    def test_profit_items_with_parenthetical_suffix(self) -> None:
        """营业利润/利润总额/净利润的括号注释被剥离。"""
        assert get_key("营业利润（亏损以“-”号填列）") == "operating_profit"
        assert get_key("利润总额（亏损总额以“-”号填列）") == "total_profit"
        assert get_key("净利润（净亏损以“-”号填列）") == "net_profit"

    def test_profit_items_with_half_width_parenthesis(self) -> None:
        """半角括号后缀同样被剥离。"""
        assert get_key("净利润(净亏损以-号填列)") == "net_profit"

    def test_loss_items_with_parenthetical_suffix(self) -> None:
        """损失类项目的括号注释被剥离。"""
        assert get_key("投资收益（损失以“-”号填列）") == "investment_income"
        assert get_key("公允价值变动收益（损失以“-”号填列）") == "fair_value_change"
        assert get_key("信用减值损失（损失以“-”号填列）") == "credit_impairment"
        assert get_key("资产减值损失（损失以“-”号填列）") == "asset_impairment"
        assert get_key("资产处置收益（损失以“-”号填列）") == "asset_disposal_gain"

    def test_prefix_and_suffix_combined(self) -> None:
        """序号前缀 + 括号后缀组合清洗。"""
        assert get_key("四、净利润（净亏损以“-”号填列）") == "net_profit"
        assert get_key("减：所得税费用（收益以“-”号填列）") == "income_tax_expense"

    def test_equity_alias_with_parenthetical_suffix(self) -> None:
        """带括号变体的所有者权益别名映射。"""
        assert get_key("实收资本（或股本）") == "paid_in_capital"
        assert get_key("负债和所有者权益总计（或股东权益总计）") == "liability_equity_total"
        assert get_key("归属于母公司所有者权益合计") == "parent_equity"

    def test_suffix_only_name_returns_none(self) -> None:
        """只有括号注释没有实际名称返回 None。"""
        assert get_key("（净亏损以“-”号填列）") is None

    def test_is_known_with_parenthetical_suffix(self) -> None:
        """带括号注释的标准名 is_known 返回 True。"""
        assert is_known("净利润（净亏损以“-”号填列）") is True
