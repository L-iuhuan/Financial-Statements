"""报表包校验服务测试。"""

from __future__ import annotations

from fsa.core.models.result import ValidationResult, ValidationSummary
from fsa.core.models.rule import Severity
from fsa.services.package_service import merge_summaries


def _result(rule_id: str, passed: bool, errored: bool = False) -> ValidationResult:
    return ValidationResult(
        rule_id=rule_id,
        rule_name=rule_id,
        passed=passed,
        severity=Severity.ERROR,
        left_value=0.0,
        right_value=0.0,
        diff=0.0,
        tolerance=0.01,
        formula="",
        message=rule_id,
        errored=errored,
    )


def test_merge_summaries_recomputes_counts() -> None:
    """合并后统计数与结果明细一致。"""
    first = ValidationSummary(
        period="2026-06",
        total=2,
        passed=1,
        failed=1,
        results=[_result("A", True), _result("B", False)],
    )
    second = ValidationSummary(
        period="2026-06",
        total=2,
        passed=2,
        failed=0,
        results=[_result("C", True), _result("D", True, errored=True)],
    )
    merged = merge_summaries(first, second)
    assert merged.total == 4
    assert merged.passed == 3
    assert merged.failed == 1
    assert merged.errored == 1
    assert [r.rule_id for r in merged.results] == ["A", "B", "C", "D"]
