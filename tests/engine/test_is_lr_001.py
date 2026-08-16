"""IS-LR-001 减值损失列示方向检查测试。

场景:
- 正数列示 (信用/资产减值损失为正) -> 触发 warning
- 负数/零 (按财会〔2019〕6号以'-'号填列) -> 通过
- 利润表未导入 -> 跳过 (P1)
- 利润表无减值数据 -> 按 0 处理, 不告警 (P1 宁可漏报)
"""

from __future__ import annotations

from pathlib import Path

from fsa.core.engine.registry import RuleRegistry
from fsa.core.engine.runner import RuleRunner
from fsa.core.models.report import Report, ReportItem, ReportType
from fsa.core.models.result import ValidationContext
from fsa.core.models.rule import ReconciliationRule, Severity
from fsa.services.validation_service import ValidationService

RULE_LIBRARY = (
    Path(__file__).resolve().parent.parent.parent / "cas_gouji_rule_library.json"
)


def _rule() -> ReconciliationRule:
    registry = RuleRegistry.from_json(RULE_LIBRARY)
    rule = registry.get_by_id("IS-LR-001")
    assert rule is not None
    return rule


def _is(credit_impairment: float | None = None, asset_impairment: float | None = None) -> Report:
    items = []
    if credit_impairment is not None:
        items.append(ReportItem(key="credit_impairment", name="信用减值损失", amount=credit_impairment))
    if asset_impairment is not None:
        items.append(ReportItem(key="asset_impairment", name="资产减值损失", amount=asset_impairment))
    return Report(
        report_type=ReportType.INCOME_STATEMENT,
        period="2024-12",
        items=items,
    )


def _context(is_report: Report) -> ValidationContext:
    ctx = ValidationContext(period="2024-12")
    ctx.add_report(is_report)
    return ctx


class TestImpairmentDirection:
    """IS-LR-001 减值损失列示方向。"""

    def test_positive_impairment_triggers_warning(self) -> None:
        """正数列示 (credit_impairment>0) -> warning 不通过。"""
        ctx = _context(_is(credit_impairment=100.0, asset_impairment=50.0))
        result = RuleRunner.run(_rule(), ctx)
        assert result.passed is False
        assert result.severity is Severity.WARNING

    def test_positive_asset_impairment_triggers_warning(self) -> None:
        """仅资产减值正数列示 -> warning 不通过。"""
        ctx = _context(_is(credit_impairment=-100.0, asset_impairment=50.0))
        result = RuleRunner.run(_rule(), ctx)
        assert result.passed is False

    def test_negative_impairment_passes(self) -> None:
        """负数列示 (正常格式) -> 通过。"""
        ctx = _context(_is(credit_impairment=-100.0, asset_impairment=-50.0))
        result = RuleRunner.run(_rule(), ctx)
        assert result.passed is True

    def test_zero_impairment_passes(self) -> None:
        """无减值损失 (0) -> 通过。"""
        ctx = _context(_is(credit_impairment=0.0, asset_impairment=0.0))
        result = RuleRunner.run(_rule(), ctx)
        assert result.passed is True

    def test_missing_impairment_lines_passes_conservatively(self) -> None:
        """利润表已导入但无减值数据 -> 按 0 处理, 不告警 (P1 宁可漏报)。"""
        ctx = _context(_is())
        result = RuleRunner.run(_rule(), ctx)
        assert result.passed is True

    def test_missing_income_statement_skipped(self) -> None:
        """利润表未导入 -> 规则不适用, 跳过。"""
        service = ValidationService(RuleRegistry([_rule()]))
        from fsa.core.models.report import Report as R

        summary = service.validate([R(report_type=ReportType.BALANCE_SHEET)], period="2024-12")
        assert summary.total == 0
        assert summary.skipped == 1
