"""存储层测试共享 fixtures。

使用临时文件数据库, 测试后自动清理。
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from fsa.core.models.report import ReportType
from fsa.core.models.result import ValidationResult, ValidationSummary
from fsa.core.models.rule import Severity
from fsa.storage.chat_repo import ChatRepo
from fsa.storage.database import Database
from fsa.storage.history_repo import HistoryRepo


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """临时数据库文件路径。"""
    return tmp_path / "test_data.db"


@pytest.fixture
def db(db_path: Path) -> Iterator[Database]:
    """已连接并初始化的数据库 (自动关闭)。"""
    database = Database(db_path)
    database.connect()
    database.init_schema()
    yield database
    database.close()


@pytest.fixture
def history_repo(db: Database) -> HistoryRepo:
    """校验历史仓库。"""
    return HistoryRepo(db)


@pytest.fixture
def chat_repo(db: Database) -> ChatRepo:
    """AI 对话仓库。"""
    return ChatRepo(db)


def make_result(
    rule_id: str = "BS-BAL-001",
    rule_name: str = "资产=负债+所有者权益",
    passed: bool = True,
    severity: Severity = Severity.ERROR,
    left_value: float = 100.0,
    right_value: float = 100.0,
    diff: float = 0.0,
    tolerance: float = 0.01,
    formula: str = "asset_total == liability_total + equity_total",
    message: str = "校验通过",
    errored: bool = False,
) -> ValidationResult:
    """构造 ValidationResult 辅助函数。"""
    return ValidationResult(
        rule_id=rule_id,
        rule_name=rule_name,
        passed=passed,
        severity=severity,
        left_value=left_value,
        right_value=right_value,
        diff=diff,
        tolerance=tolerance,
        formula=formula,
        message=message,
        errored=errored,
    )


def make_summary(
    period: str = "2024年12月",
    total: int = 3,
    passed: int = 2,
    failed: int = 1,
    errored: int = 0,
    skipped: int = 0,
    results: list[ValidationResult] | None = None,
    report_types: list[ReportType] | None = None,
) -> ValidationSummary:
    """构造 ValidationSummary 辅助函数。"""
    if results is None:
        results = [
            make_result(rule_id="R1", passed=True),
            make_result(rule_id="R2", passed=True),
            make_result(
                rule_id="R3", passed=False,
                diff=0.5, message="差额超容差",
            ),
        ]
    if report_types is None:
        report_types = [
            ReportType.BALANCE_SHEET,
            ReportType.INCOME_STATEMENT,
        ]
    return ValidationSummary(
        period=period,
        total=total,
        passed=passed,
        failed=failed,
        errored=errored,
        skipped=skipped,
        results=results,
        report_types=report_types,
    )
