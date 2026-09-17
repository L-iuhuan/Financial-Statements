"""多主体批量校验与集团内双边核对。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from loguru import logger

from fsa.core.engine.registry import RuleRegistry
from fsa.core.engine.rule_hints import format_hint_block
from fsa.core.exceptions import FSAError
from fsa.core.importer.detail_importer import DetailImporter
from fsa.core.importer.excel_reader import ExcelComSession
from fsa.core.importer.importer import ImportService
from fsa.core.importer.name_mapper import clean_name
from fsa.core.models.detail import DetailDataset
from fsa.core.models.report import Report, ReportType
from fsa.core.models.result import ValidationResult, ValidationSummary
from fsa.core.models.rule import Severity
from fsa.services.entity_config import EntityConfig
from fsa.services.package_service import PackageValidationService, merge_summaries

_SUPPORTED_SUFFIXES = (".xlsx", ".xls", ".xlsm", ".csv", ".pdf")


def _normalize_entity_name(name: str) -> str:
    """主体/对方单位名称归一化 (去全部空白), 用于别名匹配。"""
    return re.sub(r"\s+", "", name)

# 内部现金流双边核对: 一方的流入项目 ↔ 对方相应的流出项目（缺省配置，可经
# entity_config.bilateral_pairs 覆写）。命名与 detail_checks.CF_PROJECT_ALIASES
# 内部项目命名一致（"收到的…/支付的…"），保证与明细行项目名精确匹配。
DEFAULT_BILATERAL_PAIRS: dict[str, str] = {
    "销售商品、提供劳务收到的现金": "购买商品、接受劳务支付的现金",
    "收到的其他与经营活动的现金": "支付的其他与经营活动的现金",
    # 对应主表项目「收到/支付其他与投资活动有关的现金」
    "收到的其他与投资活动的现金": "支付的其他与投资活动的现金",
    # 对应主表项目「收到/支付其他与筹资活动有关的现金」
    "收到的其他与筹资活动的现金": "支付的其他与筹资活动的现金",
}
DEFAULT_BILATERAL_TOLERANCE: float = 0.01


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
    purchase_sales: list[ValidationResult] = field(default_factory=list)


class MultiEntityService:
    """批量校验多个主体的报表包，并执行集团内双边核对。"""

    def __init__(
        self,
        registry: RuleRegistry,
        configs: dict[str, EntityConfig] | None = None,
    ) -> None:
        self._registry = registry
        self._configs = configs or {}
        # 共享 Excel COM 会话 (懒启动): 多主体批量读取 DLP 加密文件时复用
        # 同一 Excel 进程, 避免每文件 5-40s 启动开销 (2026-09-17"卡死"根因)
        self._com_session: ExcelComSession | None = None

    def validate_folders(
        self,
        folders: list[str],
        period: str = "",
    ) -> MultiEntityResult:
        """逐主体校验，合并结果并做双边核对 (结束后关闭共享 COM 会话)。"""
        try:
            outcomes = [
                self.validate_folder(folder, period=period) for folder in folders
            ]
            summaries = [o.summary for o in outcomes if o.summary is not None]
            combined = merge_summaries(*summaries) if summaries else None
            bilateral = self.check_bilateral(outcomes)
            purchase_sales = self.check_purchase_sales(outcomes)
            return MultiEntityResult(
                outcomes=outcomes,
                combined=combined,
                bilateral=bilateral,
                purchase_sales=purchase_sales,
            )
        finally:
            self.close()

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
        if not files:
            errors.append(
                "文件夹中没有可导入的报表文件（支持 .xlsx/.xls/.csv/.pdf）"
            )
        for path in files:
            self._import_one(path, reports_by_type, dataset, errors, period)

        reports = list(reports_by_type.values())
        config = self._configs.get(entity)
        detail_config = config.to_detail_config() if config is not None else None
        # 按主体行业注入 LR-* 阈值; 无配置时 None -> runner 回落 general 默认阈值
        threshold_vars = config.threshold_vars() if config is not None else None
        try:
            summary = PackageValidationService(
                self._registry, detail_config
            ).validate(reports, dataset, period, threshold_vars)
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
        """导入单个文件：主表去重、明细合并，失败只记录不中断。

        先导入主表，主表成功后才尝试明细导入（避免对既非主表也非明细的
        文件产生两条重复错误）；明细导入失败仅记录调试日志，因为该文件
        可能就是纯主表文件，明细导入失败属预期路径。
        """
        try:
            reports = ImportService(period).import_file(
                str(path), com_session=self._shared_session()
            )
        except (FileNotFoundError, FSAError, ValueError, OSError, ImportError) as error:
            errors.append(f"{path.name}: {error}")
            return
        except Exception as error:
            # 兜底: 单文件未预期异常不得中断整批多主体校验 (2026-09-17
            # 实测: 文件夹内的 PDF 曾致整批中断); 记为该文件失败并继续
            logger.exception(f"「{path.name}」导入出现未预期异常")
            errors.append(f"{path.name}: 导入出现未预期错误: {error}")
            return
        for report in reports:
            if report.report_type not in reports_by_type:
                reports_by_type[report.report_type] = report
        try:
            dataset.merge(
                DetailImporter(period).import_file(
                    str(path), com_session=self._shared_session()
                )
            )
        except (FileNotFoundError, FSAError, ValueError, OSError, ImportError) as error:
            logger.debug(f"「{path.name}」明细导入失败，可能为纯主表文件: {error}")
        except Exception as error:
            logger.debug(f"「{path.name}」明细导入未预期异常 (忽略继续): {error}")

    def _shared_session(self) -> ExcelComSession:
        """懒启动共享 Excel COM 会话 (批量 DLP 加密文件复用同一 Excel 进程)。

        多主体此前每文件独立回退 COM, 每文件 5-40s Excel 启动 × 上百文件 =
        小时级耗时, 用户表现为"选整个文件夹卡死" (2026-09-17 根因)。
        会话须在同一线程创建/使用/关闭 (COM 单元模型) —— validate_folder
        循环与 close() 均在调用方同一后台线程执行, 满足亲和性约束。
        """
        if self._com_session is None:
            self._com_session = ExcelComSession()
        return self._com_session

    def close(self) -> None:
        """关闭共享 Excel COM 会话并回收本会话残留 (幂等; 须与创建线程相同)。"""
        if self._com_session is not None:
            self._com_session.close()
            self._com_session = None

    def check_bilateral(self, outcomes: list[EntityOutcome]) -> list[ValidationResult]:
        """按主体标识/别名核对内部交易现金流双边金额（流入方 vs 流出方）。

        匹配规则: 明细行「对方单位」归一化后命中对方主体的「标识 + 别名」集合
        （对方单位通常填公司全称, 与文件夹名不一致——2026-09-17 实测修复:
        此前按主体名精确匹配, 真实数据永配不上, 双边核对恒为 0 条）。
        容差约定: 每个主体对按组合中**先出现主体（left）**的配置解析——
        其自定义 -> 全局首个自定义 -> 默认值；right 主体的容差配置在该
        主体自身为先出现主体的其他组合中生效（口径隔离, 与既有行为一致）。
        """
        datasets = {
            outcome.entity_id: outcome.dataset for outcome in outcomes
        }
        name_sets = {
            entity_id: self._name_set(entity_id) for entity_id in datasets
        }
        entities = list(datasets)
        results: list[ValidationResult] = []
        for left_idx in range(len(entities)):
            for right_idx in range(left_idx + 1, len(entities)):
                left = entities[left_idx]
                right = entities[right_idx]
                pairs, tolerance = self._bilateral_settings_for(left)
                for inflow_project, outflow_project in pairs.items():
                    results.extend(
                        self._pair_results(
                            datasets[left],
                            datasets[right],
                            left,
                            right,
                            inflow_project,
                            outflow_project,
                            tolerance,
                            left_names=name_sets[left],
                            right_names=name_sets[right],
                        )
                    )
        return results

    def check_purchase_sales(self, outcomes: list[EntityOutcome]) -> list[ValidationResult]:
        """核对跨主体关联方采购与销售收入双边金额（附表4 ↔ 附表5）。

        容差约定与 check_bilateral 一致: 按主体对中先出现主体（left）的
        bilateral_tolerance 解析。
        """
        datasets = {
            outcome.entity_id: outcome.dataset for outcome in outcomes
        }
        name_sets = {
            entity_id: self._name_set(entity_id) for entity_id in datasets
        }
        entities = list(datasets)
        results: list[ValidationResult] = []
        for left_idx in range(len(entities)):
            for right_idx in range(left_idx + 1, len(entities)):
                left = entities[left_idx]
                right = entities[right_idx]
                _, tolerance = self._bilateral_settings_for(left)
                self._append_purchase_sales(
                    datasets, left, right, name_sets, tolerance, results
                )
                self._append_purchase_sales(
                    datasets, right, left, name_sets, tolerance, results
                )
        return results

    def _append_purchase_sales(
        self,
        datasets: dict[str, DetailDataset],
        buyer: str,
        seller: str,
        name_sets: dict[str, frozenset[str]],
        tolerance: float,
        results: list[ValidationResult],
    ) -> None:
        """生成单一方向的购销核对结果（任一侧非零时产出）。

        P1: 买方缺附表4（关联方采购明细）或卖方缺附表5（销售收入报表）时
        直接跳过——「缺表」不得当成「差额」误报。
        """
        buyer_data = datasets[buyer]
        seller_data = datasets[seller]
        if not buyer_data.related_party_purchases or not seller_data.sales_details:
            return
        purchase = MultiEntityService._sum_purchases(
            buyer_data, name_sets[seller]
        )
        sales = MultiEntityService._sum_sales(
            seller_data, name_sets[buyer]
        )
        if purchase or sales:
            results.append(
                MultiEntityService._build_purchase_sales_result(
                    buyer, seller, purchase, sales, tolerance
                )
            )

    def _name_set(self, entity_id: str) -> frozenset[str]:
        """主体的全部可匹配名称 (标识 + 配置别名), 归一化后返回。"""
        names = {entity_id}
        config = self._configs.get(entity_id)
        if config is not None:
            names.update(config.aliases)
        return frozenset(
            _normalize_entity_name(name) for name in names if name
        )

    def _bilateral_settings_for(self, entity_id: str) -> tuple[dict[str, str], float]:
        """按主体解析双边核对配置：该主体自定义 -> 全局兜底。"""
        own = self._configs.get(entity_id)
        if own is not None and (own.bilateral_pairs or own.bilateral_tolerance is not None):
            return (
                own.bilateral_pairs or DEFAULT_BILATERAL_PAIRS,
                own.bilateral_tolerance
                if own.bilateral_tolerance is not None
                else DEFAULT_BILATERAL_TOLERANCE,
            )
        return self._bilateral_settings()

    def _bilateral_settings(self) -> tuple[dict[str, str], float]:
        """集团双边核对的全局兜底配置：首个自定义主体配置，否则默认值。"""
        for config in self._configs.values():
            pairs = config.bilateral_pairs or DEFAULT_BILATERAL_PAIRS
            tolerance = (
                config.bilateral_tolerance
                if config.bilateral_tolerance is not None
                else DEFAULT_BILATERAL_TOLERANCE
            )
            return pairs, tolerance
        return DEFAULT_BILATERAL_PAIRS, DEFAULT_BILATERAL_TOLERANCE

    @staticmethod
    def _pair_results(
        left_data: DetailDataset,
        right_data: DetailDataset,
        left_name: str,
        right_name: str,
        inflow_project: str,
        outflow_project: str,
        tolerance: float,
        left_names: frozenset[str],
        right_names: frozenset[str],
    ) -> list[ValidationResult]:
        """生成一对主体的双向核对结果（跳过双方均为零的组合）。

        left_names/right_names: 各主体的「标识+别名」归一化集合, 用于匹配
        明细行的「对方单位」字段。
        P1: 任一侧的内部现金流明细表整体缺失（未提供/未导入）时直接跳过——
        「缺数据」不得当成「差额」误报（此时单边金额无从对证）。
        """
        if not left_data.internal_cash_flows or not right_data.internal_cash_flows:
            return []
        left_in = MultiEntityService._sum_flows(left_data, right_names, inflow_project)
        right_out = MultiEntityService._sum_flows(right_data, left_names, outflow_project)
        right_in = MultiEntityService._sum_flows(right_data, left_names, inflow_project)
        left_out = MultiEntityService._sum_flows(left_data, right_names, outflow_project)

        results: list[ValidationResult] = []
        if left_in or right_out:
            results.append(
                MultiEntityService._build_pair_result(
                    left_name, right_name, inflow_project, outflow_project,
                    left_in, right_out, tolerance,
                )
            )
        if right_in or left_out:
            results.append(
                MultiEntityService._build_pair_result(
                    right_name, left_name, inflow_project, outflow_project,
                    right_in, left_out, tolerance,
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
        tolerance: float,
    ) -> ValidationResult:
        """构建单方向的双边核对结果。"""
        diff = inflow - outflow
        passed = abs(diff) <= tolerance
        message = (
            f"「{entity}」对「{counterparty}」「{inflow_project}」"
            f"{inflow:,.2f} vs 对方「{outflow_project}」{outflow:,.2f}: "
            f"{'一致' if passed else f'差额 {diff:,.2f}'}"
        )
        if not passed:
            # 单边为零多半是别名未配置 (对方以其他名称登记), 提示先查配置
            # 再定性差异 (oracle 评审建议, 降低 P1 困扰)
            if inflow == 0.0 or outflow == 0.0:
                message += "（提示：若一方在对方明细中以其他名称登记，请在实体配置中补充别名后重新校验）"
            message += format_hint_block("ICF-002", Severity.WARNING.value)
        return ValidationResult(
            rule_id="ICF-002",
            rule_name="内部现金流双边核对",
            passed=passed,
            severity=Severity.WARNING,
            left_value=inflow,
            right_value=outflow,
            diff=diff,
            tolerance=tolerance,
            formula="内部流入金额 == 对方内部流出金额",
            message=message,
            category="L2-明细勾稽",
        )

    @staticmethod
    def _sum_flows(
        dataset: DetailDataset, counterparties: frozenset[str], project: str
    ) -> float:
        """汇总某一主体对指定对方（标识/别名集合）某项目的内部现金流发生额。"""
        total = 0.0
        for row in dataset.internal_cash_flows:
            if (
                _normalize_entity_name(row.counterparty) in counterparties
                and clean_name(row.project) == project
            ):
                total += row.amount
        return total

    @staticmethod
    def _sum_purchases(dataset: DetailDataset, seller_names: frozenset[str]) -> float:
        """汇总主体对指定卖方（标识/别名集合）的关联方采购金额。"""
        total = 0.0
        for row in dataset.related_party_purchases:
            if _normalize_entity_name(row.counterparty) in seller_names:
                total += row.total_amount
        return total

    @staticmethod
    def _sum_sales(dataset: DetailDataset, buyer_names: frozenset[str]) -> float:
        """汇总主体对指定买方（标识/别名集合）的销售收入金额。"""
        total = 0.0
        for row in dataset.sales_details:
            if _normalize_entity_name(row.customer) in buyer_names:
                total += row.revenue_amount
        return total

    @staticmethod
    def _build_purchase_sales_result(
        buyer: str,
        seller: str,
        purchase: float,
        sales: float,
        tolerance: float,
    ) -> ValidationResult:
        """构建单方向关联方购销核对结果。"""
        diff = purchase - sales
        passed = abs(diff) <= tolerance
        message = (
            f"「{buyer}」向「{seller}」采购 {purchase:,.2f} 元 vs "
            f"对方「{seller}」对「{buyer}」销售 {sales:,.2f} 元: "
            f"{'金额一致' if passed else f'差额 {diff:,.2f} 元'}"
        )
        if not passed:
            # 单边为零多半是别名未配置 (对方以其他名称登记), 提示先查配置
            # 再定性差异 (oracle 评审建议, 降低 P1 困扰)
            if purchase == 0.0 or sales == 0.0:
                message += "（提示：若一方在对方明细中以其他名称登记，请在实体配置中补充别名后重新校验）"
            message += format_hint_block("RPS-001", Severity.WARNING.value)
        return ValidationResult(
            rule_id="RPS-001",
            rule_name="关联方购销双边核对",
            passed=passed,
            severity=Severity.WARNING,
            left_value=purchase,
            right_value=sales,
            diff=diff,
            tolerance=tolerance,
            formula="一方采购金额 == 对方销售金额",
            message=message,
            category="L2-明细勾稽",
        )
