"""附表 4/5/6 检查的单元测试。"""

from __future__ import annotations

from fsa.core.engine.supplementary_checks import (
    _rp_breakdown_field_names,
    check_internal_cash_flow_vs_statement,
    check_related_party_purchase_breakdown,
    check_sales_detail_consistency,
    check_sales_vs_income_statement,
)
from fsa.core.models.detail import (
    DetailDataset,
    InternalCashFlowRow,
    RelatedPartyPurchaseRow,
    SalesDetailRow,
)
from fsa.core.models.report import Report, ReportItem, ReportType
from fsa.core.models.rule import Severity


def _is_report(revenue: float, cost: float) -> dict[ReportType, Report]:
    return {
        ReportType.INCOME_STATEMENT: Report(
            report_type=ReportType.INCOME_STATEMENT,
            items=[
                ReportItem("revenue", "营业收入", revenue, row=1, column="本期金额"),
                ReportItem("operating_cost", "营业成本", cost, row=2, column="本期金额"),
            ],
        )
    }


def _cf_report(project: str, amount: float) -> dict[ReportType, Report]:
    return {
        ReportType.CASH_FLOW_STATEMENT: Report(
            report_type=ReportType.CASH_FLOW_STATEMENT,
            items=[ReportItem("cash_received_from_sales", project, amount, row=1, column="本期金额")],
        )
    }


class TestRelatedPartyPurchase:
    """关联方采购分类合计检查。"""

    def test_breakdown_matches_total(self) -> None:
        dataset = DetailDataset(
            related_party_purchases=[
                RelatedPartyPurchaseRow("购买方", "对方A", "采购款", 1000.0, inventory=1000.0),
            ]
        )
        result = check_related_party_purchase_breakdown(dataset, 0.01)[0]
        assert result.passed is True

    def test_breakdown_mismatch_fails(self) -> None:
        dataset = DetailDataset(
            related_party_purchases=[
                RelatedPartyPurchaseRow("购买方", "对方A", "采购款", 1000.0, inventory=900.0),
            ]
        )
        result = check_related_party_purchase_breakdown(dataset, 0.01)[0]
        assert result.passed is False
        assert "对方A" in result.message

    def test_breakdown_uses_all_numeric_fields(self) -> None:
        """分类合计覆盖全部数值字段（含非常规字段 rnd_expense/admin_expense）。"""
        dataset = DetailDataset(
            related_party_purchases=[
                RelatedPartyPurchaseRow(
                    "购买方", "对方A", "采购款", 1000.0,
                    supply_chain=100.0, mold=100.0, inventory=100.0,
                    main_cost=100.0, other_cost=100.0, rnd_expense=100.0,
                    admin_expense=100.0, selling_expense=100.0, other=200.0,
                ),
            ]
        )
        result = check_related_party_purchase_breakdown(dataset, 0.01)[0]
        assert result.passed is True

    def test_breakdown_fields_dynamic_and_complete(self) -> None:
        """分类字段基于模型动态收集: 覆盖全部 float 分类字段, 排除合计/行号。"""
        fields = _rp_breakdown_field_names()
        assert "supply_chain" in fields
        assert "other" in fields
        assert "total_amount" not in fields
        assert "row" not in fields
        # 已知的 9 个分类字段全部纳入（企业扩展 float 字段时自动加入）
        assert len(fields) == 9


class TestSalesDetail:
    """销售收入成本明细检查。"""

    def test_cost_parts_and_margin_ok(self) -> None:
        dataset = DetailDataset(
            sales_details=[
                SalesDetailRow(
                    2026, 1, "主体", "客户A", "主营业务收入",
                    1000.0, 600.0, 400.0, 100.0, 50.0, 50.0, 0.4,
                )
            ]
        )
        result = check_sales_detail_consistency(dataset, 0.01)[0]
        assert result.passed is True

    def test_cost_parts_mismatch_fails(self) -> None:
        """成本构成不一致: 不通过, 且降为 WARNING (成本构成可能部分填报, P1)。"""
        dataset = DetailDataset(
            sales_details=[
                SalesDetailRow(
                    2026, 1, "主体", "客户A", "主营业务收入",
                    1000.0, 600.0, 300.0, 100.0, 50.0, 50.0, 0.4,
                )
            ]
        )
        result = check_sales_detail_consistency(dataset, 0.01)[0]
        assert result.passed is False
        assert result.severity is Severity.WARNING
        assert "部分填报" in result.message

    def test_margin_diff_within_default_tolerance_passes(self) -> None:
        """毛利率与理论值差 0.01（=默认容差）边界内通过。"""
        dataset = DetailDataset(
            sales_details=[
                SalesDetailRow(
                    2026, 1, "主体", "客户A", "主营业务收入",
                    1000.0, 600.0, 0.0, 0.0, 0.0, 0.0, 0.41,
                )
            ]
        )
        result = check_sales_detail_consistency(dataset, 0.01)[0]
        assert result.passed is True

    def test_margin_diff_over_default_tolerance_fails(self) -> None:
        """毛利率与理论值差 0.02 超过默认容差 0.01 不通过。"""
        dataset = DetailDataset(
            sales_details=[
                SalesDetailRow(
                    2026, 1, "主体", "客户A", "主营业务收入",
                    1000.0, 600.0, 0.0, 0.0, 0.0, 0.0, 0.42,
                )
            ]
        )
        result = check_sales_detail_consistency(dataset, 0.01)[0]
        assert result.passed is False

    def test_margin_tolerance_override_passes(self) -> None:
        """margin_tolerance 覆写为 0.05: 差 0.02 的毛利率通过。"""
        dataset = DetailDataset(
            sales_details=[
                SalesDetailRow(
                    2026, 1, "主体", "客户A", "主营业务收入",
                    1000.0, 600.0, 0.0, 0.0, 0.0, 0.0, 0.42,
                )
            ]
        )
        result = check_sales_detail_consistency(dataset, 0.01, margin_tolerance=0.05)[0]
        assert result.passed is True

    def test_sales_sum_vs_income_statement(self) -> None:
        dataset = DetailDataset(
            sales_details=[
                SalesDetailRow(2026, 1, "主体", "客户A", "主营业务收入", 800.0, 500.0),
                SalesDetailRow(2026, 1, "主体", "客户B", "主营业务收入", 200.0, 100.0),
            ]
        )
        results = check_sales_vs_income_statement(dataset, _is_report(1000.0, 600.0), 0.01)
        assert all(result.passed for result in results)

    def test_sales_sum_mismatch_is_warning_with_coverage_hint(self) -> None:
        """明细合计 vs 利润表不一致: 降为 WARNING 并提示全量口径假设 (P1)。"""
        dataset = DetailDataset(
            sales_details=[
                SalesDetailRow(2026, 1, "主体", "客户A", "主营业务收入", 800.0, 500.0),
            ]
        )
        results = check_sales_vs_income_statement(dataset, _is_report(1000.0, 600.0), 0.01)
        assert all(result.passed is False for result in results)
        assert all(result.severity is Severity.WARNING for result in results)
        assert any("全量口径" in result.message for result in results)


class TestInternalCashFlow:
    """内部现金流不超过主表的检查。"""

    def test_subset_within_statement_passes(self) -> None:
        dataset = DetailDataset(
            internal_cash_flows=[
                InternalCashFlowRow(1, "主体", "对方A", "货款", "收到的其他与经营活动的现金", 100.0),
            ]
        )
        results = check_internal_cash_flow_vs_statement(
            dataset, _cf_report("收到其他与经营活动有关的现金", 500.0), 0.01
        )
        assert results[0].passed is True

    def test_exceeding_statement_fails(self) -> None:
        dataset = DetailDataset(
            internal_cash_flows=[
                InternalCashFlowRow(1, "主体", "对方A", "货款", "收到的其他与经营活动的现金", 600.0),
            ]
        )
        results = check_internal_cash_flow_vs_statement(
            dataset, _cf_report("收到其他与经营活动有关的现金", 500.0), 0.01
        )
        assert results[0].passed is False
