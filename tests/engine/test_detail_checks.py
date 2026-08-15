"""明细层勾稽检查函数的单元测试。"""

from __future__ import annotations

from fsa.core.engine.detail_checks import (
    check_cash_flow_detail_vs_journal,
    check_cash_flow_detail_vs_statement,
    check_journal_voucher_balance,
    check_trial_balance_vs_balance_sheet,
)
from fsa.core.models.detail import (
    CashFlowDetailRow,
    DetailDataset,
    JournalRow,
    TrialBalanceRow,
)
from fsa.core.models.report import Report, ReportItem, ReportType


def _cf_report(amount: float) -> dict[ReportType, Report]:
    return {
        ReportType.CASH_FLOW_STATEMENT: Report(
            report_type=ReportType.CASH_FLOW_STATEMENT,
            items=[
                ReportItem(
                    key="cash_received_from_sales",
                    name="销售商品、提供劳务收到的现金",
                    amount=amount,
                    row=2,
                    column="本期金额",
                )
            ],
        )
    }


def _bs_report(amount: float) -> dict[ReportType, Report]:
    return {
        ReportType.BALANCE_SHEET: Report(
            report_type=ReportType.BALANCE_SHEET,
            items=[
                ReportItem(
                    key="monetary_funds",
                    name="货币资金",
                    amount=amount,
                    row=2,
                    column="期末余额",
                )
            ],
        )
    }


class TestJournalVoucherBalance:
    """序时账逐凭证借贷平衡检查。"""

    def test_balanced_voucher_passes(self) -> None:
        dataset = DetailDataset(
            journal=[
                JournalRow("2026-06-30", "记-0001", "银行存款", "1002", "银行存款", "收款", "贷", 500.0),
                JournalRow("2026-06-30", "记-0001", "应收账款", "1122", "应收账款", "收款", "借", 500.0),
            ]
        )
        results = check_journal_voucher_balance(dataset, tolerance=0.01)
        assert results[0].passed is True

    def test_unbalanced_voucher_fails_with_voucher_no(self) -> None:
        dataset = DetailDataset(
            journal=[
                JournalRow("2026-06-30", "记-0002", "银行存款", "1002", "银行存款", "付款", "贷", 500.0),
                JournalRow("2026-06-30", "记-0002", "管理费用", "6602", "管理费用", "付款", "借", 400.0),
            ]
        )
        results = check_journal_voucher_balance(dataset, tolerance=0.01)
        assert results[0].passed is False
        assert "记-0002" in results[0].message

    def test_large_mixed_sum_uses_fsum(self) -> None:
        """大额混合累加: 聚合值使用 math.fsum，避免 naive sum 的浮点抵消误差。

        1e16 + 1 + (-1e16) 用 sum() 得 0.0，fsum() 得精确的 1.0。
        """
        dataset = DetailDataset(
            journal=[
                JournalRow("2026-06-30", "记-0001", "银行存款", "1002", "银行存款", "a", "借", 1e16),
                JournalRow("2026-06-30", "记-0001", "银行存款", "1002", "银行存款", "a", "贷", 1e16),
                JournalRow("2026-06-30", "记-0002", "银行存款", "1002", "银行存款", "b", "借", 1.0),
                JournalRow("2026-06-30", "记-0002", "银行存款", "1002", "银行存款", "b", "贷", 1.0),
                JournalRow("2026-06-30", "记-0003", "银行存款", "1002", "银行存款", "c", "借", -1e16),
                JournalRow("2026-06-30", "记-0003", "银行存款", "1002", "银行存款", "c", "贷", -1e16),
            ]
        )
        result = check_journal_voucher_balance(dataset, tolerance=0.01)[0]
        assert result.passed is True
        assert result.left_value == 1.0
        assert result.right_value == 1.0
        assert result.diff == 0.0


class TestCashFlowDetailVsStatement:
    """现金流量明细合计与主表核对。"""

    def test_matching_project_passes(self) -> None:
        dataset = DetailDataset(
            cash_flow_detail=[
                CashFlowDetailRow("记-0001", "销售商品、提供劳务收到的现金(01)", "货款", "流入", 300.0),
                CashFlowDetailRow("记-0002", "销售商品、提供劳务收到的现金(01)", "货款", "流入", 200.0),
            ]
        )
        results = check_cash_flow_detail_vs_statement(dataset, _cf_report(500.0), 0.01)
        assert results[0].passed is True

    def test_mismatched_project_reports_diff(self) -> None:
        dataset = DetailDataset(
            cash_flow_detail=[
                CashFlowDetailRow("记-0001", "销售商品、提供劳务收到的现金(01)", "货款", "流入", 300.0),
            ]
        )
        results = check_cash_flow_detail_vs_statement(dataset, _cf_report(500.0), 0.01)
        assert results[0].passed is False
        assert results[0].diff == -200.0

    def test_unmapped_detail_project_skipped_not_errored(self) -> None:
        """明细项目未匹配主表: 跳过 (passed=True, skipped=True) 而非报错 (P1)。"""
        dataset = DetailDataset(
            cash_flow_detail=[
                CashFlowDetailRow("记-0001", "不存在的项目", "货款", "流入", 300.0),
            ]
        )
        results = check_cash_flow_detail_vs_statement(dataset, _cf_report(500.0), 0.01)
        assert len(results) == 1
        assert results[0].passed is True
        assert results[0].skipped is True
        assert results[0].errored is False
        assert "已跳过核对" in results[0].message


class TestCashFlowDetailVsJournal:
    """现金流明细与序时账现金科目按凭证核对。"""

    def test_scope_config_controls_comparison(self) -> None:
        dataset = DetailDataset(
            cash_flow_detail=[
                CashFlowDetailRow("记-0001", "投资所支付的现金(14)", "理财", "流出", 500.0),
            ],
            journal=[
                JournalRow("2026-06-30", "记-0001", "其他货币资金", "1012", "理财", "理财", "借", 500.0),
                JournalRow("2026-06-30", "记-0001", "银行存款", "1002", "银行存款", "理财", "贷", 500.0),
            ],
        )
        # 口径只含 1002：明细 -500 == 序时账 1002 净额 -500，一致
        matched = check_cash_flow_detail_vs_journal(dataset, ("1002",), 0.01)
        assert matched[0].passed is True
        # 口径含 1012：序时账净额为 0，暴露口径差异
        mismatched = check_cash_flow_detail_vs_journal(dataset, ("1001", "1002", "1012"), 0.01)
        assert mismatched[0].passed is False

    def test_large_mixed_sum_uses_fsum(self) -> None:
        """大额混合净额: 聚合值使用 math.fsum，避免浮点抵消误差。"""
        dataset = DetailDataset(
            cash_flow_detail=[
                CashFlowDetailRow("记-0001", "销售商品、提供劳务收到的现金(01)", "货款", "流入", 1e16),
                CashFlowDetailRow("记-0001", "销售商品、提供劳务收到的现金(01)", "货款", "流出", 1e16),
                CashFlowDetailRow("记-0001", "销售商品、提供劳务收到的现金(01)", "货款", "流入", 1.0),
                CashFlowDetailRow("记-0002", "投资所支付的现金(14)", "理财", "流出", 1e16),
                CashFlowDetailRow("记-0002", "投资所支付的现金(14)", "理财", "流入", 1e16),
            ],
            journal=[
                JournalRow("2026-06-30", "记-0001", "银行存款", "1002", "银行存款", "a", "借", 1e16),
                JournalRow("2026-06-30", "记-0001", "银行存款", "1002", "银行存款", "a", "贷", 1e16),
                JournalRow("2026-06-30", "记-0001", "银行存款", "1002", "银行存款", "a", "借", 1.0),
                JournalRow("2026-06-30", "记-0002", "银行存款", "1002", "银行存款", "b", "借", 1e16),
                JournalRow("2026-06-30", "记-0002", "银行存款", "1002", "银行存款", "b", "贷", 1e16),
            ],
        )
        result = check_cash_flow_detail_vs_journal(dataset, ("1002",), 0.01)[0]
        assert result.passed is True
        assert result.left_value == 1.0
        assert result.right_value == 1.0


class TestTrialBalanceVsBalanceSheet:
    """余额表期末余额与资产负债表核对。"""

    def test_matching_amount_passes(self) -> None:
        dataset = DetailDataset(
            trial_balance=[
                TrialBalanceRow(account_code="1002", account_name="银行存款", ending_debit=600.0),
                TrialBalanceRow(account_code="1012", account_name="其他货币资金", ending_debit=100.0),
            ]
        )
        mappings = {"monetary_funds": {"codes": ("1001", "1002", "1012"), "side": "debit"}}
        results = check_trial_balance_vs_balance_sheet(dataset, _bs_report(700.0), mappings, 0.01)
        assert results[0].passed is True

    def test_mismatched_amount_reports_diff(self) -> None:
        dataset = DetailDataset(
            trial_balance=[
                TrialBalanceRow(account_code="1002", account_name="银行存款", ending_debit=600.0),
            ]
        )
        mappings = {"monetary_funds": {"codes": ("1001", "1002", "1012"), "side": "debit"}}
        results = check_trial_balance_vs_balance_sheet(dataset, _bs_report(650.0), mappings, 0.01)
        assert results[0].passed is False
        assert results[0].diff == -50.0
