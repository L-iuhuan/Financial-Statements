"""校验历史仓库: ValidationSummary <-> SQLite 持久化。

遵循 AGENTS.md: 持久化层独立, 不依赖 GUI 或业务逻辑。
仅依赖数据模型 (ValidationSummary / ValidationResult)。
"""

from __future__ import annotations

import json
import sqlite3
from typing import TypedDict

from loguru import logger

from fsa.core.models.result import TraceItem, ValidationResult, ValidationSummary
from fsa.core.models.rule import Severity
from fsa.storage.database import Database


class HistoryRecord(TypedDict):
    """单条校验历史记录（不含明细）。

    Attributes:
        id: 历史记录 ID
        created_at: 创建时间
        period: 会计期间
        total: 规则总数
        passed: 通过数
        failed: 不通过数
        errored: 异常数
        skipped: 跳过数
        report_types: 涉及的报表类型
        source_files: 源文件路径列表 (审计证据链)
        source_hashes: 源文件 SHA256 列表
        rule_version: 内置规则库版本
    """

    id: int
    created_at: str
    period: str
    total: int
    passed: int
    failed: int
    errored: int
    skipped: int
    report_types: list[str]
    source_files: list[str]
    source_hashes: list[str]
    rule_version: str


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

        使用显式事务 (BEGIN/COMMIT/ROLLBACK) 确保汇总记录与明细记录
        的原子性: 明细插入中途失败时整个事务回滚，不留半截历史。

        Args:
            summary: 校验汇总结果

        Returns:
            新创建的历史记录 ID

        Raises:
            RuntimeError: 数据库未连接或事务失败
        """
        conn = self._db.connection
        report_types_json = json.dumps(
            [rt.value for rt in summary.report_types], ensure_ascii=False
        )
        source_files_json = json.dumps(summary.source_files, ensure_ascii=False)
        source_hashes_json = json.dumps(summary.source_hashes, ensure_ascii=False)

        conn.execute("BEGIN")
        try:
            cursor = conn.execute(
                """INSERT INTO validation_history
                   (period, total, passed, failed, errored, skipped,
                    report_types, source_files, source_hashes, rule_version)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (summary.period, summary.total, summary.passed,
                 summary.failed, summary.errored, summary.skipped,
                 report_types_json, source_files_json, source_hashes_json,
                 summary.rule_version),
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
        except Exception:
            conn.rollback()
            logger.exception("保存校验历史失败, 事务已回滚")
            raise

    def _insert_result(
        self, conn: sqlite3.Connection, history_id: int, result: ValidationResult
    ) -> None:
        """插入单条校验结果明细。"""
        trace_json = json.dumps(
            [
                {
                    "key": ti.key,
                    "name": ti.name,
                    "amount": ti.amount,
                    "row": ti.row,
                    "column": ti.column,
                    "side": ti.side,
                }
                for ti in result.trace
            ],
            ensure_ascii=False,
        )
        conn.execute(
            """INSERT INTO validation_results
               (history_id, rule_id, rule_name, passed, severity,
                left_value, right_value, diff, tolerance, formula,
                message, errored, skipped, category, trace)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (history_id, result.rule_id, result.rule_name,
             int(result.passed), result.severity.value,
             result.left_value, result.right_value, result.diff,
             result.tolerance, result.formula, result.message,
             int(result.errored), int(result.skipped),
             result.category, trace_json),
        )

    def get_recent(self, limit: int = 20) -> list[HistoryRecord]:
        """获取最近的校验历史记录 (不含明细)。

        Args:
            limit: 最多返回的记录数

        Returns:
            历史记录列表，每条为 HistoryRecord 字典
        """
        conn = self._db.connection
        rows = conn.execute(
            """SELECT id, created_at, period, total, passed,
                      failed, errored, skipped, report_types,
                      source_files, source_hashes, rule_version
               FROM validation_history
               ORDER BY id DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()

        result: list[HistoryRecord] = []
        for row in rows:
            result.append(self._row_to_record(row))
        return result

    def get_by_id(self, history_id: int) -> HistoryRecord | None:
        """按 ID 获取单条历史记录（不含明细）。

        Args:
            history_id: 历史记录 ID

        Returns:
            HistoryRecord 字典；记录不存在时返回 None
        """
        conn = self._db.connection
        row = conn.execute(
            """SELECT id, created_at, period, total, passed,
                      failed, errored, skipped, report_types,
                      source_files, source_hashes, rule_version
               FROM validation_history
               WHERE id = ?""",
            (history_id,),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_record(row)

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> HistoryRecord:
        """将 validation_history 行转换为 HistoryRecord (兼容旧库缺失列)。"""
        keys = row.keys()
        return {
            "id": row["id"],
            "created_at": row["created_at"],
            "period": row["period"],
            "total": row["total"],
            "passed": row["passed"],
            "failed": row["failed"],
            "errored": row["errored"],
            "skipped": row["skipped"],
            "report_types": HistoryRepo._parse_json_list(row["report_types"]),
            "source_files": HistoryRepo._parse_json_list(
                row["source_files"] if "source_files" in keys else "[]"
            ),
            "source_hashes": HistoryRepo._parse_json_list(
                row["source_hashes"] if "source_hashes" in keys else "[]"
            ),
            "rule_version": row["rule_version"] if "rule_version" in keys else "",
        }

    @staticmethod
    def _parse_json_list(raw: object) -> list[str]:
        """安全解析 JSON 字符串列表, 损坏时返回空列表。"""
        if raw is None:
            return []
        try:
            parsed = json.loads(str(raw))
        except (json.JSONDecodeError, TypeError):
            return []
        return [str(item) for item in parsed] if isinstance(parsed, list) else []

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
                      formula, message, errored, skipped, category, trace
               FROM validation_results
               WHERE history_id = ?
               ORDER BY id""",
            (history_id,),
        ).fetchall()

        results: list[ValidationResult] = []
        for row in rows:
            # 兼容旧数据库: skipped/category/trace 可能为 None
            skipped = bool(row["skipped"]) if row["skipped"] is not None else False
            category = row["category"] if row["category"] is not None else ""
            trace_raw = row["trace"] if row["trace"] is not None else "[]"
            trace_items = self._parse_trace_json(trace_raw)

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
                skipped=skipped,
                category=category,
                trace=trace_items,
            ))
        return results

    @staticmethod
    def _parse_trace_json(trace_raw: str) -> list[TraceItem]:
        """将 trace JSON 字符串解析为 TraceItem 列表。

        解析失败时返回空列表 (兼容旧数据或损坏的 JSON)。
        """
        try:
            raw_list = json.loads(trace_raw)
        except (json.JSONDecodeError, TypeError):
            return []
        items: list[TraceItem] = []
        for item in raw_list:
            try:
                items.append(TraceItem(
                    key=item.get("key", ""),
                    name=item.get("name", ""),
                    amount=float(item.get("amount", 0)),
                    row=int(item.get("row", 0)),
                    column=str(item.get("column", "")),
                    side=str(item.get("side", "")),
                ))
            except (ValueError, TypeError):
                continue
        return items

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
