"""上市公司年报样式合并报表语料回归 (Excel 优先格式变体)。

语料: tests/fixtures/generate_listed_corpus.py
- 表名带"合并"前缀 (合并资产负债表/利润表/现金流量表/所有者权益变动表)
- 合并资产负债表为左右双栏 (资产 | 负债和所有者权益), 每侧含 行次/附注
- 合并口径含"归属于母公司所有者权益"与"少数股东权益"
- 金额自洽, 预期所有适用规则通过 (0 差异基线)
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from fsa.core.engine.registry import RuleRegistry
from fsa.core.importer.importer import ImportService
from fsa.core.models.report import ReportType
from fsa.services.validation_service import ValidationService

_GENERATOR = Path(__file__).resolve().parents[1] / "fixtures" / ("generate_listed_corpus.py")


def _generate_corpus(output: Path) -> Path:
    spec = importlib.util.spec_from_file_location("generate_listed_corpus", _GENERATOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.generate(output)


@pytest.fixture(scope="module")
def corpus_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return _generate_corpus(tmp_path_factory.mktemp("listed") / "上市公司年报样式_合并报表.xlsx")


@pytest.fixture(scope="module")
def imported_reports(corpus_path: Path):
    return ImportService(period="2024-12").import_file(str(corpus_path))


@pytest.fixture(scope="module")
def validation_summary(imported_reports):
    registry = RuleRegistry.from_json("cas_gouji_rule_library.json")
    return ValidationService(registry).validate(imported_reports, "2024-12")


class TestListedImport:
    def test_four_consolidated_reports_identified(self, imported_reports) -> None:
        assert {report.report_type for report in imported_reports} == {
            ReportType.BALANCE_SHEET,
            ReportType.INCOME_STATEMENT,
            ReportType.CASH_FLOW_STATEMENT,
            ReportType.STATEMENT_OF_CHANGES_IN_EQUITY,
        }

    def test_balance_sheet_left_right_columns(self, imported_reports) -> None:
        bs = next(r for r in imported_reports if r.report_type == ReportType.BALANCE_SHEET)
        amounts = {item.key: item.amount for item in bs.items}
        assert len(bs.items) == 19
        assert amounts["asset_total"] == 9_000_000.0
        assert amounts["liability_total"] == 4_000_000.0
        assert amounts["parent_equity"] == 4_500_000.0
        assert amounts["minority_interest"] == 500_000.0
        assert amounts["equity_total"] == 5_000_000.0
        assert bs.amount_unit == "元"
        assert bs.unit_warning == ""

    def test_income_statement_amounts(self, imported_reports) -> None:
        is_report = next(r for r in imported_reports if r.report_type == ReportType.INCOME_STATEMENT)
        amounts = {item.key: item.amount for item in is_report.items}
        assert amounts["revenue"] == 5_000_000.0
        assert amounts["operating_profit"] == 920_000.0
        assert amounts["net_profit"] == 705_000.0
        assert amounts["total_comprehensive_income"] == 705_000.0

    def test_cash_flow_amounts(self, imported_reports) -> None:
        cf = next(r for r in imported_reports if r.report_type == ReportType.CASH_FLOW_STATEMENT)
        amounts = {item.key: item.amount for item in cf.items}
        assert amounts["operating_net"] == 830_000.0
        assert amounts["investing_net"] == -440_000.0
        assert amounts["financing_net"] == 100_000.0
        assert amounts["ending_cash_equiv"] == 2_000_000.0

    def test_sce_items_extracted(self, imported_reports) -> None:
        sce = next(r for r in imported_reports if r.report_type == ReportType.STATEMENT_OF_CHANGES_IN_EQUITY)
        keys = {item.key for item in sce.items}
        assert "sce_paid_in_capital_ending" in keys
        assert "sce_undistributed_profit_ending" in keys
        assert "sce_minority_interest_ending" in keys
        assert "sce_equity_total_ending" in keys


class TestListedValidation:
    def test_all_applicable_rules_pass(self, validation_summary) -> None:
        assert validation_summary.failed == 0
        assert validation_summary.errored == 0

    def test_consolidated_sce_bal_002_executes_and_passes(self, validation_summary) -> None:
        result = next(r for r in validation_summary.results if r.rule_id == "SCE-BAL-002")
        assert result.skipped is False
        assert result.passed is True
        assert result.diff == pytest.approx(0.0)

    @pytest.mark.parametrize("rule_id", [f"SCE-BS-00{i}" for i in range(1, 6)])
    def test_sce_bs_rules_pass(self, validation_summary, rule_id) -> None:
        result = next(r for r in validation_summary.results if r.rule_id == rule_id)
        assert result.passed is True
        assert result.errored is False

    @pytest.mark.parametrize(
        "rule_id",
        ["BS-BAL-001", "BS-BAL-002", "BS-BAL-003", "BS-BAL-004"],
    )
    def test_bs_balance_rules_pass(self, validation_summary, rule_id) -> None:
        result = next(r for r in validation_summary.results if r.rule_id == rule_id)
        assert result.passed is True
