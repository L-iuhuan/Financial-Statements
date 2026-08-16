"""SCE-BS-001~005 规则测试: 权益变动表各组成与资产负债表勾稽。

覆盖场景 (每条规则):
- 正常通过: 权益变动表年末余额 = 资产负债表余额
- 不一致报警: 两表余额不一致 -> 不通过
- 缺数据跳过: 权益变动表未导入 / 缺该变量 -> 跳过 (P1)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fsa.core.engine.registry import RuleRegistry
from fsa.core.exceptions import EvaluationError
from fsa.core.models.report import Report, ReportItem, ReportType
from fsa.core.models.result import ValidationContext
from fsa.core.models.rule import ReconciliationRule
from fsa.services.validation_service import ValidationService

RULE_LIBRARY = (
    Path(__file__).resolve().parent.parent.parent / "cas_gouji_rule_library.json"
)

# 规则ID -> (权益变动表变量, 资产负债表变量)
SCE_BS_RULES: dict[str, tuple[str, str]] = {
    "SCE-BS-001": ("sce_paid_in_capital_ending", "paid_in_capital"),
    "SCE-BS-002": ("sce_capital_reserve_ending", "capital_reserve"),
    "SCE-BS-003": ("sce_surplus_reserve_ending", "surplus_reserve"),
    "SCE-BS-004": ("sce_undistributed_profit_ending", "undistributed_profit"),
    "SCE-BS-005": ("sce_equity_total_ending", "equity_total"),
}


def _rule(rule_id: str) -> ReconciliationRule:
    registry = RuleRegistry.from_json(RULE_LIBRARY)
    rule = registry.get_by_id(rule_id)
    assert rule is not None
    return rule


def _bs(bs_items: dict[str, float]) -> Report:
    return Report(
        report_type=ReportType.BALANCE_SHEET,
        period="2024-12",
        items=[ReportItem(key=k, name=k, amount=v) for k, v in bs_items.items()],
    )


def _sce(sce_items: dict[str, float]) -> Report:
    return Report(
        report_type=ReportType.STATEMENT_OF_CHANGES_IN_EQUITY,
        period="2024-12",
        items=[ReportItem(key=k, name=k, amount=v) for k, v in sce_items.items()],
    )


class TestSceBsRules:
    """SCE-BS-001~005 勾稽规则。"""

    @pytest.mark.parametrize(
        "rule_id,sce_key,bs_key",
        [
            (rule_id, sce_key, bs_key)
            for rule_id, (sce_key, bs_key) in SCE_BS_RULES.items()
        ],
    )
    def test_equal_balances_pass(
        self, rule_id: str, sce_key: str, bs_key: str
    ) -> None:
        """权益变动表余额 = 资产负债表余额 -> 通过。"""
        from fsa.core.engine.runner import RuleRunner

        ctx = ValidationContext(period="2024-12")
        ctx.add_report(_sce({sce_key: 100.0}))
        ctx.add_report(_bs({bs_key: 100.0}))
        result = RuleRunner.run(_rule(rule_id), ctx)
        assert result.passed is True

    @pytest.mark.parametrize(
        "rule_id,sce_key,bs_key",
        [
            (rule_id, sce_key, bs_key)
            for rule_id, (sce_key, bs_key) in SCE_BS_RULES.items()
        ],
    )
    def test_mismatch_fails(
        self, rule_id: str, sce_key: str, bs_key: str
    ) -> None:
        """两表余额不一致 (差额10) -> 不通过。"""
        from fsa.core.engine.runner import RuleRunner

        ctx = ValidationContext(period="2024-12")
        ctx.add_report(_sce({sce_key: 100.0}))
        ctx.add_report(_bs({bs_key: 90.0}))
        result = RuleRunner.run(_rule(rule_id), ctx)
        assert result.passed is False
        assert result.diff == pytest.approx(10.0)

    @pytest.mark.parametrize(
        "rule_id,sce_key,bs_key",
        [
            (rule_id, sce_key, bs_key)
            for rule_id, (sce_key, bs_key) in SCE_BS_RULES.items()
        ],
    )
    def test_missing_sce_report_skipped(
        self, rule_id: str, sce_key: str, bs_key: str
    ) -> None:
        """权益变动表未导入 -> 规则不适用, 跳过 (不计入执行)。"""
        service = ValidationService(RuleRegistry([_rule(rule_id)]))
        summary = service.validate([_bs({bs_key: 100.0})], period="2024-12")
        assert summary.total == 0
        assert summary.skipped == 1

    @pytest.mark.parametrize(
        "rule_id,sce_key,bs_key",
        [
            (rule_id, sce_key, bs_key)
            for rule_id, (sce_key, bs_key) in SCE_BS_RULES.items()
        ],
    )
    def test_missing_sce_variable_skipped(
        self, rule_id: str, sce_key: str, bs_key: str
    ) -> None:
        """权益变动表已导入但缺少该组成变量 -> 跳过 (P1 不误报)。"""
        service = ValidationService(RuleRegistry([_rule(rule_id)]))
        # 权益变动表不含该变量 (仅含无关变量)
        sce = _sce({f"unrelated_{sce_key}": 100.0})
        summary = service.validate([sce, _bs({bs_key: 100.0})], period="2024-12")
        result = next(
            (r for r in summary.results if r.rule_id == rule_id),
            None,
        )
        assert result is not None
        assert result.skipped is True

    def test_runner_raises_on_missing_sce_variable(self) -> None:
        """runner 层: 缺少 sce_* 变量时抛出 EvaluationError。"""
        from fsa.core.engine.runner import RuleRunner

        ctx = ValidationContext(period="2024-12")
        ctx.add_report(_sce({"sce_paid_in_capital_ending": 100.0}))
        ctx.add_report(_bs({"paid_in_capital": 100.0}))
        # SCE-BS-002 需要 sce_capital_reserve_ending, 缺失
        with pytest.raises(EvaluationError):
            RuleRunner.run(_rule("SCE-BS-002"), ctx)
