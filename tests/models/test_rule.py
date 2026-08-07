"""ReconciliationRule, ToleranceType, Severity 的单元测试。"""

from __future__ import annotations

import pytest

from fsa.core.models.rule import ReconciliationRule, Severity, ToleranceType


class TestEnums:
    """枚举值测试。"""

    def test_tolerance_type_values(self) -> None:
        assert ToleranceType.EXACT.value == "exact"
        assert ToleranceType.ABSOLUTE.value == "absolute"
        assert ToleranceType.RELATIVE.value == "relative"
        assert ToleranceType.THRESHOLD.value == "threshold"

    def test_severity_values(self) -> None:
        assert Severity.ERROR.value == "error"
        assert Severity.WARNING.value == "warning"
        assert Severity.INFO.value == "info"


class TestReconciliationRule:
    """ReconciliationRule 测试。"""

    def test_normal_construction(self) -> None:
        """正常路径。"""
        rule = ReconciliationRule(
            rule_id="BS-BAL-001",
            name="资产=负债+所有者权益",
            category="A-表内平衡",
            statements=["资产负债表"],
            formula="asset_total == liability_total + equity_total",
            tolerance_type=ToleranceType.EXACT,
            tolerance=0.01,
            severity=Severity.ERROR,
        )
        assert rule.rule_id == "BS-BAL-001"
        assert rule.tolerance == 0.01

    def test_empty_rule_id_raises(self) -> None:
        """空规则编号抛异常。"""
        with pytest.raises(ValueError, match="规则编号"):
            ReconciliationRule(
                rule_id="",
                name="test",
                category="A",
                statements=["资产负债表"],
                formula="a == b",
                tolerance_type=ToleranceType.EXACT,
                tolerance=0.01,
                severity=Severity.ERROR,
            )

    def test_empty_formula_raises(self) -> None:
        """空公式抛异常。"""
        with pytest.raises(ValueError, match="公式"):
            ReconciliationRule(
                rule_id="TEST-001",
                name="test",
                category="A",
                statements=["资产负债表"],
                formula="",
                tolerance_type=ToleranceType.EXACT,
                tolerance=0.01,
                severity=Severity.ERROR,
            )

    def test_negative_tolerance_raises(self) -> None:
        """负容差抛异常。"""
        with pytest.raises(ValueError, match="容差"):
            ReconciliationRule(
                rule_id="TEST-001",
                name="test",
                category="A",
                statements=["资产负债表"],
                formula="a == b",
                tolerance_type=ToleranceType.EXACT,
                tolerance=-0.01,
                severity=Severity.ERROR,
            )

    def test_zero_tolerance_succeeds(self) -> None:
        """零容差: 精确匹配。"""
        rule = ReconciliationRule(
            rule_id="TEST-001",
            name="test",
            category="A",
            statements=["资产负债表"],
            formula="a == b",
            tolerance_type=ToleranceType.EXACT,
            tolerance=0.0,
            severity=Severity.ERROR,
        )
        assert rule.tolerance == 0.0

    def test_default_optional_fields(self) -> None:
        """可选字段默认值。"""
        rule = ReconciliationRule(
            rule_id="TEST-001",
            name="test",
            category="A",
            statements=["资产负债表"],
            formula="a == b",
            tolerance_type=ToleranceType.EXACT,
            tolerance=0.01,
            severity=Severity.ERROR,
        )
        assert rule.cas_ref == ""
        assert rule.notes == ""

    def test_frozen_immutable(self) -> None:
        """frozen=True: 不可变。"""
        rule = ReconciliationRule(
            rule_id="TEST-001",
            name="test",
            category="A",
            statements=["资产负债表"],
            formula="a == b",
            tolerance_type=ToleranceType.EXACT,
            tolerance=0.01,
            severity=Severity.ERROR,
        )
        with pytest.raises(AttributeError):
            rule.tolerance = 0.5  # type: ignore[misc]
