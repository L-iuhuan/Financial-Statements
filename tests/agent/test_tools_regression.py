"""9 个 Agent 本地工具逐一回归: 空状态/有数据/参数错误路径。"""

from __future__ import annotations

from fsa.agent.tools import TOOL_SCHEMAS, execute_tool
from fsa.core.engine.registry import RuleRegistry
from fsa.core.models.report import Report, ReportItem, ReportType
from fsa.core.models.result import (
    TraceItem,
    ValidationResult,
    ValidationSummary,
)
from fsa.core.models.rule import Severity


def _make_state(app_state):
    report = Report(
        report_type=ReportType.BALANCE_SHEET,
        period="2024-12",
        source_file="D:\\财务\\资产负债表.xlsx",
        items=[
            ReportItem(
                key="asset_total",
                name="资产总计",
                amount=1_000_000.0,
                row=35,
                column="期末余额",
            ),
            ReportItem(
                key="monetary_funds",
                name="货币资金",
                amount=200_000.0,
                row=2,
                column="期末余额",
            ),
            ReportItem(
                key="asset_impairment",
                name="资产减值损失",
                amount=-5_000.0,
                row=12,
                column="期末余额",
            ),
        ],
        unmapped_names=["其中：受限货币资金"],
    )
    app_state.set_reports([report])
    app_state._registry = RuleRegistry.from_json("cas_gouji_rule_library.json")
    failed = ValidationResult(
        rule_id="BS-BAL-001",
        rule_name="资产=负债+所有者权益",
        passed=False,
        severity=Severity.ERROR,
        left_value=1_000_000.0,
        right_value=990_000.0,
        diff=10_000.0,
        tolerance=0.01,
        formula="asset_total == liability_total + equity_total",
        message="差额超出容差",
        trace=[
            TraceItem(
                key="asset_total",
                name="资产总计",
                amount=1_000_000.0,
                row=35,
                column="期末余额",
                side="left",
            ),
            TraceItem(
                key="liability_total",
                name="负债合计",
                amount=600_000.0,
                row=20,
                column="期末余额",
                side="right",
            ),
        ],
    )
    skipped = ValidationResult(
        rule_id="SCE-BAL-001",
        rule_name="权益各组成期初±变动=期末",
        passed=True,
        severity=Severity.ERROR,
        left_value=0.0,
        right_value=0.0,
        diff=0.0,
        tolerance=0.01,
        formula="ending == beginning + total_changes",
        message="权益各组成期初±变动=期末: 跳过 - 缺少数据",
        skipped=True,
    )
    summary = ValidationSummary(
        period="2024-12",
        total=2,
        passed=1,
        failed=1,
        errored=0,
        skipped=1,
        results=[failed, skipped],
        report_types=[ReportType.BALANCE_SHEET],
        amount_unit_notes=["资产负债表: 金额单位 元，已统一换算为元"],
    )
    app_state.set_results(summary, persist=False)
    return app_state


class TestToolSchemaContract:
    def test_exactly_nine_tools_registered(self) -> None:
        names = {schema["function"]["name"] for schema in TOOL_SCHEMAS}
        assert names == {
            "get_validation_results",
            "get_rule_trace",
            "get_rule_definition",
            "get_report_item",
            "search_knowledge",
            "compare_with_history",
            "get_imported_reports",
            "get_unmapped_items",
            "get_skipped_rules",
        }

    def test_unknown_tool_returns_chinese(self, app_state) -> None:
        result = execute_tool("not_a_tool", {}, app_state)
        assert "未知工具" in result


class TestToolExecutions:
    def test_get_validation_results(self, app_state) -> None:
        _make_state(app_state)
        result = execute_tool("get_validation_results", {}, app_state)
        assert "BS-BAL-001" in result
        assert "通过 1 / 不通过 1" in result

    def test_get_validation_results_empty(self, app_state) -> None:
        result = execute_tool("get_validation_results", {}, app_state)
        assert "当前没有校验结果" in result

    def test_get_rule_trace(self, app_state) -> None:
        _make_state(app_state)
        result = execute_tool("get_rule_trace", {"rule_id": "BS-BAL-001"}, app_state)
        assert "资产总计" in result
        assert "第35行 期末余额列" in result
        assert "10,000.00" in result

    def test_get_rule_definition(self, app_state) -> None:
        _make_state(app_state)
        result = execute_tool("get_rule_definition", {"rule_id": "BS-BAL-001"}, app_state)
        assert "会计恒等式" in result or "CAS" in result
        assert "asset_total == liability_total + equity_total" in result

    def test_get_report_item_exact_then_similar(self, app_state) -> None:
        _make_state(app_state)
        exact = execute_tool("get_report_item", {"name": "资产总计"}, app_state)
        assert "1,000,000.00" in exact
        assert "资产负债表" in exact
        similar = execute_tool("get_report_item", {"name": "资产"}, app_state)
        assert "另匹配到" in similar

    def test_search_knowledge(self, app_state) -> None:
        result = execute_tool("search_knowledge", {"query": "勾稽关系"}, app_state)
        assert "资产 = 负债" in result or "资产=负债" in result

    def test_compare_with_history(self, app_state, monkeypatch) -> None:
        _make_state(app_state)

        class FakeRepo:
            def get_recent(self, limit: int = 20):
                return [
                    {"created_at": "2026-08-16 10:00:00", "passed": 20, "failed": 1, "errored": 0},
                    {"created_at": "2026-08-15 10:00:00", "passed": 18, "failed": 3, "errored": 0},
                ]

        monkeypatch.setattr(app_state, "_history_repo", FakeRepo())
        result = execute_tool("compare_with_history", {}, app_state)
        assert "与上次校验" in result
        assert "18 / 不通过 3" in result

    def test_compare_with_history_no_current(self, app_state) -> None:
        result = execute_tool("compare_with_history", {}, app_state)
        assert "当前没有校验结果" in result

    def test_get_imported_reports_hides_full_path(self, app_state) -> None:
        _make_state(app_state)
        result = execute_tool("get_imported_reports", {}, app_state)
        assert "资产负债表" in result
        assert "资产负债表.xlsx" in result
        assert "财务" not in result

    def test_get_unmapped_items(self, app_state) -> None:
        _make_state(app_state)
        result = execute_tool("get_unmapped_items", {}, app_state)
        assert "其中：受限货币资金" in result
        assert "不参与校验" in result

    def test_get_skipped_rules(self, app_state) -> None:
        _make_state(app_state)
        result = execute_tool("get_skipped_rules", {}, app_state)
        assert "SCE-BAL-001" in result
        assert "缺少数据" in result
