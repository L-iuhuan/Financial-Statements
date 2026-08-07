"""ValidationResult, ValidationContext 的单元测试。"""

from __future__ import annotations

import pytest

from fsa.core.models.report import Report, ReportItem, ReportType
from fsa.core.models.rule import Severity, ToleranceType
from fsa.core.models.result import ValidationContext, ValidationResult


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
        """build_namespace: 单张报表。"""
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
        assert ns == {"asset_total": 100.0, "liability_total": 60.0, "equity_total": 40.0}

    def test_build_namespace_multiple_reports(self) -> None:
        """build_namespace: 多张报表合并。"""
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
        assert ns == {"asset_total": 100.0, "net_profit": 10.0}

    def test_build_namespace_missing_report_skipped(self) -> None:
        """build_namespace: 报表不存在时跳过，不报错。"""
        ctx = ValidationContext()
        ctx.add_report(
            Report(
                report_type=ReportType.BALANCE_SHEET,
                items=[ReportItem(key="a", name="A", amount=100.0)],
            )
        )
        ns = ctx.build_namespace(["资产负债表", "利润表"])
        assert ns == {"a": 100.0}

    def test_build_namespace_empty_context(self) -> None:
        """build_namespace: 空上下文返回空字典。"""
        ctx = ValidationContext()
        ns = ctx.build_namespace(["资产负债表"])
        assert ns == {}

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
        """build_namespace: 未知报表类型名跳过。"""
        ctx = ValidationContext()
        ns = ctx.build_namespace(["不存在的报表"])
        assert ns == {}
