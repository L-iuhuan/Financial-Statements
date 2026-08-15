"""报表包校验服务: 主表勾稽 + 明细勾稽一次执行并合并结果。"""

from __future__ import annotations

from fsa.core.engine.registry import RuleRegistry
from fsa.core.models.detail import DetailDataset
from fsa.core.models.report import Report, ReportType
from fsa.core.models.result import ValidationResult, ValidationSummary
from fsa.services.detail_validation_service import (
    DetailCheckConfig,
    DetailValidationService,
)
from fsa.services.validation_service import ValidationService


class PackageValidationService:
    """一次导入六张附表后执行全部校验。"""

    def __init__(
        self,
        registry: RuleRegistry,
        detail_config: DetailCheckConfig | None = None,
    ) -> None:
        self._registry = registry
        self._detail_config = detail_config

    def validate(
        self,
        reports: list[Report],
        dataset: DetailDataset,
        period: str,
        threshold_vars: dict[str, float] | None = None,
    ) -> ValidationSummary:
        """执行主表规则与明细勾稽检查，合并为一份汇总。

        Args:
            reports: 待校验的报表列表
            dataset: 明细数据集 (可为空)
            period: 报告期间, 如 "2024-12"
            threshold_vars: 逻辑合理性规则(LR-*)的行业阈值变量 -> 值,
                按主体行业注入; 缺省 None 时由 runner 回落 general 默认阈值。

        Returns:
            合并后的 ValidationSummary 汇总结果
        """
        main_summary = ValidationService(self._registry).validate(
            reports, period, threshold_vars
        )
        if dataset.is_empty:
            return main_summary
        detail_service = DetailValidationService(self._detail_config)
        report_map: dict[ReportType, Report] = {
            report.report_type: report for report in reports
        }
        detail_summary = detail_service.validate(dataset, report_map)
        return merge_summaries(main_summary, detail_summary)


def merge_summaries(*summaries: ValidationSummary) -> ValidationSummary:
    """合并多个校验汇总：按 rule_id 去重并重算统计。

    去重策略: 保留首次出现的同 rule_id 结果（先者优先）。
    - 单体包校验 (PackageValidationService): 主表规则与明细勾稽 rule_id 本应
      互斥，去重可防止重复 rule_id 导致 total/passed/failed 统计失真 (P2 确定性)。
    - 多主体合并 (MultiEntityService): 汇总层每个 rule_id 只保留首个主体的结果，
      各主体的逐主体明细仍保留在 outcomes 中，不受影响。

    Returns:
        去重并重算统计后的 ValidationSummary
    """
    results: list[ValidationResult] = []
    seen: set[str] = set()
    for summary in summaries:
        for result in summary.results:
            if result.rule_id in seen:
                continue
            seen.add(result.rule_id)
            results.append(result)
    report_types: list[ReportType] = []
    for summary in summaries:
        for report_type in summary.report_types:
            if report_type not in report_types:
                report_types.append(report_type)
    passed = sum(1 for result in results if result.passed and not result.skipped and not result.errored)
    failed = sum(1 for result in results if not result.passed and not result.errored)
    errored = sum(1 for result in results if result.errored)
    skipped = sum(1 for result in results if result.skipped)
    period = next((summary.period for summary in summaries if summary.period), "")
    return ValidationSummary(
        period=period,
        total=len(results),
        passed=passed,
        failed=failed,
        errored=errored,
        skipped=skipped,
        results=results,
        report_types=report_types,
    )
