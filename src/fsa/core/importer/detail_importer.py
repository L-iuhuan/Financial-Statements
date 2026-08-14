"""附表 2 明细导入器: 科目余额表 / 序时账 / 现金流量明细。

按表头特征识别工作表类型（不依赖工作表名），并按"本月 / 1-本月"
分别归入当前期间与累计数据集。
行级解析逻辑在 detail_parsers 中，本模块只负责路由与数据集组织。
"""

from __future__ import annotations

import re

from loguru import logger

from fsa.core.importer.detail_parsers import (
    parse_cash_flow_row,
    parse_internal_cash_flow_row,
    parse_journal_row,
    parse_purchase_row,
    parse_reclassification_row,
    parse_sales_row,
    parse_trial_balance_row,
)
from fsa.core.importer.excel_reader import RawSheetData, read_excel
from fsa.core.models.detail import DetailDataset

_CUMULATIVE_KEYWORDS = ("1-本月", "1- 本月", "本年累计")


class DetailImporter:
    """明细数据导入服务。"""

    def __init__(self, period: str = "") -> None:
        self.period = period

    def import_file(self, file_path: str) -> DetailDataset:
        """读取文件并解析为 DetailDataset（含 Excel COM 自动回退）。"""
        raw_data = read_excel(file_path)
        dataset = DetailDataset(source_file=str(file_path), period=self.period)

        for sheet_name, raw in raw_data.items():
            if _is_trial_balance(raw.headers):
                self._collect_trial_balance(dataset, sheet_name, raw)
            elif _is_journal(raw.headers):
                self._collect_journal(dataset, sheet_name, raw)
            elif _is_cash_flow_detail(raw.headers):
                self._collect_cash_flow_detail(dataset, sheet_name, raw)
            elif _is_reclassification(raw.headers):
                self._collect_reclassification(dataset, raw)
            elif _is_related_party_purchase(raw.headers):
                self._collect_related_party_purchase(dataset, raw)
            elif _is_sales_detail(raw.headers):
                self._collect_sales_detail(dataset, raw)
            elif _is_internal_cash_flow(raw.headers):
                self._collect_internal_cash_flow(dataset, raw)

        logger.info(
            f"明细导入完成: 余额表 {len(dataset.trial_balance)} 行, "
            f"序时账 {len(dataset.journal)} 行, "
            f"现金流明细 {len(dataset.cash_flow_detail)} 行"
        )
        return dataset

    def _collect_trial_balance(
        self, dataset: DetailDataset, sheet_name: str, raw: RawSheetData
    ) -> None:
        """解析科目余额表工作表。"""
        rows = [
            parse_trial_balance_row(raw.headers, row)
            for row in raw.rows
        ]
        rows = [r for r in rows if r is not None]
        target = (
            dataset.trial_balance
            if _is_cumulative(sheet_name)
            else dataset.trial_balance_current
        )
        target.extend(rows)

    def _collect_journal(
        self, dataset: DetailDataset, sheet_name: str, raw: RawSheetData
    ) -> None:
        """解析序时账工作表，按口径分流入累计/本月数据集。"""
        rows = [parse_journal_row(raw.headers, row) for row in raw.rows]
        rows = [r for r in rows if r is not None]
        if _is_cumulative(sheet_name):
            dataset.journal.extend(rows)
        else:
            if rows:
                logger.warning(
                    f"工作表「{sheet_name}」为单月口径序时账，已归入 journal_current"
                    f"（共 {len(rows)} 行），不参与累计口径勾稽"
                )
                dataset.journal_current.extend(rows)

    def _collect_cash_flow_detail(
        self, dataset: DetailDataset, sheet_name: str, raw: RawSheetData
    ) -> None:
        """解析现金流量明细工作表，按口径分流入累计/本月数据集。"""
        rows = [parse_cash_flow_row(raw.headers, row) for row in raw.rows]
        rows = [r for r in rows if r is not None]
        if _is_cumulative(sheet_name):
            dataset.cash_flow_detail.extend(rows)
        else:
            if rows:
                logger.warning(
                    f"工作表「{sheet_name}」为单月口径现金流量明细，已归入 "
                    f"cash_flow_detail_current（共 {len(rows)} 行），不参与累计口径勾稽"
                )
                dataset.cash_flow_detail_current.extend(rows)

    def _collect_reclassification(
        self, dataset: DetailDataset, raw: RawSheetData
    ) -> None:
        """解析往来重分类明细工作表。"""
        rows = [parse_reclassification_row(raw.headers, row) for row in raw.rows]
        dataset.reclassifications.extend([r for r in rows if r is not None])

    def _collect_related_party_purchase(
        self, dataset: DetailDataset, raw: RawSheetData
    ) -> None:
        """解析关联方采购明细工作表。"""
        rows = [parse_purchase_row(raw.headers, row) for row in raw.rows]
        dataset.related_party_purchases.extend([r for r in rows if r is not None])

    def _collect_sales_detail(
        self, dataset: DetailDataset, raw: RawSheetData
    ) -> None:
        """解析销售收入成本明细工作表。"""
        rows = [parse_sales_row(raw.headers, row) for row in raw.rows]
        dataset.sales_details.extend([r for r in rows if r is not None])

    def _collect_internal_cash_flow(
        self, dataset: DetailDataset, raw: RawSheetData
    ) -> None:
        """解析内部交易现金流量明细工作表。"""
        rows = [parse_internal_cash_flow_row(raw.headers, row) for row in raw.rows]
        dataset.internal_cash_flows.extend([r for r in rows if r is not None])


def _is_trial_balance(headers: list[str]) -> bool:
    """按表头判断是否为科目余额表。"""
    joined = "".join(_normalize(h) for h in headers)
    return "科目编码" in joined and "余额借方" in joined


def _is_journal(headers: list[str]) -> bool:
    """按表头判断是否为序时账。"""
    joined = "".join(_normalize(h) for h in headers)
    return (
        "科目编码" in joined
        and "凭证号" in joined
        and "摘要" in joined
        and "方向" in joined
    )


def _is_cash_flow_detail(headers: list[str]) -> bool:
    """按表头判断是否为现金流量明细（区别于现金流量表主表）。"""
    joined = "".join(_normalize(h) for h in headers)
    return "现金流量项目" in joined and "方向" in joined


def _is_reclassification(headers: list[str]) -> bool:
    """按表头判断是否为往来重分类明细。"""
    joined = "".join(_normalize(h) for h in headers)
    return "重分类后科目" in joined and "账面余额" in joined


def _is_related_party_purchase(headers: list[str]) -> bool:
    """按表头判断是否为关联方采购明细。"""
    joined = "".join(_normalize(h) for h in headers)
    return "总采购金额" in joined and "对方单位名称" in joined


def _is_sales_detail(headers: list[str]) -> bool:
    """按表头判断是否为销售收入成本明细。"""
    joined = "".join(_normalize(h) for h in headers)
    return "销售收入金额" in joined and "销售成本金额" in joined


def _is_internal_cash_flow(headers: list[str]) -> bool:
    """按表头判断是否为内部交易现金流量明细。"""
    joined = "".join(_normalize(h) for h in headers)
    return "统计单位名称" in joined and "现金流量项目" in joined


def _is_cumulative(sheet_name: str) -> bool:
    """判断工作表是否为累计口径（1-本月）。"""
    return any(keyword in sheet_name for keyword in _CUMULATIVE_KEYWORDS)


def _normalize(value: str) -> str:
    """去除所有空白（含全角空格）。"""
    return re.sub(r"\s+", "", value)
