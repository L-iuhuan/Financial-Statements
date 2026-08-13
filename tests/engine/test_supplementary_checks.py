"""附表 4/5/6 检查的单元测试。"""

from __future__ import annotations

from fsa.core.engine.supplementary_checks import (
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

    def test_sales_sum_vs_income_statement(self) -> None:
        dataset = DetailDataset(
            sales_details=[
                SalesDetailRow(2026, 1, "主体", "客户A", "主营业务收入", 800.0, 500.0),
                SalesDetailRow(2026, 1, "主体", "客户B", "主营业务收入", 200.0, 100.0),
            ]
        )
        results = check_sales_vs_income_statement(dataset, _is_report(1000.0, 600.0), 0.01)
        assert all(result.passed for result in results)


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
