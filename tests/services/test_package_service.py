"""报表包校验服务测试。"""

from __future__ import annotations

from fsa.core.models.detail import DetailDataset
from fsa.core.models.result import ValidationResult, ValidationSummary
from fsa.core.models.rule import Severity
from fsa.services.package_service import PackageValidationService, merge_summaries
from tests.conftest import make_balance_sheet
from tests.services.conftest import make_registry, make_rule


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


def _dar_rule():
    """LR-DAR-001 资产负债率合理性规则 (阈值变量 dar_threshold)。"""
    return make_rule(
        rule_id="LR-DAR-001",
        name="资产负债率合理性",
        category="C-逻辑合理性",
        statements=["资产负债表"],
        formula="asset_total <= 0 or liability_total / asset_total <= dar_threshold",
        severity=Severity.WARNING,
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


def test_merge_summaries_dedups_rule_id_keeps_first() -> None:
    """重复 rule_id 去重: 保留先者, 统计不再失真 (P2 确定性)。"""
    first = ValidationSummary(
        period="2026-06",
        results=[
            _result("A", True),
            _result("B", False),
            _result("C", True),
        ],
    )
    second = ValidationSummary(
        period="2026-06",
        results=[
            _result("B", True),   # 与 first.B 重复, 被丢弃
            _result("C", False),  # 与 first.C 重复, 被丢弃 (保留先者 True)
            _result("E", False),
        ],
    )
    merged = merge_summaries(first, second)
    assert [r.rule_id for r in merged.results] == ["A", "B", "C", "E"]
    assert merged.total == 4
    assert merged.failed == 2          # B、E 失败, C 保留先者 True, 不再重复计数
    assert merged.passed == 2          # A、C


def test_merge_summaries_dedup_recomputes_all_counts() -> None:
    """去重后 passed/failed/errored/skipped 与去重结果一致。"""
    first = ValidationSummary(
        period="2026-06",
        results=[
            _result("A", False),
            _result("X", True, errored=True),
            _result("S", True),
        ],
    )
    second = ValidationSummary(
        period="2026-06",
        results=[
            _result("A", True),  # 重复, 丢弃
            _result("S", True, errored=True),  # 重复, 丢弃
        ],
    )
    merged = merge_summaries(first, second)
    assert [r.rule_id for r in merged.results] == ["A", "X", "S"]
    assert merged.errored == 1
    assert merged.total == 3


class TestPackageThresholdInjection:
    """PackageValidationService 将 threshold_vars 转发到主表校验。"""

    def test_validate_default_general_threshold_fails(self) -> None:
        """空明细 + 不传 threshold_vars -> general 0.85: 资产负债率 0.88 不通过。"""
        service = PackageValidationService(make_registry([_dar_rule()]))
        bs = make_balance_sheet(
            asset_total=100.0, liability_total=88.0, equity_total=12.0
        )

        summary = service.validate([bs], DetailDataset(), period="2024-12")

        dar = next(r for r in summary.results if r.rule_id == "LR-DAR-001")
        assert dar.passed is False

    def test_validate_financial_threshold_passes(self) -> None:
        """financial 阈值 0.92: 资产负债率 0.88 通过。"""
        service = PackageValidationService(make_registry([_dar_rule()]))
        bs = make_balance_sheet(
            asset_total=100.0, liability_total=88.0, equity_total=12.0
        )

        summary = service.validate(
            [bs],
            DetailDataset(),
            period="2024-12",
            threshold_vars={"dar_threshold": 0.92},
        )

        dar = next(r for r in summary.results if r.rule_id == "LR-DAR-001")
        assert dar.passed is True
