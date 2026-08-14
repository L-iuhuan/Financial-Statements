"""明细校验服务: 编排明细数据集与主表，执行 L2 明细勾稽检查。"""

from __future__ import annotations

from dataclasses import dataclass, field

from fsa.core.engine.cash_flow_checks import (
    check_cash_flow_classification,
    check_cash_flow_coverage,
)
from fsa.core.engine.detail_checks import (
    check_cash_flow_detail_vs_journal,
    check_cash_flow_detail_vs_statement,
    check_journal_voucher_balance,
    check_trial_balance_vs_balance_sheet,
)
from fsa.core.engine.reclassification_checks import (
    check_reclassification_rules,
    check_reclassification_vs_balance_sheet,
)
from fsa.core.engine.supplementary_checks import (
    check_internal_cash_flow_vs_statement,
    check_related_party_purchase_breakdown,
    check_sales_detail_consistency,
    check_sales_vs_income_statement,
)
from fsa.core.models.detail import DetailDataset
from fsa.core.models.report import Report, ReportType
from fsa.core.models.result import ValidationSummary

_DEFAULT_TB_BS_MAPPINGS: dict[str, dict[str, object]] = {
    "monetary_funds": {"codes": ("1001", "1002", "1012"), "side": "debit"},
    "accounts_receivable": {"codes": ("1122",), "side": "debit"},
    "accounts_payable": {"codes": ("2202",), "side": "credit"},
}


@dataclass(frozen=True)
class DetailCheckConfig:
    """明细检查配置（口径可按主体覆盖）。

    Attributes:
        tolerance: 明细勾稽金额容差（元）
        cash_equivalent_codes: 现金等价物科目编码
        tb_to_bs_mappings: 余额表 -> 资产负债表映射
        reclass_pairs: 重分类科目对（标准科目 -> 目标标准科目），
            None 时使用 DEFAULT_RECLASS_PAIRS
        balance_sheet_accounts: 报表项目 key -> 标准科目，
            None 时使用 DEFAULT_BALANCE_SHEET_ACCOUNTS
        margin_tolerance: 毛利率核对容差（相对比例），None 时默认 0.01
    """

    tolerance: float = 0.01
    cash_equivalent_codes: tuple[str, ...] = ("1001", "1002")
    tb_to_bs_mappings: dict[str, dict[str, object]] = field(
        default_factory=lambda: dict(_DEFAULT_TB_BS_MAPPINGS)
    )
    reclass_pairs: dict[str, tuple[str, ...]] | None = None
    balance_sheet_accounts: dict[str, str] | None = None
    margin_tolerance: float | None = None


class DetailValidationService:
    """执行明细勾稽检查并汇总结果。"""

    def __init__(self, config: DetailCheckConfig | None = None) -> None:
        self._config = config or DetailCheckConfig()

    def validate(
        self,
        dataset: DetailDataset,
        reports: dict[ReportType, Report],
    ) -> ValidationSummary:
        """对明细数据集执行全部已实现的 L2 检查。"""
        results = check_journal_voucher_balance(dataset, self._config.tolerance)
        results += check_cash_flow_detail_vs_statement(
            dataset, reports, self._config.tolerance
        )
        results += check_cash_flow_detail_vs_journal(
            dataset, self._config.cash_equivalent_codes, self._config.tolerance
        )
        results += check_trial_balance_vs_balance_sheet(
            dataset, reports, self._config.tb_to_bs_mappings, self._config.tolerance
        )
        results += check_cash_flow_classification(
            dataset, self._config.cash_equivalent_codes, self._config.tolerance
        )
        results.append(
            check_cash_flow_coverage(
                dataset, self._config.cash_equivalent_codes, self._config.tolerance
            )
        )
        results += check_reclassification_rules(
            dataset, self._config.tolerance, self._config.reclass_pairs
        )
        results += check_reclassification_vs_balance_sheet(
            dataset,
            reports,
            self._config.tolerance,
            self._config.balance_sheet_accounts,
        )
        results += check_related_party_purchase_breakdown(dataset, self._config.tolerance)
        results += check_sales_detail_consistency(
            dataset, self._config.tolerance, self._config.margin_tolerance
        )
        results += check_sales_vs_income_statement(
            dataset, reports, self._config.tolerance
        )
        results += check_internal_cash_flow_vs_statement(
            dataset, reports, self._config.tolerance
        )

        passed = sum(1 for result in results if result.passed)
        failed = sum(1 for result in results if not result.passed and not result.errored)
        errored = sum(1 for result in results if result.errored)
        skipped = sum(1 for result in results if result.skipped)
        return ValidationSummary(
            period=dataset.period,
            total=len(results),
            passed=passed,
            failed=failed,
            errored=errored,
            skipped=skipped,
            results=results,
            report_types=list(reports.keys()),
        )
