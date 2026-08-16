"""SCE-IS-001/002 规则 E2E 测试（归母口径修复）。

SCE-IS-001: 权益变动表'未分配利润'列'综合收益总额'栏 == 归母净利润。
- 合并报表: 取利润表「归属于母公司所有者的净利润」(net_profit_parent)
- 单体报表: 无归母行, 回退取净利润 (net_profit, 单体净利润=归母)
SCE-IS-002: 归母 OCI 无映射来源, 维持 warning 提示级。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fsa.core.engine.rule_loader import load_rules_from_json
from fsa.core.engine.runner import RuleRunner
from fsa.core.exceptions import EvaluationError
from fsa.core.models.report import Report, ReportItem, ReportType
from fsa.core.models.result import ValidationContext
from fsa.core.models.rule import ReconciliationRule, Severity

RULE_LIBRARY = (
    Path(__file__).resolve().parent.parent.parent / "cas_gouji_rule_library.json"
)


def _load_rule(rule_id: str) -> ReconciliationRule:
    rules = {r.rule_id: r for r in load_rules_from_json(RULE_LIBRARY)}
    return rules[rule_id]


def _sce_report(
    undistributed_comprehensive: float, oci_comprehensive: float = 0.0
) -> Report:
    return Report(
        report_type=ReportType.STATEMENT_OF_CHANGES_IN_EQUITY,
        period="2024-12",
        items=[
            ReportItem(
                key="sce_undistributed_profit_comprehensive",
                name="未分配利润(综合收益总额)",
                amount=undistributed_comprehensive,
                row=5,
                column="未分配利润",
            ),
            ReportItem(
                key="sce_other_comprehensive_comprehensive",
                name="其他综合收益(综合收益总额)",
                amount=oci_comprehensive,
                row=5,
                column="其他综合收益",
            ),
        ],
    )


def _income_statement(
    net_profit: float | None,
    net_profit_parent: float | None = None,
) -> Report:
    items: list[ReportItem] = []
    if net_profit is not None:
        items.append(
            ReportItem(
                key="net_profit", name="净利润", amount=net_profit, row=30, column="本期金额"
            )
        )
    if net_profit_parent is not None:
        items.append(
            ReportItem(
                key="net_profit_parent",
                name="归属于母公司所有者的净利润",
                amount=net_profit_parent,
                row=31,
                column="本期金额",
            )
        )
    return Report(
        report_type=ReportType.INCOME_STATEMENT, period="2024-12", items=items
    )


def _context(sce: Report, income: Report) -> ValidationContext:
    ctx = ValidationContext(period="2024-12")
    ctx.add_report(sce)
    ctx.add_report(income)
    return ctx


class TestSceIs001AttributableNetProfit:
    """SCE-IS-001 归母口径: 单体回退 net_profit, 合并取 net_profit_parent。"""

    def test_standalone_uses_net_profit_passes(self) -> None:
        """单体场景: 无归母行, SCE 综合收益=净利润 -> 通过, severity 回 error。"""
        rule = _load_rule("SCE-IS-001")
        ctx = _context(_sce_report(100.0), _income_statement(net_profit=100.0))
        result = RuleRunner.run(rule, ctx)
        assert result.passed is True
        assert result.severity is Severity.ERROR

    def test_standalone_mismatch_fails(self) -> None:
        """单体场景: SCE 综合收益≠净利润 -> 不通过 (error)。"""
        rule = _load_rule("SCE-IS-001")
        ctx = _context(_sce_report(100.0), _income_statement(net_profit=90.0))
        result = RuleRunner.run(rule, ctx)
        assert result.passed is False
        assert result.severity is Severity.ERROR

    def test_consolidated_uses_parent_net_profit_passes(self) -> None:
        """合并场景: 归母 80 / 合计 100, SCE 归母口径 80 -> 通过 (取归母而非合计)。"""
        rule = _load_rule("SCE-IS-001")
        ctx = _context(
            _sce_report(80.0),
            _income_statement(net_profit=100.0, net_profit_parent=80.0),
        )
        result = RuleRunner.run(rule, ctx)
        assert result.passed is True

    def test_consolidated_equal_to_total_fails(self) -> None:
        """合并场景反证: SCE=合计净利润 100 ≠ 归母 80 -> 不通过 (证明取归母)。"""
        rule = _load_rule("SCE-IS-001")
        ctx = _context(
            _sce_report(100.0),
            _income_statement(net_profit=100.0, net_profit_parent=80.0),
        )
        result = RuleRunner.run(rule, ctx)
        assert result.passed is False

    def test_missing_all_sources_skips(self) -> None:
        """归母行与净利润均无真实数据 -> 变量缺失, 抛 EvaluationError 走 skip (P1)。"""
        rule = _load_rule("SCE-IS-001")
        ctx = _context(_sce_report(100.0), _income_statement(net_profit=None))
        with pytest.raises(EvaluationError):
            RuleRunner.run(rule, ctx)

    def test_trace_points_to_parent_item(self) -> None:
        """合并场景 trace: net_profit_attributable 溯源到归母行 (名称/行号)。"""
        rule = _load_rule("SCE-IS-001")
        ctx = _context(
            _sce_report(80.0),
            _income_statement(net_profit=100.0, net_profit_parent=80.0),
        )
        result = RuleRunner.run(rule, ctx)
        trace = [t for t in result.trace if t.key == "net_profit_attributable"]
        assert len(trace) == 1
        assert trace[0].name == "归属于母公司所有者的净利润"
        assert trace[0].amount == 80.0
        assert trace[0].row == 31

    def test_trace_points_to_net_profit_when_standalone(self) -> None:
        """单体场景 trace: net_profit_attributable 溯源到净利润行。"""
        rule = _load_rule("SCE-IS-001")
        ctx = _context(_sce_report(100.0), _income_statement(net_profit=100.0))
        result = RuleRunner.run(rule, ctx)
        trace = [t for t in result.trace if t.key == "net_profit_attributable"]
        assert len(trace) == 1
        assert trace[0].name == "净利润"
        assert trace[0].amount == 100.0


class TestSceIs002StaysWarning:
    """SCE-IS-002: 归母 OCI 无映射来源, 维持 warning 并在 notes 注明。"""

    def test_severity_remains_warning(self) -> None:
        rule = _load_rule("SCE-IS-002")
        assert rule.severity is Severity.WARNING
        assert "归母 OCI" in rule.notes
        assert "无" in rule.notes and "映射" in rule.notes

    def test_matching_oci_passes(self) -> None:
        """OCI 一致 -> 通过。"""
        rule = _load_rule("SCE-IS-002")
        sce = _sce_report(0.0, oci_comprehensive=5.0)
        income = _income_statement(net_profit=100.0)
        income.add_item(
            ReportItem(
                key="other_comprehensive_income_after_tax",
                name="其他综合收益的税后净额",
                amount=5.0,
                row=40,
                column="本期金额",
            )
        )
        result = RuleRunner.run(rule, _context(sce, income))
        assert result.passed is True
