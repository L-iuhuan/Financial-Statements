"""name_mapper 模块测试: 中文科目名到 snake_case key 的映射。

测试内容: 正向映射、反向查找、缺失处理、完整变量覆盖。
"""

from __future__ import annotations

import pytest

from fsa.core.importer.name_mapper import (
    NAME_TO_KEY,
    KEY_TO_NAME,
    get_key,
    get_name,
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

    def test_no_duplicate_keys_in_mapping(self) -> None:
        """确保没有不同的中文名映射到同一个 key。"""
        keys = list(NAME_TO_KEY.values())
        assert len(keys) == len(set(keys)), "存在重复的 key 映射"

    def test_mapping_dict_is_immutable(self) -> None:
        """确保映射字典不可变。"""
        with pytest.raises(TypeError):
            NAME_TO_KEY["新科目"] = "new_key"  # type: ignore[index]


class TestEdgeCases:
    """测试边界情况。"""

    def test_map_whitespace_only_name_returns_none(self) -> None:
        assert get_key("   ") is None

    def test_map_none_name_returns_none(self) -> None:
        assert get_key(None) is None  # type: ignore[arg-type]