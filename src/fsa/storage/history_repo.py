"""校验历史仓库: ValidationSummary <-> SQLite 持久化。

遵循 AGENTS.md: 持久化层独立, 不依赖 GUI 或业务逻辑。
仅依赖数据模型 (ValidationSummary / ValidationResult)。
"""

from __future__ import annotations

import json

from loguru import logger

from fsa.core.models.result import ValidationResult, ValidationSummary
from fsa.core.models.rule import Severity
from fsa.storage.database import Database


class HistoryRepo:
    """校验历史仓库: 保存和读取校验记录。

    一次校验的 ValidationSummary 保存为:
    - 1 条 validation_history 记录 (汇总)
    - N 条 validation_results 记录 (明细)
    """

    def __init__(self, db: Database) -> None:
        self._db = db

    def save(self, summary: ValidationSummary) -> int:
        """保存一次校验结果, 返回历史记录 ID。

        Args:
            summary: 校验汇总结果

        Returns:
            新创建的历史记录 ID

        Raises:
            RuntimeError: 数据库未连接
        """
        conn = self._db.connection
        report_types_json = json.dumps(
            [rt.value for rt in summary.report_types], ensure_ascii=False
        )

        cursor = conn.execute(
            """INSERT INTO validation_history
               (period, total, passed, failed, errored, skipped, report_types)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (summary.period, summary.total, summary.passed,
             summary.failed, summary.errored, summary.skipped,
             report_types_json),
        )
        history_id = cursor.lastrowid
        if history_id is None:
            raise RuntimeError("插入历史记录失败, 未获取到 ID")

        for result in summary.results:
            self._insert_result(conn, history_id, result)

        conn.commit()
        logger.info(
            f"保存校验历史 #{history_id}: "
            f"通过 {summary.passed}, 不通过 {summary.failed}, 异常 {summary.errored}"
        )
        return history_id

    def _insert_result(
        self, conn, history_id: int, result: ValidationResult
    ) -> None:
        """插入单条校验结果明细。"""
        conn.execute(
            """INSERT INTO validation_results
               (history_id, rule_id, rule_name, passed, severity,
                left_value, right_value, diff, tolerance, formula,
                message, errored)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (history_id, result.rule_id, result.rule_name,
             int(result.passed), result.severity.value,
             result.left_value, result.right_value, result.diff,
             result.tolerance, result.formula, result.message,
             int(result.errored)),
        )

    def get_recent(self, limit: int = 20) -> list[dict]:
        """获取最近的校验历史记录 (不含明细)。

        Args:
            limit: 最多返回的记录数

        Returns:
            历史记录列表, 每条为字典:
            {id, created_at, period, total, passed, failed, errored, skipped, report_types}
        """
        conn = self._db.connection
        rows = conn.execute(
            """SELECT id, created_at, period, total, passed,
                      failed, errored, skipped, report_types
               FROM validation_history
               ORDER BY id DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()

        result: list[dict] = []
        for row in rows:
            result.append({
                "id": row["id"],
                "created_at": row["created_at"],
                "period": row["period"],
                "total": row["total"],
                "passed": row["passed"],
                "failed": row["failed"],
                "errored": row["errored"],
                "skipped": row["skipped"],
                "report_types": json.loads(row["report_types"]),
            })
        return result

    def get_detail(self, history_id: int) -> list[ValidationResult]:
        """获取指定历史记录的校验结果明细。

        Args:
            history_id: 历史记录 ID

        Returns:
            ValidationResult 列表
        """
        conn = self._db.connection
        rows = conn.execute(
            """SELECT rule_id, rule_name, passed, severity,
                      left_value, right_value, diff, tolerance,
                      formula, message, errored
               FROM validation_results
               WHERE history_id = ?
               ORDER BY id""",
            (history_id,),
        ).fetchall()

        results: list[ValidationResult] = []
        for row in rows:
            results.append(ValidationResult(
                rule_id=row["rule_id"],
                rule_name=row["rule_name"],
                passed=bool(row["passed"]),
                severity=Severity(row["severity"]),
                left_value=row["left_value"],
                right_value=row["right_value"],
                diff=row["diff"],
                tolerance=row["tolerance"],
                formula=row["formula"],
                message=row["message"],
                errored=bool(row["errored"]),
            ))
        return results

    def delete(self, history_id: int) -> None:
        """删除指定历史记录 (含明细, CASCADE)。

        Args:
            history_id: 历史记录 ID
        """
        conn = self._db.connection
        conn.execute(
            "DELETE FROM validation_history WHERE id = ?", (history_id,)
        )
        conn.commit()
        logger.info(f"删除校验历史 #{history_id}")

    def delete_older_than(self, days: int) -> int:
        """删除超过指定天数的历史记录（含明细，CASCADE）。

        Args:
            days: 保留天数，删除 created_at 早于此天数的记录

        Returns:
            被删除的历史记录条数
        """
        conn = self._db.connection
        cursor = conn.execute(
            """DELETE FROM validation_history
               WHERE created_at < datetime('now', 'localtime', ?)""",
            (f"-{days} days",),
        )
        conn.commit()
        deleted = cursor.rowcount
        if deleted > 0:
            logger.info(f"清理过期校验历史: {deleted} 条 (保留 {days} 天)")
        return deleted

    def count(self) -> int:
        """返回历史记录总数。"""
        conn = self._db.connection
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM validation_history"
        ).fetchone()
        return row["cnt"] if row else 0
