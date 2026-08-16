"""规则容差/启停覆写仓库: 持久化用户自定义的规则容差与启用状态。

遵循 AGENTS.md: 持久化层独立, 不依赖 GUI 或业务逻辑。
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from loguru import logger

from fsa.core.exceptions import InvalidToleranceError
from fsa.storage.database import Database


@dataclass(frozen=True)
class RuleOverride:
    """单条规则的覆写记录: 容差 + 启停。"""

    tolerance: float
    enabled: bool


class RuleOverrideRepo:
    """规则容差/启停覆写仓库: 保存和读取用户自定义的规则容差与启停状态。

    覆写值存储在 rule_overrides 表中，以 rule_id 为主键。
    应用启动时加载并应用到 RuleRegistry。
    """

    def __init__(self, db: Database) -> None:
        self._db = db

    def set(self, rule_id: str, tolerance: float) -> None:
        """设置或更新某条规则的容差覆写 (已有记录的启停状态保持不变)。

        Args:
            rule_id: 规则编号
            tolerance: 新的容差值

        Raises:
            InvalidToleranceError: 容差不是有限非负数 (NaN/Inf/负数)
        """
        if not math.isfinite(tolerance) or tolerance < 0:
            raise InvalidToleranceError(tolerance)

        conn = self._db.connection
        conn.execute(
            """INSERT INTO rule_overrides (rule_id, tolerance)
               VALUES (?, ?)
               ON CONFLICT(rule_id) DO UPDATE SET tolerance = excluded.tolerance""",
            (rule_id, tolerance),
        )
        conn.commit()
        logger.debug(f"容差覆写已保存: {rule_id} → {tolerance}")

    def set_enabled(self, rule_id: str, enabled: bool, current_tolerance: float) -> None:
        """设置或更新某条规则的启停覆写 (已有记录的容差覆写保持不变)。

        Args:
            rule_id: 规则编号
            enabled: 启用/禁用
            current_tolerance: 该规则当前生效容差。仅在该规则尚无覆写记录时
                随插入写入 (tolerance 列 NOT NULL); 已有记录时不会被使用,
                既有容差覆写保持不变
        """
        conn = self._db.connection
        conn.execute(
            """INSERT INTO rule_overrides (rule_id, tolerance, enabled)
               VALUES (?, ?, ?)
               ON CONFLICT(rule_id) DO UPDATE SET enabled = excluded.enabled""",
            (rule_id, current_tolerance, 1 if enabled else 0),
        )
        conn.commit()
        logger.debug(f"启停覆写已保存: {rule_id} → {'启用' if enabled else '禁用'}")

    def get_all(self) -> dict[str, RuleOverride]:
        """获取所有规则覆写 (容差 + 启停)。

        Returns:
            {rule_id: RuleOverride} 字典
        """
        conn = self._db.connection
        rows = conn.execute(
            "SELECT rule_id, tolerance, enabled FROM rule_overrides"
        ).fetchall()
        return {
            row["rule_id"]: RuleOverride(
                tolerance=row["tolerance"], enabled=bool(row["enabled"])
            )
            for row in rows
        }

    def delete(self, rule_id: str) -> None:
        """删除某条规则的覆写。

        Args:
            rule_id: 规则编号
        """
        conn = self._db.connection
        conn.execute(
            "DELETE FROM rule_overrides WHERE rule_id = ?", (rule_id,)
        )
        conn.commit()
        logger.debug(f"规则覆写已删除: {rule_id}")

    def clear(self) -> None:
        """清空所有规则覆写。"""
        conn = self._db.connection
        conn.execute("DELETE FROM rule_overrides")
        conn.commit()
        logger.info("所有规则覆写已清空")
