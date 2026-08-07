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
    """规则执行异常时记录为 errored。"""

    def test_validate_rule_with_missing_variable_returns_errored(self):
        """报表缺少 liability_total -> MissingItemError -> errored。"""
        bs = Report(
            report_type=ReportType.BALANCE_SHEET,
            period="2024-12",
            items=[make_item("asset_total", "资产总计", 100.0)],
        )
        service = ValidationService(make_registry([make_rule_bs_bal_001()]))

        summary = service.validate([bs])

        assert summary.total == 1
        assert summary.errored == 1
        assert summary.passed == 0
        assert summary.failed == 0
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

    def test_validate_error_result_has_errored_flag(self):
        """异常结果的 errored 标志为 True。"""
        bs = Report(
            report_type=ReportType.BALANCE_SHEET,
            items=[make_item("asset_total", "资产总计", 100.0)],
        )
        service = ValidationService(make_registry([make_rule_bs_bal_001()]))

        summary = service.validate([bs])

        assert len(summary.results) == 1
        assert summary.results[0].errored is True


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
