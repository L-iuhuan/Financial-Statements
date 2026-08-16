"""L4 现金流选择正确性检查的单元测试。"""

from __future__ import annotations

from fsa.core.engine.cash_flow_checks import (
    check_cash_flow_classification,
    check_cash_flow_coverage,
)
from fsa.core.engine.cash_flow_rules import DEFAULT_CASH_FLOW_RULES
from fsa.core.models.detail import CashFlowDetailRow, DetailDataset, JournalRow


def _dataset_with_voucher(counterpart_code: str, project: str) -> DetailDataset:
    return DetailDataset(
        journal=[
            JournalRow("2026-06-30", "记-0001", "银行存款", "1002", "银行存款", "收款", "借", 500.0),
            JournalRow("2026-06-30", "记-0001", "对方科目", counterpart_code, "对方科目", "收款", "贷", 500.0),
        ],
        cash_flow_detail=[
            CashFlowDetailRow("记-0001", project, "货款", "流入", 500.0),
        ],
    )


class TestCashFlowClassification:
    """现金流项目与对方科目一致性检查。"""

    def test_sales_receipt_with_receivable_passes(self) -> None:
        dataset = _dataset_with_voucher("1122", "销售商品、提供劳务收到的现金(01)")
        results = check_cash_flow_classification(dataset, ("1002",), 0.01)
        sales_rule = next(r for r in results if r.rule_id == "CF-CLS-001")
        assert sales_rule.passed is True

    def test_sales_receipt_with_payable_is_suspicious(self) -> None:
        dataset = _dataset_with_voucher("2202", "销售商品、提供劳务收到的现金(01)")
        results = check_cash_flow_classification(dataset, ("1002",), 0.01)
        sales_rule = next(r for r in results if r.rule_id == "CF-CLS-001")
        assert sales_rule.passed is False
        assert "记-0001" in sales_rule.message

    def test_project_name_suo_variation_is_matched(self) -> None:
        """项目名含「所」字（投资所支付的现金）仍能命中规则。"""
        dataset = DetailDataset(
            journal=[
                JournalRow("2026-06-30", "记-0001", "其他货币资金", "1012", "理财", "理财", "借", 500.0),
                JournalRow("2026-06-30", "记-0001", "银行存款", "1002", "银行存款", "理财", "贷", 500.0),
            ],
            cash_flow_detail=[
                CashFlowDetailRow("记-0001", "投资所支付的现金(14)", "理财", "流出", 500.0),
            ],
        )
        results = check_cash_flow_classification(dataset, ("1002",), 0.01)
        invest_rule = next(r for r in results if r.rule_id == "CF-CLS-006")
        assert invest_rule.passed is False
        assert "记-0001" in invest_rule.message


class TestCashFlowCoverage:
    """现金凭证是否都指定了现金流项目。"""

    def test_missing_detail_flagged(self) -> None:
        dataset = DetailDataset(
            journal=[
                JournalRow("2026-06-30", "记-0001", "银行存款", "1002", "银行存款", "收款", "借", 500.0),
            ],
            cash_flow_detail=[],
        )
        result = check_cash_flow_coverage(dataset, ("1002",), 0.01)
        assert result.passed is False
        assert "记-0001" in result.message

    def test_full_coverage_passes(self) -> None:
        dataset = DetailDataset(
            journal=[
                JournalRow("2026-06-30", "记-0001", "银行存款", "1002", "银行存款", "收款", "借", 500.0),
            ],
            cash_flow_detail=[
                CashFlowDetailRow("记-0001", "销售商品、提供劳务收到的现金(01)", "货款", "流入", 500.0),
            ],
        )
        result = check_cash_flow_coverage(dataset, ("1002",), 0.01)
        assert result.passed is True


class TestCashFlowRuleCodeTable:
    """对方科目编码表与标准科目表一致性。"""

    def test_cls001_excludes_2204_and_includes_contract_liability(self) -> None:
        """标准科目表无 2204 编码；2203 预收/2205 合同负债必须在列。"""
        rule = next(r for r in DEFAULT_CASH_FLOW_RULES if r.rule_id == "CF-CLS-001")
        assert "2204" not in rule.counterpart_prefixes
        assert "2203" in rule.counterpart_prefixes
        assert "2205" in rule.counterpart_prefixes

    def test_investment_rules_include_1503_1504(self) -> None:
        """投资类规则补充 1503 其他债权投资 / 1504 其他权益工具投资。"""
        for rule_id in ("CF-CLS-005", "CF-CLS-006"):
            rule = next(r for r in DEFAULT_CASH_FLOW_RULES if r.rule_id == rule_id)
            assert "1503" in rule.counterpart_prefixes
            assert "1504" in rule.counterpart_prefixes

    def test_1521_is_investment_property(self) -> None:
        """1521 为投资性房地产, 名称不得再写作其他权益工具投资。"""
        for rule_id in ("CF-CLS-005", "CF-CLS-006"):
            rule = next(r for r in DEFAULT_CASH_FLOW_RULES if r.rule_id == rule_id)
            assert "1521" in rule.counterpart_prefixes
            assert "投资性房地产" in rule.description
