"""往来重分类检查的单元测试。"""

from __future__ import annotations

from fsa.core.engine.reclassification_checks import (
    check_reclassification_rules,
    check_reclassification_vs_balance_sheet,
)
from fsa.core.models.detail import DetailDataset, ReclassificationRow
from fsa.core.models.report import Report, ReportItem, ReportType
from fsa.core.models.rule import Severity


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

    def test_alias_account_recognized(self) -> None:
        """别名「预收账款」与标准名「预收款项」统一命中（共享别名源）。"""
        dataset = DetailDataset(
            reclassifications=[
                ReclassificationRow("应收账款", "客户A", -20.0, "预收账款", 20.0),
            ]
        )
        result = check_reclassification_rules(dataset, 0.01)[0]
        assert result.passed is True

    def test_reclass_pairs_override_effective(self) -> None:
        """entity_config 覆写科目对: 应收账款 -> 预付款项（原默认不允许）。"""
        pairs = {"应收账款": ("预付款项",)}
        dataset = DetailDataset(
            reclassifications=[
                ReclassificationRow("应收账款", "客户A", -20.0, "预付款项", 20.0),
            ]
        )
        result = check_reclassification_rules(dataset, 0.01, reclass_pairs=pairs)[0]
        assert result.passed is True

    def test_reclass_pairs_default_regression(self) -> None:
        """缺省配置回归: 应收账款默认只允许重分类到预收款项。"""
        dataset = DetailDataset(
            reclassifications=[
                ReclassificationRow("应收账款", "客户A", -20.0, "预付款项", 20.0),
            ]
        )
        result = check_reclassification_rules(dataset, 0.01)[0]
        assert result.passed is False


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
        """重分类合计与报表不一致: 不通过, 降为 WARNING 并保留坏账口径提示 (P1)。"""
        dataset = DetailDataset(
            reclassifications=[
                ReclassificationRow("应收账款", "客户B", 900.0, "应收账款", 900.0),
            ]
        )
        results = check_reclassification_vs_balance_sheet(dataset, _bs_report(), 0.01)
        ar_result = next(r for r in results if "accounts_receivable" in r.message)
        assert ar_result.passed is False
        assert ar_result.diff == -80.0
        assert ar_result.severity is Severity.WARNING
        assert "坏账准备" in ar_result.message

    def test_balance_sheet_accounts_override_effective(self) -> None:
        """entity_config 覆写报表科目映射: 只核对 accounts_receivable。"""
        accounts = {"accounts_receivable": "应收账款"}
        dataset = DetailDataset(
            reclassifications=[
                ReclassificationRow("应收账款", "客户B", 980.0, "应收账款", 980.0),
            ]
        )
        results = check_reclassification_vs_balance_sheet(
            dataset, _bs_report(), 0.01, balance_sheet_accounts=accounts
        )
        assert len(results) == 1
        assert results[0].passed is True

    def test_balance_sheet_accounts_default_regression(self) -> None:
        """缺省映射回归: 默认核对全部 6 个往来科目。"""
        from fsa.core.engine.reclassification_checks import (
            DEFAULT_BALANCE_SHEET_ACCOUNTS,
        )

        dataset = DetailDataset(reclassifications=[])
        results = check_reclassification_vs_balance_sheet(dataset, _bs_report(), 0.01)
        assert {r.message for r in results} >= {
            "重分类后「accounts_receivable」合计 0.00 vs 报表 980.00: 差额 -980.00（差异可能来自坏账准备等报表调整，需人工确认）",
            "重分类后「advance_from_customers」合计 0.00 vs 报表 20.00: 差额 -20.00（差异可能来自坏账准备等报表调整，需人工确认）",
            "重分类后「accounts_payable」合计 0.00 vs 报表 1,000.00: 差额 -1,000.00（差异可能来自坏账准备等报表调整，需人工确认）",
        }
        assert len(DEFAULT_BALANCE_SHEET_ACCOUNTS) == 6
