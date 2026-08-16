"""往来重分类检查（附表 3）。"""

from __future__ import annotations

from collections import defaultdict

from fsa.core.importer.name_mapper import clean_name
from fsa.core.models.detail import DetailDataset
from fsa.core.models.report import Report, ReportType
from fsa.core.models.result import ValidationResult
from fsa.core.models.rule import Severity

# 统一别名源: 标准往来科目 -> 企业常用别名。
# RC-001 重分类目标科目与 RC-002 资产负债表项目核对共用此别名源，
# 避免两处别名集合不一致导致同一科目命中结果不同（P3 可追溯、P2 确定性）。
ACCOUNT_ALIASES: dict[str, tuple[str, ...]] = {
    "应收账款": ("应收账款",),
    "预收款项": ("预收款项", "预收账款"),
    "应付账款": ("应付账款",),
    "预付款项": ("预付款项", "预付账款"),
    "其他应收款": ("其他应收款",),
    "其他应付款": ("其他应付款",),
}

# 负数重分类: 标准科目 -> 重分类目标标准科目（缺省配置，可经 entity_config 覆写）。
# 目标标准科目的别名见 ACCOUNT_ALIASES，查找时自动展开。
DEFAULT_RECLASS_PAIRS: dict[str, tuple[str, ...]] = {
    "应收账款": ("预收款项",),
    "预收款项": ("应收账款",),
    "应付账款": ("预付款项",),
    "预付款项": ("应付账款",),
    "其他应收款": ("其他应付款",),
    "其他应付款": ("其他应收款",),
}

# 报表项目 key -> 标准科目（缺省配置，可经 entity_config 覆写）
DEFAULT_BALANCE_SHEET_ACCOUNTS: dict[str, str] = {
    "accounts_receivable": "应收账款",
    "advance_from_customers": "预收款项",
    "accounts_payable": "应付账款",
    "prepayments": "预付款项",
    "other_receivable": "其他应收款",
    "other_payable": "其他应付款",
}


def _canonical_account(account: str) -> str | None:
    """返回科目名对应的标准科目（含别名解析）；未识别返回 None。"""
    for canonical, aliases in ACCOUNT_ALIASES.items():
        if account in aliases:
            return canonical
    return None


def _reclass_target_accounts(
    original_account: str,
    reclass_pairs: dict[str, tuple[str, ...]],
) -> tuple[str, ...]:
    """返回某科目重分类后允许的目标科目集合（含企业别名）。

    原始科目先解析为标准科目（未识别时按原文），
    目标标准科目的别名一并纳入，保证「预收账款」与「预收款项」命中一致。
    """
    canonical = _canonical_account(original_account) or original_account
    targets: list[str] = []
    for target in reclass_pairs.get(canonical, ()):
        targets.extend(ACCOUNT_ALIASES.get(target, (target,)))
    return tuple(targets)


def check_reclassification_rules(
    dataset: DetailDataset,
    tolerance: float,
    reclass_pairs: dict[str, tuple[str, ...]] | None = None,
) -> list[ValidationResult]:
    """核对负数重分类规则：负数转正、科目落到对应往来科目。

    Args:
        dataset: 明细数据集
        tolerance: 容差（元）
        reclass_pairs: 重分类科目对（标准科目 -> 目标标准科目），
            None 时使用 DEFAULT_RECLASS_PAIRS（可经 entity_config 覆写）。
    """
    pairs = DEFAULT_RECLASS_PAIRS if reclass_pairs is None else reclass_pairs
    mismatches: list[str] = []
    for row in dataset.reclassifications:
        book = row.book_amount
        reclassified = row.reclassified_amount
        if book < -tolerance:
            amount_ok = abs(reclassified + book) <= tolerance
            account_ok = row.reclassified_account in _reclass_target_accounts(
                row.original_account, pairs
            )
        elif book > tolerance:
            amount_ok = abs(reclassified - book) <= tolerance
            # 与负数路径口径一致: 经别名归一后比较，避免"预收款项/预收账款"类差异误报 (P1)
            original_canonical = _canonical_account(row.original_account) or row.original_account
            reclassified_canonical = (
                _canonical_account(row.reclassified_account) or row.reclassified_account
            )
            account_ok = reclassified_canonical == original_canonical
        else:
            continue
        if not amount_ok or not account_ok:
            mismatches.append(
                f"行{row.row}「{row.counterparty}」账面 {book:,.2f} → "
                f"{row.reclassified_account} {reclassified:,.2f}"
            )

    passed = not mismatches
    message = (
        f"往来重分类规则: 校验通过（共 {len(dataset.reclassifications)} 行）"
        if passed
        else f"往来重分类规则: {len(mismatches)} 行与重分类规则不符。"
        + "；".join(mismatches[:5])
    )
    return [
        ValidationResult(
            rule_id="RC-001",
            rule_name="往来重分类规则",
            passed=passed,
            severity=Severity.ERROR,
            left_value=0.0,
            right_value=0.0,
            diff=float(len(mismatches)),
            tolerance=tolerance,
            formula="负数重分类转正 + 科目对应",
            message=message,
            category="L2-明细勾稽",
        )
    ]


def check_reclassification_vs_balance_sheet(
    dataset: DetailDataset,
    reports: dict[ReportType, Report],
    tolerance: float,
    balance_sheet_accounts: dict[str, str] | None = None,
) -> list[ValidationResult]:
    """核对重分类后各往来科目合计与资产负债表项目。

    Args:
        dataset: 明细数据集
        reports: 主表报表字典（需含资产负债表）
        tolerance: 容差（元）
        balance_sheet_accounts: 报表项目 key -> 标准科目，
            None 时使用 DEFAULT_BALANCE_SHEET_ACCOUNTS（可经 entity_config 覆写）。
    """
    accounts_cfg = (
        DEFAULT_BALANCE_SHEET_ACCOUNTS
        if balance_sheet_accounts is None
        else balance_sheet_accounts
    )
    report = reports.get(ReportType.BALANCE_SHEET)
    if report is None:
        return [
            ValidationResult(
                rule_id="RC-002",
                rule_name="重分类后科目=资产负债表",
                passed=True,
                severity=Severity.INFO,
                left_value=0.0,
                right_value=0.0,
                diff=0.0,
                tolerance=tolerance,
                formula="",
                message="重分类后科目=资产负债表: 跳过 - 缺少资产负债表",
                skipped=True,
                category="L2-明细勾稽",
            )
        ]

    statement = {item.key: item.amount for item in report.items}
    sums: dict[str, float] = defaultdict(float)
    for row in dataset.reclassifications:
        account = clean_name(row.reclassified_account)
        canonical = _canonical_account(account)
        for key, standard in accounts_cfg.items():
            if account == standard or (canonical is not None and canonical == standard):
                sums[key] += row.reclassified_amount
                break

    results: list[ValidationResult] = []
    for key in accounts_cfg:
        expected = sums.get(key, 0.0)
        actual = statement.get(key)
        if actual is None:
            continue
        diff = expected - actual
        passed = abs(diff) <= tolerance
        results.append(
            ValidationResult(
                rule_id="RC-002",
                rule_name="重分类后科目=资产负债表",
                passed=passed,
                # 坏账准备等备抵科目的口径差异常见且不构成确定差错 -> 降为 WARNING (P1)
                severity=Severity.WARNING,
                left_value=expected,
                right_value=actual,
                diff=diff,
                tolerance=tolerance,
                formula="重分类后科目合计 == 报表项目",
                message=(
                    f"重分类后「{key}」合计 {expected:,.2f} vs 报表 {actual:,.2f}: "
                    f"{'一致' if passed else f'差额 {diff:,.2f}（差异可能来自坏账准备等报表调整，需人工确认）'}"
                ),
                category="L2-明细勾稽",
            )
        )
    return results
