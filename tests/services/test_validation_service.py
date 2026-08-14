"""ValidationService 测试: 端到端校验编排。

测试覆盖:
- 单规则: 通过/不通过/零值/大数
- 报表缺失: 跳过规则
- 异常处理: 缺失变量/公式错误
- 多规则: 混合结果
- 注册表交互: 禁用规则
- 跨表规则: 两侧齐全/一侧缺失
- 汇总属性: success_rate / all_passed / failed_results
"""

from __future__ import annotations

from fsa.core.models.report import Report, ReportType
from fsa.core.models.rule import ReconciliationRule, Severity, ToleranceType
from fsa.services.validation_service import ValidationService
from tests.conftest import make_balance_sheet, make_item, make_rule_bs_bal_001
from tests.services.conftest import (
    make_income_statement,
    make_registry,
    make_rule,
)

# ────────────────────── 单规则场景 ──────────────────────


class TestSingleRule:
    """单规则场景。"""

    def test_validate_passing_rule_returns_passed(self):
        """资产=负债+权益, 100=60+40 -> 通过。"""
        bs = make_balance_sheet(100.0, 60.0, 40.0)
        service = ValidationService(make_registry([make_rule_bs_bal_001()]))

        summary = service.validate([bs], period="2024-12")

        assert summary.total == 1
        assert summary.passed == 1
        assert summary.failed == 0
        assert summary.errored == 0
        assert summary.skipped == 0
        assert summary.all_passed is True

    def test_validate_failing_rule_returns_failed(self):
        """资产=100, 负债+权益=90 -> 不通过。"""
        bs = make_balance_sheet(100.0, 60.0, 30.0)
        service = ValidationService(make_registry([make_rule_bs_bal_001()]))

        summary = service.validate([bs])

        assert summary.total == 1
        assert summary.passed == 0
        assert summary.failed == 1
        assert summary.all_passed is False

    def test_validate_zero_values_passes(self):
        """全部为0 -> 通过 (0==0+0)。"""
        bs = make_balance_sheet(0.0, 0.0, 0.0)
        service = ValidationService(make_registry([make_rule_bs_bal_001()]))

        summary = service.validate([bs])

        assert summary.passed == 1

    def test_validate_large_numbers_correct(self):
        """1e15 级别 -> 正确计算。"""
        bs = make_balance_sheet(1e15, 6e14, 4e14)
        service = ValidationService(make_registry([make_rule_bs_bal_001()]))

        summary = service.validate([bs])

        assert summary.passed == 1

    def test_validate_negative_values_correct(self):
        """负数金额 -> 正确计算。"""
        bs = make_balance_sheet(-100.0, -60.0, -40.0)
        service = ValidationService(make_registry([make_rule_bs_bal_001()]))

        summary = service.validate([bs])

        assert summary.passed == 1

    def test_validate_floating_point_tolerance(self):
        """浮点精度: 0.1+0.2 != 0.3 但容差内通过。"""
        bs = make_balance_sheet(0.3, 0.1, 0.2)
        service = ValidationService(make_registry([make_rule_bs_bal_001()]))

        summary = service.validate([bs])

        assert summary.passed == 1


# ────────────────────── 报表缺失 ──────────────────────


class TestMissingReport:
    """所需报表未导入时跳过规则。"""

    def test_validate_missing_report_type_skips_rule(self):
        """规则需要利润表, 但只导入资产负债表 -> 跳过。"""
        is_rule = make_rule(
            rule_id="IS-BAL-001",
            name="收入-成本=利润",
            statements=["利润表"],
            formula="revenue - expenses == net_profit",
        )
        bs = make_balance_sheet(100.0, 60.0, 40.0)
        service = ValidationService(make_registry([is_rule]))

        summary = service.validate([bs])

        assert summary.total == 0
        assert summary.skipped == 1
        assert summary.passed == 0
        assert summary.failed == 0

    def test_validate_empty_reports_all_skipped(self):
        """无报表 -> 所有规则跳过。"""
        service = ValidationService(make_registry([make_rule_bs_bal_001()]))

        summary = service.validate([])

        assert summary.total == 0
        assert summary.skipped == 1
        assert summary.all_passed is True

    def test_validate_cross_statement_rule_one_missing_skipped(self):
        """跨表规则需要 BS+IS, 只有 BS -> 跳过。"""
        cross_rule = make_rule(
            rule_id="BS-IS-001",
            name="期末权益=期初权益+净利润",
            statements=["资产负债表", "利润表"],
            formula="equity_total == net_profit",
        )
        bs = make_balance_sheet(equity_total=40.0)
        service = ValidationService(make_registry([cross_rule]))

        summary = service.validate([bs])

        assert summary.total == 0
        assert summary.skipped == 1


# ────────────────────── 异常处理 ──────────────────────


class TestErrorHandling:
    """规则执行异常时记录为 errored 或 skipped。"""

    def test_validate_rule_with_missing_variable_defaults_zero_fails(self):
        """报表缺少 liability_total -> 预填充为 0，公式 100 != 0+0 -> 不通过。

        build_namespace 将已知科目预填充为 0，
        缺失的 liability_total 默认 0，公式求值 100 == 0 不成立。
        """
        bs = Report(
            report_type=ReportType.BALANCE_SHEET,
            period="2024-12",
            items=[make_item("asset_total", "资产总计", 100.0)],
        )
        service = ValidationService(make_registry([make_rule_bs_bal_001()]))

        summary = service.validate([bs])

        assert summary.total == 1
        assert summary.errored == 0
        assert summary.passed == 0
        assert summary.failed == 1
        assert summary.skipped == 0
        assert summary.all_passed is False

    def test_validate_rule_with_bad_formula_returns_errored(self):
        """公式语法错误 -> errored。"""
        bad_rule = make_rule(
            rule_id="BAD-001",
            name="错误公式",
            formula="asset_total ==@@@",
        )
        bs = make_balance_sheet(100.0, 60.0, 40.0)
        service = ValidationService(make_registry([bad_rule]))

        summary = service.validate([bs])

        assert summary.errored == 1

    def test_validate_missing_variable_evaluates_not_skipped(self):
        """缺少变量的规则会预填充 0 并求值，不标记为 skipped。"""
        bs = Report(
            report_type=ReportType.BALANCE_SHEET,
            items=[make_item("asset_total", "资产总计", 100.0)],
        )
        service = ValidationService(make_registry([make_rule_bs_bal_001()]))

        summary = service.validate([bs])

        assert len(summary.results) == 1
        assert summary.results[0].skipped is False
        assert summary.results[0].errored is False
        assert summary.results[0].passed is False


# ────────────────────── 相对容差基准为 0 ──────────────────────


class TestRelativeBaseZero:
    """相对容差规则: 基准值为 0 时按 P1 跳过而非计为异常。"""

    @staticmethod
    def _relative_rule(rule_id: str = "RL-001") -> ReconciliationRule:
        """净利润=营业收入, 相对容差。"""
        return make_rule(
            rule_id=rule_id,
            name="净利润=营业收入",
            statements=["利润表"],
            formula="net_profit == revenue",
            tolerance_type=ToleranceType.RELATIVE,
            tolerance=0.3,
        )

    def test_validate_relative_base_zero_left_nonzero_skips(self):
        """基准值为0且左值非0 -> 跳过 (passed=True, skipped=True, errored=False)。"""
        is_ = make_income_statement(revenue=0.0, net_profit=100.0)
        service = ValidationService(make_registry([self._relative_rule()]))

        summary = service.validate([is_])

        result = summary.results[0]
        assert result.skipped is True
        assert result.errored is False
        assert result.passed is True
        assert "基准科目金额为 0" in result.message
        assert "跳过" in result.message

    def test_validate_relative_base_zero_both_zero_passes(self):
        """基准值为0且左右均为0 -> 通过 (既有行为回归)。"""
        is_ = make_income_statement(revenue=0.0, net_profit=0.0)
        service = ValidationService(make_registry([self._relative_rule()]))

        summary = service.validate([is_])

        result = summary.results[0]
        assert result.passed is True
        assert result.skipped is False
        assert result.errored is False

    def test_validate_relative_base_zero_counts_as_skipped(self):
        """跳过计入 summary.skipped, 不计入 total/errored。"""
        is_ = make_income_statement(revenue=0.0, net_profit=100.0)
        service = ValidationService(make_registry([self._relative_rule()]))

        summary = service.validate([is_])

        assert summary.skipped == 1
        assert summary.total == 0
        assert summary.errored == 0
        assert summary.failed == 0

    def test_validate_duplicate_variable_returns_errored(self):
        """其他运行期异常 (重复变量) -> errored 而非跳过 (既有行为回归)。

        相对容差基准为 0 已改为跳过, 但其余可预期异常仍应计为 errored。
        """
        dup_rule = make_rule(
            rule_id="DUP-001",
            name="跨表净利润一致",
            statements=["资产负债表", "利润表"],
            formula="net_profit == net_profit",
        )
        bs = Report(
            report_type=ReportType.BALANCE_SHEET,
            period="2024-12",
            items=[
                make_item("asset_total", "资产总计", 100.0),
                make_item("net_profit", "净利润", 50.0),
            ],
        )
        is_ = make_income_statement(revenue=0.0, net_profit=100.0)
        service = ValidationService(make_registry([dup_rule]))

        summary = service.validate([bs, is_])

        assert len(summary.results) == 1
        assert summary.results[0].errored is True
        assert summary.results[0].skipped is False
        assert summary.errored == 1


# ────────────────────── 多规则 ──────────────────────


class TestMultipleRules:
    """多规则场景。"""

    def test_validate_multiple_rules_mixed_results(self):
        """两条规则, 一通过一不通过。"""
        pass_rule = make_rule_bs_bal_001()
        fail_rule = make_rule(
            rule_id="BS-BAL-002",
            name="流动资产+非流动资产=资产总计",
            formula="current_assets + non_current_assets == asset_total",
        )
        bs = make_balance_sheet(
            asset_total=100.0,
            liability_total=60.0,
            equity_total=40.0,
            current_assets=70.0,
            non_current_assets=20.0,  # 70+20=90 != 100
        )
        service = ValidationService(make_registry([pass_rule, fail_rule]))

        summary = service.validate([bs])

        assert summary.total == 2
        assert summary.passed == 1
        assert summary.failed == 1

    def test_validate_all_rules_pass(self):
        """所有规则通过。"""
        rule1 = make_rule_bs_bal_001()
        rule2 = make_rule(
            rule_id="BS-BAL-002",
            name="流动+非流动=资产",
            formula="current_assets + non_current_assets == asset_total",
        )
        bs = make_balance_sheet(
            asset_total=100.0,
            liability_total=60.0,
            equity_total=40.0,
            current_assets=70.0,
            non_current_assets=30.0,
        )
        service = ValidationService(make_registry([rule1, rule2]))

        summary = service.validate([bs])

        assert summary.all_passed is True
        assert summary.passed == 2

    def test_validate_all_rules_fail(self):
        """所有规则不通过。"""
        rule1 = make_rule_bs_bal_001()
        rule2 = make_rule(
            rule_id="BS-BAL-002",
            name="流动+非流动=资产",
            formula="current_assets + non_current_assets == asset_total",
        )
        bs = make_balance_sheet(
            asset_total=100.0,
            liability_total=50.0,
            equity_total=30.0,  # 50+30=80 != 100
            current_assets=60.0,
            non_current_assets=20.0,  # 60+20=80 != 100
        )
        service = ValidationService(make_registry([rule1, rule2]))

        summary = service.validate([bs])

        assert summary.failed == 2
        assert summary.passed == 0


# ────────────────────── 跨表规则 ──────────────────────


class TestCrossStatement:
    """跨表勾稽规则。"""

    def test_validate_cross_statement_both_present_runs(self):
        """跨表规则, 两张报表都有 -> 执行。"""
        cross_rule = make_rule(
            rule_id="BS-IS-001",
            name="净利润计入权益",
            statements=["资产负债表", "利润表"],
            formula="equity_total == net_profit",
        )
        bs = make_balance_sheet(equity_total=50.0)
        is_ = make_income_statement(net_profit=50.0)
        service = ValidationService(make_registry([cross_rule]))

        summary = service.validate([bs, is_])

        assert summary.total == 1
        assert summary.passed == 1
        assert ReportType.BALANCE_SHEET in summary.report_types
        assert ReportType.INCOME_STATEMENT in summary.report_types


# ────────────────────── 注册表交互 ──────────────────────


class TestRegistryInteraction:
    """与 RuleRegistry 的交互。"""

    def test_validate_disabled_rule_not_counted(self):
        """禁用的规则不参与校验。"""
        registry = make_registry([make_rule_bs_bal_001()])
        registry.disable("BS-BAL-001")
        bs = make_balance_sheet(100.0, 60.0, 40.0)
        service = ValidationService(registry)

        summary = service.validate([bs])

        assert summary.total == 0
        assert summary.skipped == 0  # disabled is not skipped, just not present

    def test_validate_empty_registry_returns_empty_summary(self):
        """空注册表 -> 空汇总。"""
        service = ValidationService(make_registry([]))
        bs = make_balance_sheet(100.0, 60.0, 40.0)

        summary = service.validate([bs])

        assert summary.total == 0
        assert summary.passed == 0
        assert summary.all_passed is True


# ────────────────────── 汇总属性 ──────────────────────


class TestSummaryProperties:
    """ValidationSummary 属性。"""

    def test_summary_success_rate_all_passed(self):
        """全部通过时 success_rate=1.0。"""
        bs = make_balance_sheet(100.0, 60.0, 40.0)
        service = ValidationService(make_registry([make_rule_bs_bal_001()]))

        summary = service.validate([bs])

        assert summary.success_rate == 1.0

    def test_summary_success_rate_partial(self):
        """部分通过时 success_rate=0.5。"""
        rule1 = make_rule_bs_bal_001()
        rule2 = make_rule(
            rule_id="BS-BAL-002",
            name="流动+非流动=资产",
            formula="current_assets + non_current_assets == asset_total",
        )
        bs = make_balance_sheet(
            asset_total=100.0,
            liability_total=60.0,
            equity_total=40.0,
            current_assets=50.0,
            non_current_assets=30.0,  # 80 != 100
        )
        service = ValidationService(make_registry([rule1, rule2]))

        summary = service.validate([bs])

        assert summary.success_rate == 0.5

    def test_summary_success_rate_no_rules(self):
        """无规则时 success_rate=1.0。"""
        service = ValidationService(make_registry([]))
        bs = make_balance_sheet()

        summary = service.validate([bs])

        assert summary.success_rate == 1.0

    def test_summary_failed_results_excludes_passed(self):
        """failed_results 只含不通过的结果。"""
        rule1 = make_rule_bs_bal_001()
        rule2 = make_rule(
            rule_id="BS-BAL-002",
            name="流动+非流动=资产",
            formula="current_assets + non_current_assets == asset_total",
        )
        bs = make_balance_sheet(
            asset_total=100.0,
            liability_total=60.0,
            equity_total=40.0,
            current_assets=50.0,
            non_current_assets=30.0,  # fails
        )
        service = ValidationService(make_registry([rule1, rule2]))

        summary = service.validate([bs])

        assert len(summary.failed_results) == 1
        assert summary.failed_results[0].rule_id == "BS-BAL-002"

    def test_summary_period_set_from_reports(self):
        """汇总的 period 从报表获取。"""
        bs = make_balance_sheet(period="2025-06")
        service = ValidationService(make_registry([make_rule_bs_bal_001()]))

        summary = service.validate([bs], period="2025-06")

        assert summary.period == "2025-06"


# ────────────────────── 行业阈值注入 ──────────────────────


class TestIndustryThresholdInjection:
    """threshold_vars 穿线: 逻辑合理性规则按行业阈值判定。"""

    @staticmethod
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

    def test_validate_default_general_threshold_fails(self):
        """不传 threshold_vars -> general 0.85: 资产负债率 0.88 不通过 (默认行为)。"""
        bs = make_balance_sheet(
            asset_total=100.0, liability_total=88.0, equity_total=12.0
        )
        service = ValidationService(make_registry([self._dar_rule()]))

        summary = service.validate([bs], period="2024-12")

        assert summary.total == 1
        assert summary.results[0].rule_id == "LR-DAR-001"
        assert summary.results[0].passed is False

    def test_validate_financial_threshold_passes(self):
        """financial 阈值 0.92: 资产负债率 0.88 通过。"""
        bs = make_balance_sheet(
            asset_total=100.0, liability_total=88.0, equity_total=12.0
        )
        service = ValidationService(make_registry([self._dar_rule()]))

        summary = service.validate(
            [bs], period="2024-12", threshold_vars={"dar_threshold": 0.92}
        )

        assert summary.results[0].rule_id == "LR-DAR-001"
        assert summary.results[0].passed is True

    def test_validate_partial_threshold_vars_keep_general_defaults(self):
        """只覆写 dar_threshold, 其他阈值变量仍回落 general 默认。"""
        bs = make_balance_sheet(
            asset_total=100.0, liability_total=85.0, equity_total=15.0
        )
        service = ValidationService(make_registry([self._dar_rule()]))

        summary = service.validate(
            [bs], period="2024-12", threshold_vars={"dar_threshold": 0.80}
        )

        assert summary.results[0].passed is False  # 0.85 > 0.80 仍不通过
