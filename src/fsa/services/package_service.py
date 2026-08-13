"""报表包校验服务: 主表勾稽 + 明细勾稽一次执行并合并结果。"""

from __future__ import annotations

from fsa.core.engine.registry import RuleRegistry
from fsa.core.models.detail import DetailDataset
from fsa.core.models.report import Report, ReportType
from fsa.core.models.result import ValidationSummary
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
    ) -> ValidationSummary:
        """执行主表规则与明细勾稽检查，合并为一份汇总。"""
        main_summary = ValidationService(self._registry).validate(reports, period)
        detail_service = DetailValidationService(self._detail_config)
        report_map: dict[ReportType, Report] = {
            report.report_type: report for report in reports
        }
        detail_summary = detail_service.validate(dataset, report_map)
        return merge_summaries(main_summary, detail_summary)


def merge_summaries(*summaries: ValidationSummary) -> ValidationSummary:
    """合并多个校验汇总：拼接结果明细并重算统计。"""
    results = [result for summary in summaries for result in summary.results]
    report_types: list[ReportType] = []
    for summary in summaries:
        for report_type in summary.report_types:
            if report_type not in report_types:
                report_types.append(report_type)
    passed = sum(1 for result in results if result.passed)
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
