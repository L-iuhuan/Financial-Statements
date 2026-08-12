"""ValidationResult, ValidationContext 的单元测试。"""

from __future__ import annotations

import pytest

from fsa.core.models.report import Report, ReportItem, ReportType
from fsa.core.models.rule import Severity, ToleranceType
from fsa.core.models.result import (
    TraceItem,
    ValidationContext,
    ValidationResult,
)


class TestValidationResult:
    """ValidationResult 测试。"""

    def test_normal_construction(self) -> None:
        """正常路径。"""
        result = ValidationResult(
            rule_id="BS-BAL-001",
            rule_name="资产=负债+所有者权益",
            passed=True,
            severity=Severity.ERROR,
            left_value=100.0,
            right_value=100.0,
            diff=0.0,
            tolerance=0.01,
            formula="asset_total == liability_total + equity_total",
            message="校验通过",
        )
        assert result.passed is True
        assert result.diff == 0.0

    def test_failed_result(self) -> None:
        """失败结果。"""
        result = ValidationResult(
            rule_id="BS-BAL-001",
            rule_name="资产=负债+所有者权益",
            passed=False,
            severity=Severity.ERROR,
            left_value=100.0,
            right_value=95.0,
            diff=5.0,
            tolerance=0.01,
            formula="asset_total == liability_total + equity_total",
            message="差额 5.00 元，超出容差 0.01 元",
        )
        assert result.passed is False
        assert result.diff == 5.0

    def test_category_defaults_to_empty(self) -> None:
        """category 默认值为空字符串。"""
        result = ValidationResult(
            rule_id="BS-BAL-001",
            rule_name="测试",
            passed=True,
            severity=Severity.ERROR,
            left_value=0.0,
            right_value=0.0,
            diff=0.0,
            tolerance=0.01,
            formula="a == b",
            message="ok",
        )
        assert result.category == ""

    def test_category_can_be_set(self) -> None:
        """category 可显式设置。"""
        result = ValidationResult(
            rule_id="BS-BAL-001",
            rule_name="测试",
            passed=True,
            severity=Severity.ERROR,
            left_value=0.0,
            right_value=0.0,
            diff=0.0,
            tolerance=0.01,
            formula="a == b",
            message="ok",
            category="A-表内平衡",
        )
        assert result.category == "A-表内平衡"

    def test_trace_defaults_to_empty_list(self) -> None:
        """trace 默认值为空列表。"""
        result = ValidationResult(
            rule_id="BS-BAL-001",
            rule_name="测试",
            passed=True,
            severity=Severity.ERROR,
            left_value=0.0,
            right_value=0.0,
            diff=0.0,
            tolerance=0.01,
            formula="a == b",
            message="ok",
        )
        assert result.trace == []

    def test_trace_can_be_set(self) -> None:
        """trace 可显式设置。"""
        trace = [
            TraceItem(
                key="asset_total", name="资产总计", amount=100.0,
                row=5, column="期末余额", side="left",
            ),
        ]
        result = ValidationResult(
            rule_id="BS-BAL-001",
            rule_name="测试",
            passed=True,
            severity=Severity.ERROR,
            left_value=0.0,
            right_value=0.0,
            diff=0.0,
            tolerance=0.01,
            formula="a == b",
            message="ok",
            trace=trace,
        )
        assert len(result.trace) == 1
        assert result.trace[0].key == "asset_total"

    def test_from_error_has_category(self) -> None:
        """from_error 类方法传递 rule.category。"""
        from fsa.core.models.rule import ReconciliationRule
        rule = ReconciliationRule(
            rule_id="TEST-001",
            name="测试规则",
            category="B-表间勾稽",
            statements=["资产负债表"],
            formula="a == b",
            tolerance_type=ToleranceType.EXACT,
            tolerance=0.01,
            severity=Severity.ERROR,
        )
        result = ValidationResult.from_error(rule, "测试错误")
        assert result.category == "B-表间勾稽"

    def test_from_skip_has_category(self) -> None:
        """from_skip 类方法传递 rule.category。"""
        from fsa.core.models.rule import ReconciliationRule
        rule = ReconciliationRule(
            rule_id="TEST-001",
            name="测试规则",
            category="B-表间勾稽",
            statements=["资产负债表"],
            formula="a == b",
            tolerance_type=ToleranceType.EXACT,
            tolerance=0.01,
            severity=Severity.ERROR,
        )
        result = ValidationResult.from_skip(rule, "测试跳过")
        assert result.category == "B-表间勾稽"


class TestTraceItem:
    """TraceItem 测试。"""

    def test_normal_construction(self) -> None:
        """正常路径。"""
        ti = TraceItem(
            key="asset_total", name="资产总计", amount=100.0,
            row=5, column="期末余额", side="left",
        )
        assert ti.key == "asset_total"
        assert ti.name == "资产总计"
        assert ti.amount == 100.0
        assert ti.row == 5
        assert ti.column == "期末余额"
        assert ti.side == "left"

    def test_side_right(self) -> None:
        """side 为 right。"""
        ti = TraceItem(
            key="liability_total", name="负债合计", amount=60.0,
            row=10, column="期末余额", side="right",
        )
        assert ti.side == "right"

    def test_zero_amount_ok(self) -> None:
        """金额为 0 正常。"""
        ti = TraceItem(
            key="monetary_funds", name="货币资金", amount=0.0,
            row=0, column="", side="left",
        )
        assert ti.amount == 0.0


class TestValidationContext:
    """ValidationContext 测试。"""

    def test_add_and_get_report(self) -> None:
        """添加并获取报表。"""
        ctx = ValidationContext(period="2024-12")
        bs = Report(
            report_type=ReportType.BALANCE_SHEET,
            period="2024-12",
            items=[ReportItem(key="asset_total", name="资产总计", amount=100.0)],
        )
        ctx.add_report(bs)
        assert ctx.get_report(ReportType.BALANCE_SHEET) is bs

    def test_get_nonexistent_report_returns_none(self) -> None:
        """获取不存在的报表返回 None。"""
        ctx = ValidationContext()
        assert ctx.get_report(ReportType.INCOME_STATEMENT) is None

    def test_add_report_overwrites(self) -> None:
        """添加同类型报表覆盖旧的。"""
        ctx = ValidationContext()
        bs1 = Report(
            report_type=ReportType.BALANCE_SHEET,
            items=[ReportItem(key="a", name="A", amount=100.0)],
        )
        bs2 = Report(
            report_type=ReportType.BALANCE_SHEET,
            items=[ReportItem(key="a", name="A", amount=200.0)],
        )
        ctx.add_report(bs1)
        ctx.add_report(bs2)
        report = ctx.get_report(ReportType.BALANCE_SHEET)
        assert report is not None
        assert report.get_amount("a") == 200.0

    def test_build_namespace_single_report(self) -> None:
        """build_namespace: 单张报表，已知科目预填充为 0。"""
        ctx = ValidationContext()
        ctx.add_report(
            Report(
                report_type=ReportType.BALANCE_SHEET,
                items=[
                    ReportItem(key="asset_total", name="资产总计", amount=100.0),
                    ReportItem(key="liability_total", name="负债合计", amount=60.0),
                    ReportItem(key="equity_total", name="所有者权益合计", amount=40.0),
                ],
            )
        )
        ns = ctx.build_namespace(["资产负债表"])
        # 报表中的科目有实际值
        assert ns["asset_total"] == 100.0
        assert ns["liability_total"] == 60.0
        assert ns["equity_total"] == 40.0
        # 已知科目未在报表中出现时预填充为 0
        assert ns["monetary_funds"] == 0.0
        assert ns["accounts_receivable"] == 0.0

    def test_build_namespace_multiple_reports(self) -> None:
        """build_namespace: 多张报表合并，已知科目预填充。"""
        ctx = ValidationContext()
        ctx.add_report(
            Report(
                report_type=ReportType.BALANCE_SHEET,
                items=[ReportItem(key="asset_total", name="资产总计", amount=100.0)],
            )
        )
        ctx.add_report(
            Report(
                report_type=ReportType.INCOME_STATEMENT,
                items=[ReportItem(key="net_profit", name="净利润", amount=10.0)],
            )
        )
        ns = ctx.build_namespace(["资产负债表", "利润表"])
        assert ns["asset_total"] == 100.0
        assert ns["net_profit"] == 10.0
        # 预填充的已知科目
        assert ns["monetary_funds"] == 0.0
        assert ns["revenue"] == 0.0

    def test_build_namespace_missing_report_skipped(self) -> None:
        """build_namespace: 报表不存在时跳过，不报错，已知科目仍预填充。"""
        ctx = ValidationContext()
        ctx.add_report(
            Report(
                report_type=ReportType.BALANCE_SHEET,
                items=[ReportItem(key="a", name="A", amount=100.0)],
            )
        )
        ns = ctx.build_namespace(["资产负债表", "利润表"])
        assert ns["a"] == 100.0
        # 已知科目预填充为 0
        assert ns["monetary_funds"] == 0.0

    def test_build_namespace_empty_context(self) -> None:
        """build_namespace: 空上下文返回所有已知科目默认 0。"""
        ctx = ValidationContext()
        ns = ctx.build_namespace(["资产负债表"])
        # 空报表 -> 所有已知科目预填充为 0
        assert ns["asset_total"] == 0.0
        assert ns["monetary_funds"] == 0.0

    def test_build_namespace_duplicate_key_raises(self) -> None:
        """build_namespace: 同一 key 出现在多张报表中抛异常。"""
        ctx = ValidationContext()
        ctx.add_report(
            Report(
                report_type=ReportType.BALANCE_SHEET,
                items=[ReportItem(key="total", name="合计", amount=100.0)],
            )
        )
        ctx.add_report(
            Report(
                report_type=ReportType.INCOME_STATEMENT,
                items=[ReportItem(key="total", name="合计", amount=200.0)],
            )
        )
        with pytest.raises(ValueError, match="重复"):
            ctx.build_namespace(["资产负债表", "利润表"])

    def test_build_namespace_unknown_statement_skipped(self) -> None:
        """build_namespace: 未知报表类型名跳过，已知科目仍预填充。"""
        ctx = ValidationContext()
        ns = ctx.build_namespace(["不存在的报表"])
        # 未知报表 -> 仍预填充已知科目为 0
        assert ns["asset_total"] == 0.0
        assert ns["monetary_funds"] == 0.0

    def test_get_item_finds_in_main_report(self) -> None:
        """get_item: 在主表中查找项目。"""
        ctx = ValidationContext()
        ctx.add_report(
            Report(
                report_type=ReportType.BALANCE_SHEET,
                items=[ReportItem(key="asset_total", name="资产总计", amount=100.0)],
            )
        )
        item = ctx.get_item("asset_total")
        assert item is not None
        assert item.key == "asset_total"
        assert item.amount == 100.0

    def test_get_item_finds_cf_notes_key(self) -> None:
        """get_item: 查找 cf_notes_ 前缀的项目。"""
        ctx = ValidationContext()
        ctx.add_report(
            Report(
                report_type=ReportType.CASH_FLOW_STATEMENT,
                items=[
                    ReportItem(
                        key="cf_notes_net_profit", name="净利润",
                        amount=705000.0, row=25,
                    ),
                ],
            )
        )
        item = ctx.get_item("cf_notes_net_profit")
        assert item is not None
        assert item.key == "cf_notes_net_profit"
        assert item.amount == 705000.0

    def test_get_item_returns_none_for_missing(self) -> None:
        """get_item: 不存在的 key 返回 None。"""
        ctx = ValidationContext()
        ctx.add_report(
            Report(
                report_type=ReportType.BALANCE_SHEET,
                items=[ReportItem(key="asset_total", name="资产总计", amount=100.0)],
            )
        )
        assert ctx.get_item("nonexistent") is None

    def test_get_item_returns_none_for_empty_context(self) -> None:
        """get_item: 空上下文返回 None。"""
        ctx = ValidationContext()
        assert ctx.get_item("anything") is None

    def test_build_namespace_has_ending_variable(self) -> None:
        """build_namespace: 为每个 item 设置 {key}_ending 变量。"""
        ctx = ValidationContext()
        ctx.add_report(
            Report(
                report_type=ReportType.BALANCE_SHEET,
                items=[
                    ReportItem(
                        key="undistributed_profit", name="未分配利润",
                        amount=500000.0, beginning_amount=400000.0,
                    ),
                ],
            )
        )
        ns = ctx.build_namespace(["资产负债表"])
        assert ns["undistributed_profit_ending"] == 500000.0
        assert ns["undistributed_profit_beginning"] == 400000.0

    def test_build_namespace_beginning_var_none_omitted(self) -> None:
        """build_namespace: beginning_amount 为 None 时不设置 _beginning 变量。"""
        ctx = ValidationContext()
        ctx.add_report(
            Report(
                report_type=ReportType.BALANCE_SHEET,
                items=[
                    ReportItem(
                        key="asset_total", name="资产总计", amount=100.0,
                    ),
                ],
            )
        )
        ns = ctx.build_namespace(["资产负债表"])
        assert ns["asset_total_ending"] == 100.0
        assert "asset_total_beginning" not in ns

    def test_build_namespace_beginning_var_zero_present(self) -> None:
        """build_namespace: beginning_amount 为 0 时仍然设置 _beginning 变量。"""
        ctx = ValidationContext()
        ctx.add_report(
            Report(
                report_type=ReportType.BALANCE_SHEET,
                items=[
                    ReportItem(
                        key="treasury_stock", name="库存股",
                        amount=0.0, beginning_amount=0.0,
                    ),
                ],
            )
        )
        ns = ctx.build_namespace(["资产负债表"])
        assert ns["treasury_stock_ending"] == 0.0
        assert ns["treasury_stock_beginning"] == 0.0

    def test_build_namespace_cf_notes_has_ending_var(self) -> None:
        """build_namespace: cf_notes_ 前缀的项目也设置 _ending 变量。"""
        ctx = ValidationContext()
        ctx.add_report(
            Report(
                report_type=ReportType.CASH_FLOW_STATEMENT,
                items=[
                    ReportItem(
                        key="cf_notes_net_profit", name="净利润",
                        amount=705000.0, beginning_amount=650000.0,
                    ),
                ],
            )
        )
        ns = ctx.build_namespace(["现金流量表"])
        assert ns["cf_notes_net_profit_ending"] == 705000.0
        assert ns["cf_notes_net_profit_beginning"] == 650000.0

    def test_build_namespace_profit_distribution_keys_absent(self) -> None:
        """build_namespace: 利润分配类变量不预填充 (无数据源, 缺失时规则跳过 per P1)。"""
        ctx = ValidationContext()
        ns = ctx.build_namespace(["资产负债表"])
        # dividends 等变量三大主表无数据源, 不预填 0 — 若预填会导致
        # BS-IS-001 对分红企业误报 (如茅台 2023 分红 ~658 亿)
        assert "dividends" not in ns
        assert "surplus_withheld" not in ns
        assert "prior_period_adjust" not in ns
        assert "restricted_adjust" not in ns
