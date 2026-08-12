"""公式中文化显示测试。"""

from __future__ import annotations

from fsa.gui.formula_display import formula_to_chinese


class TestFormulaToChinese:
    """英文公式 -> 中文显示 (仅显示层)。"""

    def test_basic_equality(self) -> None:
        assert (
            formula_to_chinese("asset_total == liability_total + equity_total")
            == "资产总计 == 负债合计 + 所有者权益合计"
        )

    def test_threshold(self) -> None:
        result = formula_to_chinese("liability_total / asset_total <= 0.85")
        assert "负债合计" in result
        assert "资产总计" in result
        assert "<=" in result

    def test_logical_operators(self) -> None:
        result = formula_to_chinese("net_profit <= 0 or operating_net >= 0")
        assert "或" in result
        assert "净利润" in result

    def test_ending_beginning_suffix(self) -> None:
        result = formula_to_chinese("monetary_funds_ending - monetary_funds_beginning")
        assert "货币资金(期末)" in result
        assert "货币资金(期初)" in result

    def test_cf_notes_prefix(self) -> None:
        result = formula_to_chinese("cf_notes_net_profit == net_profit")
        assert "(补充资料)" in result

    def test_function_names(self) -> None:
        result = formula_to_chinese("abs(x) <= 0.30")
        assert "绝对值" in result

    def test_unknown_token_kept(self) -> None:
        """未映射变量保留原文, 不翻成错误内容。"""
        result = formula_to_chinese("restricted_adjust + asset_total")
        assert "restricted_adjust" in result
        assert "资产总计" in result

    def test_empty_formula(self) -> None:
        assert formula_to_chinese("") == ""
