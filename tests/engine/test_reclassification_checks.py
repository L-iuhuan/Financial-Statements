"""往来重分类检查的单元测试。"""

from __future__ import annotations

from fsa.core.engine.reclassification_checks import (
    check_reclassification_rules,
    check_reclassification_vs_balance_sheet,
)
from fsa.core.models.detail import DetailDataset, ReclassificationRow
from fsa.core.models.report import Report, ReportItem, ReportType


def _bs_report() -> dict[ReportType, Report]:
    return {
        ReportType.BALANCE_SHEET: Report(
            report_type=ReportType.BALANCE_SHEET,
            items=[
                ReportItem("accounts_receivable", "应收账款", 980.0, row=1, column="期末余额"),
                ReportItem("advance_from_customers", "预收款项", 20.0, row=2, column="期末余额"),
                ReportItem("accounts_payable", "应付账款", 1000.0, row=3, column="期末余额"),
            ],
        )
    }


class TestReclassificationRules:
    """负数重分类与科目对应规则。"""

    def test_negative_reclass_passes(self) -> None:
        dataset = DetailDataset(
            reclassifications=[
                ReclassificationRow("应收账款", "客户A", -20.0, "预收账款", 20.0),
            ]
        )
        result = check_reclassification_rules(dataset, 0.01)[0]
        assert result.passed is True

    def test_wrong_reclassified_account_fails(self) -> None:
        dataset = DetailDataset(
            reclassifications=[
                ReclassificationRow("应收账款", "客户A", -20.0, "应收账款", 20.0),
            ]
        )
        result = check_reclassification_rules(dataset, 0.01)[0]
        assert result.passed is False
        assert "客户A" in result.message

    def test_positive_amount_unchanged_passes(self) -> None:
        dataset = DetailDataset(
            reclassifications=[
                ReclassificationRow("应付账款", "供应商A", 1000.0, "应付账款", 1000.0),
            ]
        )
        result = check_reclassification_rules(dataset, 0.01)[0]
        assert result.passed is True


class TestReclassificationVsBalanceSheet:
    """重分类后科目合计与资产负债表勾稽。"""

    def test_sums_match_balance_sheet(self) -> None:
        dataset = DetailDataset(
            reclassifications=[
                ReclassificationRow("应收账款", "客户B", 980.0, "应收账款", 980.0),
                ReclassificationRow("应收账款", "客户A", -20.0, "预收账款", 20.0),
                ReclassificationRow("应付账款", "供应商A", 1000.0, "应付账款", 1000.0),
            ]
        )
        results = check_reclassification_vs_balance_sheet(dataset, _bs_report(), 0.01)
        assert all(result.passed for result in results)

    def test_mismatch_reports_diff(self) -> None:
        dataset = DetailDataset(
            reclassifications=[
                ReclassificationRow("应收账款", "客户B", 900.0, "应收账款", 900.0),
            ]
        )
        results = check_reclassification_vs_balance_sheet(dataset, _bs_report(), 0.01)
        ar_result = next(r for r in results if "accounts_receivable" in r.message)
        assert ar_result.passed is False
        assert ar_result.diff == -80.0
