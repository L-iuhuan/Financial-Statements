"""行业阈值参数化测试 (P1#8)。

验证:
- entity_config.industry 字段与阈值映射 (load_entity_configs 解析)
- runner 求值前注入行业阈值变量, 改变阈值规则判定结果
- 默认 general 行为与现状一致 (回归不破)
- 未知行业回落 general (P1: 保守)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fsa.core.engine.registry import RuleRegistry
from fsa.core.engine.runner import RuleRunner
from fsa.core.engine.thresholds import (
    DEFAULT_THRESHOLDS,
    INDUSTRY_THRESHOLD_RULES,
    KNOWN_INDUSTRIES,
    threshold_vars_for,
)
from fsa.core.models.report import Report, ReportItem, ReportType
from fsa.core.models.result import ValidationContext
from fsa.services.entity_config import EntityConfig, load_entity_configs

RULE_LIBRARY = (
    Path(__file__).resolve().parent.parent.parent / "cas_gouji_rule_library.json"
)


def _registry() -> RuleRegistry:
    return RuleRegistry.from_json(RULE_LIBRARY)


def _item(key: str, amount: float, beginning: float | None = None) -> ReportItem:
    return ReportItem(key=key, name=key, amount=amount, beginning_amount=beginning)


def _context(*reports: Report) -> ValidationContext:
    ctx = ValidationContext(period="2024-12")
    for report in reports:
        ctx.add_report(report)
    return ctx


def _bs(
    asset_total: float | None = None,
    liability_total: float | None = None,
    current_assets: float | None = None,
    current_liabilities: float | None = None,
    accounts_receivable: float | None = None,
) -> Report:
    items = []
    if asset_total is not None:
        items.append(_item("asset_total", asset_total))
    if liability_total is not None:
        items.append(_item("liability_total", liability_total))
    if current_assets is not None:
        items.append(_item("current_assets", current_assets))
    if current_liabilities is not None:
        items.append(_item("current_liabilities", current_liabilities))
    if accounts_receivable is not None:
        items.append(_item("accounts_receivable", accounts_receivable))
    return Report(report_type=ReportType.BALANCE_SHEET, period="2024-12", items=items)


def _is(
    revenue: float | None = None,
    operating_cost: float | None = None,
    revenue_beginning: float | None = None,
    operating_cost_beginning: float | None = None,
) -> Report:
    items: list[ReportItem] = []
    if revenue is not None:
        beginning = revenue_beginning if revenue_beginning is not None else None
        items.append(_item("revenue", revenue, beginning=beginning))
    if operating_cost is not None:
        beginning = (
            operating_cost_beginning if operating_cost_beginning is not None else None
        )
        items.append(_item("operating_cost", operating_cost, beginning=beginning))
    return Report(report_type=ReportType.INCOME_STATEMENT, period="2024-12", items=items)


def _cf(cash_received_from_sales: float) -> Report:
    return Report(
        report_type=ReportType.CASH_FLOW_STATEMENT,
        period="2024-12",
        items=[_item("cash_received_from_sales", cash_received_from_sales)],
    )


class TestEntityConfigIndustry:
    """entity_config.industry 字段与阈值映射。"""

    def test_default_industry_is_general(self) -> None:
        config = EntityConfig(entity_id="主体A")
        assert config.industry == "general"
        assert config.threshold_vars() == DEFAULT_THRESHOLDS

    def test_industry_loaded_from_json(self, tmp_path: Path) -> None:
        path = tmp_path / "configs.json"
        path.write_text(
            '{"entities": {"建筑公司": {"industry": "construction", '
            '"tolerance": 0.02}}}',
            encoding="utf-8",
        )
        configs = load_entity_configs(path)
        config = configs["建筑公司"]
        assert config.industry == "construction"
        assert config.tolerance == 0.02
        assert config.threshold_vars()["ar_to_revenue_threshold"] == 0.60

    def test_financial_threshold_vars(self) -> None:
        config = EntityConfig(entity_id="银行", industry="financial")
        assert config.threshold_vars()["dar_threshold"] == 0.92

    def test_unknown_industry_falls_back_to_general(self) -> None:
        config = EntityConfig(entity_id="未知", industry="不存在的行业")
        assert config.threshold_vars() == DEFAULT_THRESHOLDS

    def test_known_industries_defined(self) -> None:
        assert "general" in KNOWN_INDUSTRIES
        assert set(INDUSTRY_THRESHOLD_RULES) >= {
            "LR-DAR-001",
            "LR-GM-002",
            "LR-ART-001",
            "LR-FLUC-001",
            "LR-SALES-001",
            "LR-QUICK-001",
        }


class TestDefaultGeneralRegression:
    """默认 general 行为与现状一致 (回归不破)。"""

    def test_dar_088_default_fails(self) -> None:
        """general 资产负债率 0.88 > 0.85 -> 不通过。"""
        rule = _registry().get_by_id("LR-DAR-001")
        assert rule is not None
        ctx = _context(_bs(asset_total=100.0, liability_total=88.0))
        result = RuleRunner.run(rule, ctx)
        assert result.passed is False

    def test_default_equals_general_threshold_vars(self) -> None:
        """不带 threshold_vars 与带 general 阈值结果一致。"""
        rule = _registry().get_by_id("LR-DAR-001")
        assert rule is not None
        ctx = _context(_bs(asset_total=100.0, liability_total=88.0))
        default = RuleRunner.run(rule, ctx)
        general = RuleRunner.run(rule, ctx, threshold_vars_for("general"))
        assert default.passed == general.passed
        assert default.passed is False


class TestIndustryThresholdBehavior:
    """每个行业阈值至少一个用例。"""

    def test_lr_dar_financial_088_passes_general_fails(self) -> None:
        """资产负债率 0.88: financial 不报警, general 报警。"""
        rule = _registry().get_by_id("LR-DAR-001")
        assert rule is not None
        ctx = _context(_bs(asset_total=100.0, liability_total=88.0))
        assert RuleRunner.run(rule, ctx).passed is False
        assert RuleRunner.run(rule, ctx, threshold_vars_for("financial")).passed is True

    def test_lr_dar_real_estate_091_fails(self) -> None:
        """资产负债率 0.91: real_estate (0.85) 报警, 与 financial 区分。"""
        rule = _registry().get_by_id("LR-DAR-001")
        assert rule is not None
        ctx = _context(_bs(asset_total=100.0, liability_total=91.0))
        assert RuleRunner.run(rule, ctx, threshold_vars_for("real_estate")).passed is False

    def test_lr_dar_construction_079_passes(self) -> None:
        """资产负债率 0.79: construction (0.80) 不报警。"""
        rule = _registry().get_by_id("LR-DAR-001")
        assert rule is not None
        ctx = _context(_bs(asset_total=100.0, liability_total=79.0))
        assert RuleRunner.run(rule, ctx, threshold_vars_for("construction")).passed is True

    def test_lr_dar_retail_074_passes(self) -> None:
        """资产负债率 0.74: retail (0.75) 不报警。"""
        rule = _registry().get_by_id("LR-DAR-001")
        assert rule is not None
        ctx = _context(_bs(asset_total=100.0, liability_total=74.0))
        assert RuleRunner.run(rule, ctx, threshold_vars_for("retail")).passed is True

    def test_lr_gm_yoy_cyclical(self) -> None:
        """毛利率同比波动 0.40: general (0.30) 报警, cyclical (0.50) 不报警。"""
        rule = _registry().get_by_id("LR-GM-002")
        assert rule is not None
        # 本期毛利 0.5, 上期毛利 0.1 -> 波动 0.40
        ctx = _context(
            _is(
                revenue=100.0,
                operating_cost=50.0,
                revenue_beginning=100.0,
                operating_cost_beginning=90.0,
            )
        )
        assert RuleRunner.run(rule, ctx).passed is False
        assert RuleRunner.run(rule, ctx, threshold_vars_for("cyclical")).passed is True

    def test_lr_art_construction(self) -> None:
        """应收/营收 0.45: general (0.30) 报警, construction (0.60) 不报警。"""
        rule = _registry().get_by_id("LR-ART-001")
        assert rule is not None
        ctx = _context(_bs(accounts_receivable=45.0), _is(revenue=100.0))
        assert RuleRunner.run(rule, ctx).passed is False
        assert RuleRunner.run(rule, ctx, threshold_vars_for("construction")).passed is True

    def test_lr_fluc_high_growth(self) -> None:
        """收入同比波动 0.40: general (0.30) 报警, high_growth (0.50) 不报警。"""
        rule = _registry().get_by_id("LR-FLUC-001")
        assert rule is not None
        ctx = _context(_is(revenue=140.0, revenue_beginning=100.0))
        assert RuleRunner.run(rule, ctx).passed is False
        assert RuleRunner.run(rule, ctx, threshold_vars_for("high_growth")).passed is True

    def test_lr_sales_construction(self) -> None:
        """销售收现比 0.60: general (0.8) 报警, construction (0.5) 不报警。"""
        rule = _registry().get_by_id("LR-SALES-001")
        assert rule is not None
        ctx = _context(_is(revenue=100.0), _cf(cash_received_from_sales=60.0))
        assert RuleRunner.run(rule, ctx).passed is False
        assert RuleRunner.run(rule, ctx, threshold_vars_for("construction")).passed is True

    def test_lr_quick_retail(self) -> None:
        """流动比率 0.85: general (1.0) 报警, retail (0.7) 不报警。"""
        rule = _registry().get_by_id("LR-QUICK-001")
        assert rule is not None
        ctx = _context(_bs(current_assets=85.0, current_liabilities=100.0))
        assert RuleRunner.run(rule, ctx).passed is False
        assert RuleRunner.run(rule, ctx, threshold_vars_for("retail")).passed is True


class TestRunnerInjection:
    """runner 注入行为。"""

    def test_partial_override_keeps_general_defaults(self) -> None:
        """仅覆写 dar_threshold, 其余阈值回落 general 默认。"""
        rule = _registry().get_by_id("LR-QUICK-001")
        assert rule is not None
        ctx = _context(_bs(current_assets=85.0, current_liabilities=100.0))
        # 只传 dar_threshold 覆写, current_ratio_threshold 仍为 general 1.0
        result = RuleRunner.run(rule, ctx, {"dar_threshold": 0.92})
        assert result.passed is False

    def test_trace_shows_injected_threshold(self) -> None:
        """trace 中阈值变量展示实际注入值 (可审计 P3)。"""
        rule = _registry().get_by_id("LR-DAR-001")
        assert rule is not None
        ctx = _context(_bs(asset_total=100.0, liability_total=88.0))
        result = RuleRunner.run(rule, ctx, threshold_vars_for("financial"))
        trace = {t.key: t.amount for t in result.trace}
        assert trace["dar_threshold"] == pytest.approx(0.92)

    def test_threshold_message_shows_resolved_value(self) -> None:
        """不通过消息中阈值变量替换为实际数值 (面向财务用户)。"""
        rule = _registry().get_by_id("LR-DAR-001")
        assert rule is not None
        ctx = _context(_bs(asset_total=100.0, liability_total=85.0))
        result = RuleRunner.run(rule, ctx, threshold_vars_for("construction"))
        assert result.passed is False
        assert "0.8" in result.message
        assert "dar_threshold" not in result.message
