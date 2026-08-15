"""所有者权益变动表 (SCE) 提取器与集成测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

from fsa.core.importer.excel_reader import read_excel
from fsa.core.importer.importer import ImportService
from fsa.core.importer.sce_extractor import extract_sce_items
from fsa.core.models.report import ReportType

FIXTURE = (
    Path(__file__).resolve().parent.parent
    / "fixtures" / "real_reports" / "测试报表_含权益变动表.xlsx"
)


@pytest.fixture(scope="module")
def sce_raw():
    """读取夹具中的 SCE 工作表原始数据。"""
    data = read_excel(str(FIXTURE))
    return data["所有者权益变动表"]


@pytest.fixture(scope="module")
def sce_items(sce_raw):
    """提取 SCE 项目。"""
    return extract_sce_items(sce_raw)


def _amount(items, key):
    for it in items:
        if it.key == key:
            return it.amount
    raise KeyError(key)


class TestSceExtractor:
    """SCE 矩阵提取测试。"""

    def test_extracts_ending_values(self, sce_items) -> None:
        """年末余额行正确提取为 _ending。"""
        assert _amount(sce_items, "sce_paid_in_capital_ending") == 1000000.0
        assert _amount(sce_items, "sce_surplus_reserve_ending") == 300000.0
        assert _amount(sce_items, "sce_equity_total_ending") == 3000000.0

    def test_extracts_beginning_values(self, sce_items) -> None:
        """年初/上年年末行正确提取为 _beginning (上年年末=本年期初)。"""
        assert _amount(sce_items, "sce_paid_in_capital_beginning") == 1000000.0
        assert _amount(sce_items, "sce_undistributed_profit_beginning") == 870000.0

    def test_extracts_comprehensive_values(self, sce_items) -> None:
        """综合收益总额行正确提取为 _comprehensive。"""
        assert _amount(sce_items, "sce_undistributed_profit_comprehensive") == 330000.0
        assert _amount(sce_items, "sce_other_comprehensive_comprehensive") == 20000.0
        assert _amount(sce_items, "sce_equity_total_comprehensive") == 350000.0

    def test_ending_uses_year_end_row_not_prior(self, sce_items) -> None:
        """ending 取自'本年年末余额'行而非'上年年末余额' (分类正确性)。"""
        # 本年年末 盈余公积=300000, 上年年末=280000; 取正确行则为 300000
        assert _amount(sce_items, "sce_surplus_reserve_ending") == 300000.0

    def test_strips_minus_prefix(self, sce_items) -> None:
        """减:库存股 前缀正确剥离。"""
        assert _amount(sce_items, "sce_treasury_stock_ending") == 0.0

    def test_non_change_rows_skipped(self, sce_items) -> None:
        """本年增减变动/利润分配等非期初期末综合行不产生变量。"""
        keys = {it.key for it in sce_items}
        assert not any("_changes" in k or "_distribution" in k for k in keys)


class TestSceImportIntegration:
    """SCE 导入集成测试。"""

    def test_import_returns_four_reports(self) -> None:
        """导入 4 表工作簿返回 4 个报表, 含 SCE。"""
        reports = ImportService().import_file(str(FIXTURE))
        types = {r.report_type for r in reports}
        assert len(reports) == 4
        assert ReportType.STATEMENT_OF_CHANGES_IN_EQUITY in types

    def test_sce_report_has_items(self) -> None:
        """SCE 报表包含提取的矩阵项目。"""
        reports = ImportService().import_file(str(FIXTURE))
        sce = next(
            r for r in reports
            if r.report_type == ReportType.STATEMENT_OF_CHANGES_IN_EQUITY
        )
        assert len(sce.items) > 0
        keys = {it.key for it in sce.items}
        assert "sce_paid_in_capital_ending" in keys

    def test_excel_without_sce_still_works(self) -> None:
        """仅三大主表的工作簿不含 SCE, SCE 规则不受影响 (回归)。"""
        three_only = (
            Path(__file__).resolve().parent.parent
            / "fixtures" / "real_reports" / "贵州茅台_2023年报_三大报表.xlsx"
        )
        if not three_only.exists():
            pytest.skip("真实年报 fixture 缺失（合规红线：已移出 git，需手动放置）")
        reports = ImportService().import_file(str(three_only))
        types = {r.report_type for r in reports}
        assert ReportType.STATEMENT_OF_CHANGES_IN_EQUITY not in types


class TestSceMultiRowHeader:
    """测试权益变动表的多层表头（股本/资本公积 + 优先股/永续债等子层）。"""

    def test_component_columns_mapped_across_header_layers(self) -> None:
        """组件名分布在多层表头时仍能正确映射。"""
        from fsa.core.importer.excel_reader import RawSheetData

        raw = RawSheetData(
            name="所有者权益变动表",
            headers=["项目", "行次", "46174", "列4", "列5", "资本公积", "所有者权益合计"],
            header_rows=[
                ["项目", "行次", "46174", "", "", "资本公积", "所有者权益合计"],
                ["", "", "", "股本", "其他权益工具", "", ""],
                ["", "", "", "", "优先股", "", ""],
            ],
            rows=[
                {
                    "_row": 7,
                    "项目": "一、上年年末余额",
                    "行次": 1,
                    "列4": 1000000.0,
                    "资本公积": 2300000.0,
                    "所有者权益合计": 1312769.29,
                },
                {
                    "_row": 11,
                    "项目": "三、本年增减变动金额",
                    "行次": 6,
                    "所有者权益合计": -10228207.35,
                },
            ],
        )

        items = extract_sce_items(raw)
        keys = {item.key: item.amount for item in items}
        assert keys["sce_paid_in_capital_beginning"] == 1000000.0
        assert keys["sce_capital_reserve_beginning"] == 2300000.0
        assert keys["sce_equity_total_beginning"] == 1312769.29
