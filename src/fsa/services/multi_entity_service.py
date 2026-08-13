"""多主体批量校验与集团内双边核对。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from loguru import logger

from fsa.core.engine.registry import RuleRegistry
from fsa.core.exceptions import FSAError
from fsa.core.importer.detail_importer import DetailImporter
from fsa.core.importer.importer import ImportService
from fsa.core.importer.name_mapper import clean_name
from fsa.core.models.detail import DetailDataset
from fsa.core.models.report import Report, ReportType
from fsa.core.models.result import ValidationResult, ValidationSummary
from fsa.core.models.rule import Severity
from fsa.services.entity_config import EntityConfig
from fsa.services.package_service import PackageValidationService, merge_summaries

_SUPPORTED_SUFFIXES = (".xlsx", ".xls", ".pdf")

# 内部现金流双边核对: 一方的流入项目 ↔ 对方相应的流出项目
_BILATERAL_PAIRS: dict[str, str] = {
    "收到的其他与经营活动的现金": "支付的其他与经营活动的现金",
    "销售商品、提供劳务收到的现金": "购买商品、接受劳务支付的现金",
}


@dataclass
class EntityOutcome:
    """单个主体的校验结果。"""

    entity_id: str
    folder: str
    reports: list[Report] = field(default_factory=list)
    dataset: DetailDataset = field(default_factory=DetailDataset)
    summary: ValidationSummary | None = None
    errors: list[str] = field(default_factory=list)


@dataclass
class MultiEntityResult:
    """多主体批量校验结果。"""

    outcomes: list[EntityOutcome] = field(default_factory=list)
    combined: ValidationSummary | None = None
    bilateral: list[ValidationResult] = field(default_factory=list)


class MultiEntityService:
    """批量校验多个主体的报表包，并执行集团内双边核对。"""

    def __init__(
        self,
        registry: RuleRegistry,
        configs: dict[str, EntityConfig] | None = None,
    ) -> None:
        self._registry = registry
        self._configs = configs or {}

    def validate_folders(
        self,
        folders: list[str],
        period: str = "",
    ) -> MultiEntityResult:
        """逐主体校验，合并结果并做双边核对。"""
        outcomes = [
            self.validate_folder(folder, period=period) for folder in folders
        ]
        summaries = [o.summary for o in outcomes if o.summary is not None]
        combined = merge_summaries(*summaries) if summaries else None
        bilateral = self.check_bilateral(outcomes)
        return MultiEntityResult(
            outcomes=outcomes,
            combined=combined,
            bilateral=bilateral,
        )

    def validate_folder(
        self,
        folder: str,
        entity_id: str | None = None,
        period: str = "",
    ) -> EntityOutcome:
        """导入一个主体文件夹中的全部报表文件并校验。"""
        folder_path = Path(folder)
        entity = entity_id or folder_path.name
        reports_by_type: dict[ReportType, Report] = {}
        dataset = DetailDataset(period=period, entity=entity)
        errors: list[str] = []

        files = [
            path
            for path in sorted(folder_path.iterdir())
            if path.is_file() and path.suffix.lower() in _SUPPORTED_SUFFIXES
        ]
        for path in files:
            self._import_one(path, reports_by_type, dataset, errors, period)

        reports = list(reports_by_type.values())
        config = self._configs.get(entity)
        detail_config = config.to_detail_config() if config is not None else None
        try:
            summary = PackageValidationService(
                self._registry, detail_config
            ).validate(reports, dataset, period)
        except (FSAError, ValueError, KeyError, TypeError) as error:
            logger.error(f"主体「{entity}」校验失败: {error}")
            summary = None
            errors.append(str(error))
        return EntityOutcome(
            entity_id=entity,
            folder=str(folder_path),
            reports=reports,
            dataset=dataset,
            summary=summary,
            errors=errors,
        )

    def _import_one(
        self,
        path: Path,
        reports_by_type: dict[ReportType, Report],
        dataset: DetailDataset,
        errors: list[str],
        period: str,
    ) -> None:
        """导入单个文件：主表去重、明细合并，失败只记录不中断。"""
        try:
            reports = ImportService(period).import_file(str(path))
            for report in reports:
                if report.report_type not in reports_by_type:
                    reports_by_type[report.report_type] = report
        except (FileNotFoundError, FSAError, ValueError, OSError, ImportError) as error:
            errors.append(f"{path.name}: {error}")
        try:
            dataset.merge(DetailImporter(period).import_file(str(path)))
        except (FileNotFoundError, FSAError, ValueError, OSError, ImportError) as error:
            errors.append(f"{path.name}: {error}")

    def check_bilateral(self, outcomes: list[EntityOutcome]) -> list[ValidationResult]:
        """按主体名核对内部交易现金流双边金额（流入方 vs 流出方）。"""
        datasets = {
            outcome.entity_id: outcome.dataset for outcome in outcomes
        }
        entities = list(datasets)
        results: list[ValidationResult] = []
        for left_idx in range(len(entities)):
            for right_idx in range(left_idx + 1, len(entities)):
                left = entities[left_idx]
                right = entities[right_idx]
                for inflow_project, outflow_project in _BILATERAL_PAIRS.items():
                    results.extend(
                        self._pair_results(
                            datasets[left],
                            datasets[right],
                            left,
                            right,
                            inflow_project,
                            outflow_project,
                        )
                    )
        return results

    @staticmethod
    def _pair_results(
        left_data: DetailDataset,
        right_data: DetailDataset,
        left_name: str,
        right_name: str,
        inflow_project: str,
        outflow_project: str,
    ) -> list[ValidationResult]:
        """生成一对主体的双向核对结果（跳过双方均为零的组合）。"""
        left_in = MultiEntityService._sum_flows(left_data, right_name, inflow_project)
        right_out = MultiEntityService._sum_flows(right_data, left_name, outflow_project)
        right_in = MultiEntityService._sum_flows(right_data, left_name, inflow_project)
        left_out = MultiEntityService._sum_flows(left_data, right_name, outflow_project)

        results: list[ValidationResult] = []
        if left_in or right_out:
            results.append(
                MultiEntityService._build_pair_result(
                    left_name, right_name, inflow_project, outflow_project,
                    left_in, right_out,
                )
            )
        if right_in or left_out:
            results.append(
                MultiEntityService._build_pair_result(
                    right_name, left_name, inflow_project, outflow_project,
                    right_in, left_out,
                )
            )
        return results

    @staticmethod
    def _build_pair_result(
        entity: str,
        counterparty: str,
        inflow_project: str,
        outflow_project: str,
        inflow: float,
        outflow: float,
    ) -> ValidationResult:
        """构建单方向的双边核对结果。"""
        diff = inflow - outflow
        passed = abs(diff) <= 0.01
        return ValidationResult(
            rule_id="ICF-002",
            rule_name="内部现金流双边核对",
            passed=passed,
            severity=Severity.WARNING,
            left_value=inflow,
            right_value=outflow,
            diff=diff,
            tolerance=0.01,
            formula="内部流入金额 == 对方内部流出金额",
            message=(
                f"「{entity}」对「{counterparty}」「{inflow_project}」"
                f"{inflow:,.2f} vs 对方「{outflow_project}」{outflow:,.2f}: "
                f"{'一致' if passed else f'差额 {diff:,.2f}'}"
            ),
            category="L2-明细勾稽",
        )

    @staticmethod
    def _sum_flows(
        dataset: DetailDataset, counterparty: str, project: str
    ) -> float:
        """汇总某一主体对指定对方的某项目内部现金流发生额。"""
        total = 0.0
        for row in dataset.internal_cash_flows:
            if row.counterparty == counterparty and clean_name(row.project) == project:
                total += row.amount
        return total
