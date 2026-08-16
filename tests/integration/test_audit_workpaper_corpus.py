"""审计底稿样式全套报表语料回归测试。

语料由 tests/fixtures/generate_audit_workpaper_corpus.py 生成,
特点:
- 每张表带审计底稿表头 (被审计单位/报表名称/会企编号/截止日/编制复核留痕)
- 三大主表金额互相勾稽, 同时含科目余额表/序时账/现金流量明细
- 预埋两处差异: BS-BAL-004 权益组成少计 5 万; CF-DTL-001 现金流明细仅部分覆盖

本测试不依赖 git 仓库内的二进制 fixture (tests/fixtures/real_reports 被忽略),
每次在 tmp_path 现场生成, 保证可重复且不产生大文件提交。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from fsa.core.engine.registry import RuleRegistry
from fsa.core.importer.detail_importer import DetailImporter
from fsa.core.importer.importer import ImportService
from fsa.core.models.report import ReportType
from fsa.services.detail_validation_service import DetailValidationService
from fsa.services.validation_service import ValidationService

_GENERATOR = Path(__file__).resolve().parents[1] / "fixtures" / ("generate_audit_workpaper_corpus.py")


def _generate_corpus(output: Path) -> Path:
    """现场生成审计底稿样式语料工作簿。"""
    spec = importlib.util.spec_from_file_location("generate_audit_workpaper_corpus", _GENERATOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.generate(output)


@pytest.fixture(scope="module")
def corpus_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """生成并返回审计底稿样式全套报表工作簿。"""
    return _generate_corpus(tmp_path_factory.mktemp("workpaper") / "审计底稿样式_全套报表.xlsx")


@pytest.fixture(scope="module")
def imported_reports(corpus_path: Path):
    """从语料导入的三大主表 Report 列表。"""
    return ImportService(period="2024-12").import_file(str(corpus_path))


@pytest.fixture(scope="module")
def registry() -> RuleRegistry:
    """内置 CAS 规则库。"""
    return RuleRegistry.from_json("cas_gouji_rule_library.json")


@pytest.fixture(scope="module")
def validation_summary(imported_reports, registry: RuleRegistry):
    """语料三大主表的校验结果。"""
    return ValidationService(registry).validate(imported_reports, "2024-12")


@pytest.fixture(scope="module")
def detail_dataset(corpus_path: Path):
    """语料中科目余额表/序时账/现金流量明细的解析结果。"""
    return DetailImporter(period="2024-12").import_file(str(corpus_path))


@pytest.fixture(scope="module")
def detail_summary(imported_reports, detail_dataset):
    """语料明细勾稽校验结果。"""
    reports = {report.report_type: report for report in imported_reports}
    return DetailValidationService().validate(detail_dataset, reports)


# ── 主表导入 ──


class TestWorkpaperImport:
    """审计底稿表头不应干扰主表识别与提取。"""

    def test_three_main_reports_identified(self, imported_reports) -> None:
        """工作簿应识别出三大主表, 底稿说明/科目余额表等不混入主表。"""
        assert {report.report_type for report in imported_reports} == {
            ReportType.BALANCE_SHEET,
            ReportType.INCOME_STATEMENT,
            ReportType.CASH_FLOW_STATEMENT,
        }

    def test_unit_and_no_warning(self, imported_reports) -> None:
        """表头"单位：元"被识别, 且无单位换算告警。"""
        for report in imported_reports:
            assert report.amount_unit == "元"
            assert report.unit_warning == ""

    def test_balance_sheet_items(self, imported_reports) -> None:
        """底稿表头后的 36 个资产负债表项目全部提取。"""
        bs = next(r for r in imported_reports if r.report_type == ReportType.BALANCE_SHEET)
        amounts = {item.key: item.amount for item in bs.items}
        assert len(bs.items) == 36
        assert amounts["monetary_funds"] == 2_000_000.0
        assert amounts["accounts_receivable"] == 800_000.0
        assert amounts["current_assets"] == 4_500_000.0
        assert amounts["non_current_assets"] == 4_500_000.0
        assert amounts["asset_total"] == 9_000_000.0
        assert amounts["liability_total"] == 4_000_000.0
        assert amounts["other_comprehensive_income"] == 50_000.0
        assert amounts["undistributed_profit"] == 1_200_000.0
        assert amounts["equity_total"] == 5_000_000.0

    def test_income_statement_items(self, imported_reports) -> None:
        """利润表项目金额与语料一致。"""
        is_report = next(r for r in imported_reports if r.report_type == ReportType.INCOME_STATEMENT)
        amounts = {item.key: item.amount for item in is_report.items}
        assert len(is_report.items) == 21
        assert amounts["revenue"] == 5_000_000.0
        assert amounts["operating_cost"] == 3_000_000.0
        assert amounts["operating_profit"] == 920_000.0
        assert amounts["total_profit"] == 940_000.0
        assert amounts["income_tax_expense"] == 235_000.0
        assert amounts["net_profit"] == 705_000.0
        assert amounts["total_comprehensive_income"] == 725_000.0

    def test_cash_flow_items(self, imported_reports) -> None:
        """现金流量表项目金额与语料一致。"""
        cf = next(r for r in imported_reports if r.report_type == ReportType.CASH_FLOW_STATEMENT)
        amounts = {item.key: item.amount for item in cf.items}
        assert len(cf.items) == 28
        assert amounts["operating_net"] == 830_000.0
        assert amounts["investing_net"] == -440_000.0
        assert amounts["financing_net"] == 100_000.0
        assert amounts["fx_effect"] == 10_000.0
        assert amounts["net_increase_cash"] == 500_000.0
        assert amounts["beginning_cash_equiv"] == 1_500_000.0
        assert amounts["ending_cash_equiv"] == 2_000_000.0


# ── 主表校验 ──


class TestWorkpaperValidation:
    """语料应稳定命中"通过 + 预埋差异"两类结果。"""

    def test_balanced_rules_pass(self, validation_summary) -> None:
        """勾稽正确的表内平衡规则全部通过。"""
        by_id = {result.rule_id: result for result in validation_summary.results}
        for rule_id in (
            "BS-BAL-001",
            "BS-BAL-002",
            "BS-BAL-003",
            "IS-BAL-002",
            "IS-BAL-003",
            "IS-BAL-005",
            "CF-BAL-001",
            "CF-BAL-004",
        ):
            assert by_id[rule_id].passed is True, by_id[rule_id].message
            assert by_id[rule_id].errored is False

    def test_seeded_bs_bal_004_diff_detected(self, validation_summary) -> None:
        """预埋差异: 其他综合收益 5 万未计入权益合计, BS-BAL-004 应不通过。"""
        result = next(r for r in validation_summary.results if r.rule_id == "BS-BAL-004")
        assert result.passed is False
        assert result.errored is False
        assert abs(result.diff - 50_000.0) < 0.01

    def test_sce_bal_002_skips_for_standalone_bs(self, validation_summary) -> None:
        """单体资产负债表无"归属于母公司权益"时应跳过 SCE-BAL-002, 不误报。"""
        result = next(r for r in validation_summary.results if r.rule_id == "SCE-BAL-002")
        assert result.skipped is True
        assert "未定义" in result.message

    def test_no_unexpected_failures(self, validation_summary) -> None:
        """除预埋的 BS-BAL-004 外, 不应出现其他未预期的不通过/异常。"""
        failed_ids = {
            result.rule_id
            for result in validation_summary.results
            if not result.passed and not result.errored and not result.skipped
        }
        assert failed_ids == {"BS-BAL-004"}
        assert validation_summary.errored == 0


# ── 明细附表导入与勾稽 ──


class TestWorkpaperDetails:
    """科目余额表/序时账/现金流量明细与主表联动。"""

    def test_trial_balance_parsed(self, detail_dataset) -> None:
        """底稿表头下的科目余额表 3 行被解析, 金额按元保留。"""
        rows = detail_dataset.trial_balance
        assert len(rows) == 3
        by_code = {row.account_code: row for row in rows}
        assert by_code["1002"].ending_debit == 2_000_000.0
        assert by_code["1122"].ending_debit == 800_000.0
        assert by_code["2202"].ending_credit == 1_200_000.0
        assert detail_dataset.unit_warnings == []

    def test_journal_parsed_and_balanced(self, detail_dataset) -> None:
        """序时账两张凭证行解析, 借贷各 50 万。"""
        assert len(detail_dataset.journal) == 2
        assert {row.direction for row in detail_dataset.journal} == {"借", "贷"}
        assert sum(row.amount for row in detail_dataset.journal) == 1_000_000.0

    def test_cash_flow_detail_parsed(self, detail_dataset) -> None:
        """现金流量明细 2 行解析。"""
        rows = detail_dataset.cash_flow_detail
        assert len(rows) == 2
        assert {row.project for row in rows} == {
            "销售商品、提供劳务收到的现金",
            "购买商品、接受劳务支付的现金",
        }

    def test_tb_matches_bs(self, detail_summary) -> None:
        """余额表三大科目与资产负债表核对全部一致。"""
        tb_results = [result for result in detail_summary.results if result.rule_id == "TB-BS-001"]
        assert len(tb_results) == 3
        assert all(result.passed for result in tb_results)

    def test_seeded_cf_detail_coverage_diff(self, detail_summary) -> None:
        """预埋差异: 现金流量明细仅覆盖部分主表流入/流出, 应产生 2 条不通过。"""
        failed = [result for result in detail_summary.results if result.rule_id == "CF-DTL-001" and not result.passed]
        assert len(failed) == 2
        assert any("销售商品、提供劳务收到的现金" in r.message for r in failed)
        assert any("购买商品、接受劳务支付的现金" in r.message for r in failed)
        assert abs(sum(r.diff for r in failed) + 7_200_000.0) < 0.01

    def test_journal_voucher_balance(self, detail_summary) -> None:
        """序时账逐凭证借贷平衡检查通过。"""
        result = next(r for r in detail_summary.results if r.rule_id == "JNL-BAL-001")
        assert result.passed is True
