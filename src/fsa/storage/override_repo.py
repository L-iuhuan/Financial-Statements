"""规则容差覆写仓库: 持久化用户自定义的规则容差。

遵循 AGENTS.md: 持久化层独立, 不依赖 GUI 或业务逻辑。
"""

from __future__ import annotations

import math

from loguru import logger

from fsa.core.exceptions import InvalidToleranceError
from fsa.storage.database import Database


class RuleOverrideRepo:
    """规则容差覆写仓库: 保存和读取用户自定义的规则容差。

    覆写值存储在 rule_overrides 表中，以 rule_id 为主键。
    应用启动时加载并应用到 RuleRegistry。
    """

    def __init__(self, db: Database) -> None:
        self._db = db

    def set(self, rule_id: str, tolerance: float) -> None:
        """设置或更新某条规则的容差覆写。

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

    def get_all(self) -> dict[str, float]:
        """获取所有规则容差覆写。

        Returns:
            {rule_id: tolerance} 字典
        """
        conn = self._db.connection
        rows = conn.execute(
            "SELECT rule_id, tolerance FROM rule_overrides"
        ).fetchall()
        return {row["rule_id"]: row["tolerance"] for row in rows}

    def delete(self, rule_id: str) -> None:
        """删除某条规则的容差覆写。

        Args:
            rule_id: 规则编号
        """
        conn = self._db.connection
        conn.execute(
            "DELETE FROM rule_overrides WHERE rule_id = ?", (rule_id,)
        )
        conn.commit()
        logger.debug(f"容差覆写已删除: {rule_id}")

    def clear(self) -> None:
        """清空所有容差覆写。"""
        conn = self._db.connection
        conn.execute("DELETE FROM rule_overrides")
        conn.commit()
        logger.info("所有容差覆写已清空")
