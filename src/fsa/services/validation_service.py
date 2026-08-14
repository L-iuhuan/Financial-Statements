"""校验服务: 编排报表导入 -> 规则匹配 -> 执行校验 -> 返回汇总结果。

ValidationService 是业务编排层, 将 RuleRegistry + RuleRunner + ValidationContext 组合:
1. 从报表列表构建 ValidationContext
2. 筛选适用的规则 (所需报表类型均已导入)
3. 逐条执行, 捕获异常转为 errored 结果
4. 返回 ValidationSummary

不读取文件、不操作 GUI。文件导入由 ImportService 完成, 调用方将 Report 传入即可。
"""

from __future__ import annotations

from loguru import logger

from fsa.core.engine.registry import RuleRegistry
from fsa.core.engine.runner import RuleRunner
from fsa.core.exceptions import EvaluationError, FormulaParseError, FSAError
from fsa.core.models.report import Report, ReportType
from fsa.core.models.result import (
    ValidationContext,
    ValidationResult,
    ValidationSummary,
)
from fsa.core.models.rule import ReconciliationRule

_NAME_TO_TYPE: dict[str, ReportType] = {rt.value: rt for rt in ReportType}


class ValidationService:
    """校验编排服务。

    职责: 接收报表列表 + 规则注册表 -> 执行校验 -> 返回汇总结果。
    禁止: 读取文件、操作 GUI。

    Usage:
        registry = RuleRegistry.from_json("rules.json")
        service = ValidationService(registry)
        summary = service.validate(reports, period="2024-12")
        if not summary.all_passed:
            for r in summary.failed_results:
                print(r.message)
    """

    def __init__(self, registry: RuleRegistry) -> None:
        self._registry = registry

    def validate(
        self,
        reports: list[Report],
        period: str = "",
        threshold_vars: dict[str, float] | None = None,
    ) -> ValidationSummary:
        """校验报表列表, 返回汇总结果。

        Args:
            reports: 待校验的报表列表
            period: 报告期间, 如 "2024-12"
            threshold_vars: 逻辑合理性规则(LR-*)的行业阈值变量 -> 值,
                按主体行业注入 (见 EntityConfig.industry)。缺省为 None,
                由 runner 回落 general 默认阈值 (与现状行为一致)。

        Returns:
            ValidationSummary 汇总结果
        """
        logger.info(f"开始校验, 共 {len(reports)} 张报表, 期间 {period}")

        context = self._build_context(reports, period)
        active_rules = self._registry.get_active()

        results: list[ValidationResult] = []
        skipped = 0

        for rule in active_rules:
            if not self._is_applicable(rule, context):
                skipped += 1
                logger.debug(f"规则 {rule.rule_id} 跳过 (缺少所需报表)")
                continue
            result = self._run_rule_safe(rule, context, threshold_vars)
            results.append(result)

        summary = self._build_summary(results, context, period, skipped)
        logger.info(
            f"校验完成: 共 {summary.total} 条, "
            f"通过 {summary.passed}, 不通过 {summary.failed}, "
            f"异常 {summary.errored}, 跳过 {summary.skipped}"
        )
        return summary

    def _build_context(
        self, reports: list[Report], period: str
    ) -> ValidationContext:
        """从报表列表构建校验上下文。"""
        context = ValidationContext(period=period)
        for report in reports:
            context.add_report(report)
        return context

    @staticmethod
    def _is_applicable(
        rule: ReconciliationRule, context: ValidationContext
    ) -> bool:
        """检查规则所需的所有报表类型是否都已导入。"""
        required = _get_required_types(rule)
        available = set(context.reports.keys())
        return required.issubset(available)

    @staticmethod
    def _run_rule_safe(
        rule: ReconciliationRule,
        context: ValidationContext,
        threshold_vars: dict[str, float] | None = None,
    ) -> ValidationResult:
        """执行单条规则, 捕获异常转为跳过/异常结果。

        EvaluationError (变量未定义/除零/相对容差基准为0) -> 跳过 (缺少数据, 不算不通过)
        FormulaParseError (公式语法错误) -> 异常 (规则定义有误)
        其他 FSAError -> 异常
        可预期的运行期异常 (ValueError/TypeError/KeyError/ArithmeticError/
        RuntimeError/OSError) -> 异常 (未预期错误)
        其余异常 -> 向上传播 (暴露真实缺陷, 不做宽泛捕获)
        """
        try:
            return RuleRunner.run(rule, context, threshold_vars)
        except EvaluationError as e:
            logger.info(f"规则 {rule.rule_id} 跳过 (数据不足): {e}")
            return ValidationResult.from_skip(rule, str(e))
        except FormulaParseError as e:
            logger.warning(f"规则 {rule.rule_id} 公式错误: {e}")
            return ValidationResult.from_error(rule, str(e))
        except FSAError as e:
            logger.warning(f"规则 {rule.rule_id} 执行异常: {e}")
            return ValidationResult.from_error(rule, str(e))
        except (ValueError, TypeError, KeyError, ArithmeticError, RuntimeError, OSError) as e:
            logger.error(f"规则 {rule.rule_id} 执行异常: {type(e).__name__}: {e}")
            return ValidationResult.from_error(rule, f"未预期错误: {e}")

    @staticmethod
    def _build_summary(
        results: list[ValidationResult],
        context: ValidationContext,
        period: str,
        skipped: int,
    ) -> ValidationSummary:
        """从结果列表构建汇总。

        skipped 参数来自缺少所需报表的规则 (未放入 results)。
        results 中可能有 skipped=True 的结果 (来自 EvaluationError)。
        """
        skipped_from_results = sum(1 for r in results if r.skipped)
        passed = sum(1 for r in results if r.passed and not r.skipped)
        failed = sum(1 for r in results if not r.passed and not r.errored)
        errored = sum(1 for r in results if r.errored)
        total = len(results) - skipped_from_results

        return ValidationSummary(
            period=period,
            total=total,
            passed=passed,
            failed=failed,
            errored=errored,
            skipped=skipped + skipped_from_results,
            results=results,
            report_types=list(context.reports.keys()),
        )


def _get_required_types(rule: ReconciliationRule) -> set[ReportType]:
    """从规则的 statements 字段提取所需的 ReportType 集合。"""
    types: set[ReportType] = set()
    for name in rule.statements:
        rt = _NAME_TO_TYPE.get(name)
        if rt is not None:
            types.add(rt)
    return types
