"""端到端集成测试: Excel 导入 -> 校验 -> 验证结果。

验证完整管线:
1. Excel 文件读取 -> 识别三大报表 -> 提取科目数据
2. 导入的 Report 对象包含正确的科目和金额
3. ValidationService 执行规则库全部规则 -> 产出 ValidationSummary
4. 校验结果中: 表内平衡规则全部通过, 部分跨表规则因缺项异常
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fsa.core.engine.registry import RuleRegistry
from fsa.core.importer.importer import ImportService
from fsa.core.models.report import ReportType

# ── 导入测试 ──


class TestExcelImport:
    """Excel 导入管线测试。"""

    def test_import_returns_three_reports(self, imported_reports) -> None:
        """导入示例 Excel 应返回 3 张报表。"""
        assert len(imported_reports) == 3

    def test_imported_report_types(self, imported_reports) -> None:
        """三张报表分别为资产负债表/利润表/现金流量表。"""
        types = {r.report_type for r in imported_reports}
        assert ReportType.BALANCE_SHEET in types
        assert ReportType.INCOME_STATEMENT in types
        assert ReportType.CASH_FLOW_STATEMENT in types

    def test_balance_sheet_items_extracted(self, imported_reports) -> None:
        """资产负债表的核心科目被正确提取。"""
        bs = next(
            r for r in imported_reports
            if r.report_type == ReportType.BALANCE_SHEET
        )
        keys = {item.key for item in bs.items}
        # 核心平衡变量
        assert "asset_total" in keys
        assert "liability_total" in keys
        assert "equity_total" in keys
        assert "current_assets" in keys
        assert "non_current_assets" in keys
        assert "current_liabilities" in keys
        assert "non_current_liabilities" in keys
        # 权益组成
        assert "paid_in_capital" in keys
        assert "capital_reserve" in keys
        assert "surplus_reserve" in keys
        assert "undistributed_profit" in keys

    def test_balance_sheet_amounts_correct(self, imported_reports) -> None:
        """资产负债表金额与 Excel 数据一致。"""
        bs = next(
            r for r in imported_reports
            if r.report_type == ReportType.BALANCE_SHEET
        )
        amounts = {item.key: item.amount for item in bs.items}
        assert amounts["asset_total"] == 9_000_000.0
        assert amounts["liability_total"] == 4_000_000.0
        assert amounts["equity_total"] == 5_000_000.0
        assert amounts["current_assets"] == 5_000_000.0
        assert amounts["non_current_assets"] == 4_000_000.0

    def test_income_statement_items_extracted(self, imported_reports) -> None:
        """利润表核心科目被正确提取。"""
        is_report = next(
            r for r in imported_reports
            if r.report_type == ReportType.INCOME_STATEMENT
        )
        keys = {item.key for item in is_report.items}
        assert "revenue" in keys
        assert "operating_cost" in keys
        assert "operating_profit" in keys
        assert "total_profit" in keys
        assert "net_profit" in keys
        assert "income_tax_expense" in keys

    def test_income_statement_amounts_correct(self, imported_reports) -> None:
        """利润表金额与 Excel 数据一致。"""
        is_report = next(
            r for r in imported_reports
            if r.report_type == ReportType.INCOME_STATEMENT
        )
        amounts = {item.key: item.amount for item in is_report.items}
        assert amounts["revenue"] == 5_000_000.0
        assert amounts["operating_cost"] == 3_500_000.0
        assert amounts["net_profit"] == 600_000.0
        assert amounts["income_tax_expense"] == 200_000.0

    def test_cash_flow_items_extracted(self, imported_reports) -> None:
        """现金流量表核心科目被正确提取。"""
        cf = next(
            r for r in imported_reports
            if r.report_type == ReportType.CASH_FLOW_STATEMENT
        )
        keys = {item.key for item in cf.items}
        assert "operating_net" in keys
        assert "investing_net" in keys
        assert "financing_net" in keys
        assert "net_increase_cash" in keys
        assert "beginning_cash_equiv" in keys
        assert "ending_cash_equiv" in keys

    def test_cash_flow_amounts_correct(self, imported_reports) -> None:
        """现金流量表金额与 Excel 数据一致。"""
        cf = next(
            r for r in imported_reports
            if r.report_type == ReportType.CASH_FLOW_STATEMENT
        )
        amounts = {item.key: item.amount for item in cf.items}
        assert amounts["operating_net"] == 800_000.0
        assert amounts["investing_net"] == -300_000.0
        assert amounts["financing_net"] == -200_000.0
        assert amounts["net_increase_cash"] == 300_000.0
        assert amounts["ending_cash_equiv"] == 2_000_000.0

    def test_import_nonexistent_file_raises(self, tmp_path: Path) -> None:
        """导入不存在的文件应抛出 FileNotFoundError。"""
        importer = ImportService(period="2024-12")
        with pytest.raises(FileNotFoundError):
            importer.import_file(str(tmp_path / "nonexistent.xlsx"))


# ── 校验测试 ──


class TestValidationPipeline:
    """校验管线端到端测试。"""

    def test_validation_produces_summary(self, validation_summary) -> None:
        """校验服务应产出 ValidationSummary。"""
        assert validation_summary is not None
        assert validation_summary.total > 0

    def test_bs_bal_001_passes(self, validation_summary) -> None:
        """BS-BAL-001: 资产 = 负债 + 所有者权益 (9M = 4M + 5M) 应通过。"""
        result = next(
            r for r in validation_summary.results
            if r.rule_id == "BS-BAL-001"
        )
        assert result.passed is True
        assert result.errored is False
        assert abs(result.diff) < 0.01

    def test_bs_bal_002_passes(self, validation_summary) -> None:
        """BS-BAL-002: 流动+非流动资产 = 资产总计 (5M + 4M = 9M) 应通过。"""
        result = next(
            r for r in validation_summary.results
            if r.rule_id == "BS-BAL-002"
        )
        assert result.passed is True

    def test_bs_bal_003_passes(self, validation_summary) -> None:
        """BS-BAL-003: 流动+非流动负债 = 负债合计 (3M + 1M = 4M) 应通过。"""
        result = next(
            r for r in validation_summary.results
            if r.rule_id == "BS-BAL-003"
        )
        assert result.passed is True

    def test_bs_bal_004_passes(self, validation_summary) -> None:
        """BS-BAL-004: 权益各组成 = 权益合计 (3M+0.5M+0+0.2M+1.3M-0 = 5M) 应通过。"""
        result = next(
            r for r in validation_summary.results
            if r.rule_id == "BS-BAL-004"
        )
        assert result.passed is True

    def test_passed_count_at_least_four(self, validation_summary) -> None:
        """至少 4 条 BS-BAL 规则通过。"""
        assert validation_summary.passed >= 4

    def test_no_failed_results_for_balanced_items(
        self, validation_summary
    ) -> None:
        """内部平衡规则的差额应为 0 (容差内)。"""
        bs_results = [
            r for r in validation_summary.results
            if r.rule_id.startswith("BS-BAL")
            and not r.errored
        ]
        for result in bs_results:
            assert abs(result.diff) <= result.tolerance, (
                f"{result.rule_id} 差额 {result.diff} 超过容差 {result.tolerance}"
            )

    def test_errored_results_have_messages(self, validation_summary) -> None:
        """异常结果必须包含中文消息说明原因。"""
        errored = [
            r for r in validation_summary.results if r.errored
        ]
        for result in errored:
            assert result.message, f"{result.rule_id} 异常但无消息"
            assert len(result.message) > 0

    def test_all_results_have_rule_ids(self, validation_summary) -> None:
        """每条结果都有规则 ID。"""
        for result in validation_summary.results:
            assert result.rule_id, "结果缺少 rule_id"
            assert result.rule_name, "结果缺少 rule_name"

    def test_summary_counts_are_consistent(
        self, validation_summary, sample_registry: RuleRegistry
    ) -> None:
        """汇总中的 passed + failed + errored = total (skipped 单独计)。

        skipped + total = 启用的规则总数 (含缺少报表而跳过的规则)。
        规则总数从注册表动态读取, 规则库升级时无需修改本测试。
        """
        s = validation_summary
        assert s.passed + s.failed + s.errored == s.total
        assert s.skipped + s.total == len(sample_registry.get_active())


# ── 数据一致性测试 ──


class TestDataConsistency:
    """导入数据的内部一致性测试。"""

    def test_bs_equation_holds(self, imported_reports) -> None:
        """资产 = 负债 + 权益 (导入数据层面验证)。"""
        bs = next(
            r for r in imported_reports
            if r.report_type == ReportType.BALANCE_SHEET
        )
        amounts = {item.key: item.amount for item in bs.items}
        assert abs(
            amounts["asset_total"]
            - amounts["liability_total"]
            - amounts["equity_total"]
        ) < 0.01

    def test_bs_asset_decomposition(self, imported_reports) -> None:
        """流动 + 非流动资产 = 资产总计。"""
        bs = next(
            r for r in imported_reports
            if r.report_type == ReportType.BALANCE_SHEET
        )
        amounts = {item.key: item.amount for item in bs.items}
        assert abs(
            amounts["current_assets"]
            + amounts["non_current_assets"]
            - amounts["asset_total"]
        ) < 0.01

    def test_cf_net_increase_equation(self, imported_reports) -> None:
        """经营 + 投资 + 筹资 = 现金净增加。"""
        cf = next(
            r for r in imported_reports
            if r.report_type == ReportType.CASH_FLOW_STATEMENT
        )
        amounts = {item.key: item.amount for item in cf.items}
        assert abs(
            amounts["operating_net"]
            + amounts["investing_net"]
            + amounts["financing_net"]
            - amounts["net_increase_cash"]
        ) < 0.01

    def test_cf_ending_equals_beginning_plus_increase(
        self, imported_reports
    ) -> None:
        """期末现金 = 期初 + 净增加。"""
        cf = next(
            r for r in imported_reports
            if r.report_type == ReportType.CASH_FLOW_STATEMENT
        )
        amounts = {item.key: item.amount for item in cf.items}
        assert abs(
            amounts["ending_cash_equiv"]
            - amounts["beginning_cash_equiv"]
            - amounts["net_increase_cash"]
        ) < 0.01

    def test_monetary_funds_match_ending_cash(
        self, imported_reports
    ) -> None:
        """资产负债表货币资金 = 现金流量表期末现金。"""
        bs = next(
            r for r in imported_reports
            if r.report_type == ReportType.BALANCE_SHEET
        )
        cf = next(
            r for r in imported_reports
            if r.report_type == ReportType.CASH_FLOW_STATEMENT
        )
        bs_amounts = {item.key: item.amount for item in bs.items}
        cf_amounts = {item.key: item.amount for item in cf.items}
        assert abs(
            bs_amounts.get("monetary_funds", 0)
            - cf_amounts.get("ending_cash_equiv", 0)
        ) < 0.01
