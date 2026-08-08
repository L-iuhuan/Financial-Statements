"""HistoryRepo 校验历史仓库测试。

覆盖: 保存、读取、删除、计数、明细加载。
"""

from __future__ import annotations

import pytest

from fsa.core.models.report import ReportType
from fsa.core.models.result import ValidationResult, ValidationSummary
from fsa.core.models.rule import Severity
from fsa.storage.history_repo import HistoryRepo

from tests.storage.conftest import make_result, make_summary


class TestHistoryRepoSave:
    """保存校验结果测试。"""

    def test_save_returns_valid_id(
        self, history_repo: HistoryRepo
    ) -> None:
        # Arrange
        summary = make_summary()

        # Act
        history_id = history_repo.save(summary)

        # Assert
        assert history_id > 0

    def test_save_with_zero_results(self, history_repo: HistoryRepo) -> None:
        # Arrange
        summary = ValidationSummary(
            period="2024年12月", total=0, passed=0, failed=0,
            errored=0, skipped=44, results=[], report_types=[],
        )

        # Act
        history_id = history_repo.save(summary)

        # Assert
        assert history_id > 0

    def test_save_with_many_results(
        self, history_repo: HistoryRepo
    ) -> None:
        # Arrange
        results = [
            make_result(rule_id=f"R{i}", passed=(i % 2 == 0))
            for i in range(44)
        ]
        summary = ValidationSummary(
            period="2024年12月", total=44, passed=22, failed=22,
            errored=0, skipped=0, results=results,
            report_types=[ReportType.BALANCE_SHEET],
        )

        # Act
        history_id = history_repo.save(summary)

        # Assert
        assert history_id > 0

    def test_save_persists_report_types(
        self, history_repo: HistoryRepo
    ) -> None:
        # Arrange
        report_types = [
            ReportType.BALANCE_SHEET,
            ReportType.INCOME_STATEMENT,
            ReportType.CASH_FLOW_STATEMENT,
        ]
        summary = make_summary(report_types=report_types)

        # Act
        history_id = history_repo.save(summary)

        # Assert
        recent = history_repo.get_recent()
        assert len(recent) == 1
        assert set(recent[0]["report_types"]) == {
            "资产负债表", "利润表", "现金流量表",
        }


class TestHistoryRepoGetRecent:
    """读取历史列表测试。"""

    def test_get_recent_empty(
        self, history_repo: HistoryRepo
    ) -> None:
        # Act
        result = history_repo.get_recent()

        # Assert
        assert result == []

    def test_get_recent_returns_in_desc_order(
        self, history_repo: HistoryRepo
    ) -> None:
        # Arrange
        for i in range(3):
            summary = make_summary(period=f"2024年{i+1}月")
            history_repo.save(summary)

        # Act
        result = history_repo.get_recent()

        # Assert
        assert len(result) == 3
        # 最新的在前
        assert result[0]["period"] == "2024年3月"
        assert result[2]["period"] == "2024年1月"

    def test_get_recent_respects_limit(
        self, history_repo: HistoryRepo
    ) -> None:
        # Arrange
        for i in range(5):
            summary = make_summary(period=f"2024年{i+1}月")
            history_repo.save(summary)

        # Act
        result = history_repo.get_recent(limit=3)

        # Assert
        assert len(result) == 3

    def test_get_recent_includes_all_fields(
        self, history_repo: HistoryRepo
    ) -> None:
        # Arrange
        summary = make_summary(
            period="2024年12月", total=10, passed=8,
            failed=1, errored=1, skipped=34,
        )

        # Act
        history_repo.save(summary)
        result = history_repo.get_recent()

        # Assert
        record = result[0]
        assert record["id"] > 0
        assert record["created_at"] != ""
        assert record["period"] == "2024年12月"
        assert record["total"] == 10
        assert record["passed"] == 8
        assert record["failed"] == 1
        assert record["errored"] == 1
        assert record["skipped"] == 34
        assert isinstance(record["report_types"], list)


class TestHistoryRepoGetDetail:
    """读取明细测试。"""

    def test_get_detail_returns_all_results(
        self, history_repo: HistoryRepo
    ) -> None:
        # Arrange
        results = [
            make_result(rule_id="R1", passed=True, message="通过"),
            make_result(
                rule_id="R2", passed=False, diff=100.0,
                message="差额超容差",
            ),
            make_result(
                rule_id="R3", passed=False, errored=True,
                message="缺失科目",
            ),
        ]
        summary = make_summary(results=results)

        # Act
        history_id = history_repo.save(summary)
        detail = history_repo.get_detail(history_id)

        # Assert
        assert len(detail) == 3
        assert detail[0].rule_id == "R1"
        assert detail[0].passed is True
        assert detail[1].rule_id == "R2"
        assert detail[1].passed is False
        assert detail[2].rule_id == "R3"
        assert detail[2].errored is True

    def test_get_detail_preserves_severity(
        self, history_repo: HistoryRepo
    ) -> None:
        # Arrange
        results = [
            make_result(rule_id="R1", severity=Severity.ERROR),
            make_result(rule_id="R2", severity=Severity.WARNING),
            make_result(rule_id="R3", severity=Severity.INFO),
        ]
        summary = make_summary(results=results)

        # Act
        history_id = history_repo.save(summary)
        detail = history_repo.get_detail(history_id)

        # Assert
        assert detail[0].severity == Severity.ERROR
        assert detail[1].severity == Severity.WARNING
        assert detail[2].severity == Severity.INFO

    def test_get_detail_preserves_numeric_values(
        self, history_repo: HistoryRepo
    ) -> None:
        # Arrange
        results = [
            make_result(
                rule_id="R1", left_value=1e15, right_value=1e15,
                diff=0.0, tolerance=0.01,
            ),
            make_result(
                rule_id="R2", left_value=100.55, right_value=100.50,
                diff=0.05, tolerance=0.01,
            ),
        ]
        summary = make_summary(results=results)

        # Act
        history_id = history_repo.save(summary)
        detail = history_repo.get_detail(history_id)

        # Assert
        assert detail[0].left_value == 1e15
        assert detail[1].diff == pytest.approx(0.05)

    def test_get_detail_nonexistent_id_returns_empty(
        self, history_repo: HistoryRepo
    ) -> None:
        # Act
        detail = history_repo.get_detail(9999)

        # Assert
        assert detail == []

    def test_get_detail_preserves_formula_and_message(
        self, history_repo: HistoryRepo
    ) -> None:
        # Arrange
        results = [
            make_result(
                rule_id="BS-BAL-001",
                formula="asset_total == liability_total + equity_total",
                message="资产=负债+所有者权益 校验通过",
            ),
        ]
        summary = make_summary(results=results)

        # Act
        history_id = history_repo.save(summary)
        detail = history_repo.get_detail(history_id)

        # Assert
        assert detail[0].formula == (
            "asset_total == liability_total + equity_total"
        )
        assert detail[0].message == (
            "资产=负债+所有者权益 校验通过"
        )


class TestHistoryRepoDelete:
    """删除测试。"""

    def test_delete_removes_history(
        self, history_repo: HistoryRepo
    ) -> None:
        # Arrange
        summary = make_summary()
        history_id = history_repo.save(summary)
        assert history_repo.count() == 1

        # Act
        history_repo.delete(history_id)

        # Assert
        assert history_repo.count() == 0

    def test_delete_cascades_to_results(
        self, history_repo: HistoryRepo
    ) -> None:
        # Arrange
        summary = make_summary()
        history_id = history_repo.save(summary)
        assert len(history_repo.get_detail(history_id)) == 3

        # Act
        history_repo.delete(history_id)

        # Assert
        assert history_repo.get_detail(history_id) == []

    def test_delete_nonexistent_id_is_noop(
        self, history_repo: HistoryRepo
    ) -> None:
        # Arrange
        summary = make_summary()
        history_repo.save(summary)

        # Act
        history_repo.delete(9999)

        # Assert
        assert history_repo.count() == 1


class TestHistoryRepoCount:
    """计数测试。"""

    def test_count_empty(self, history_repo: HistoryRepo) -> None:
        assert history_repo.count() == 0

    def test_count_after_saves(
        self, history_repo: HistoryRepo
    ) -> None:
        # Arrange
        for _ in range(5):
            history_repo.save(make_summary())

        # Act + Assert
        assert history_repo.count() == 5
