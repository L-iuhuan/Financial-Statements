"""AI 对话仓库: 会话和消息的 SQLite 持久化。

遵循 AGENTS.md: 持久化层独立, 不依赖 GUI。
支持会话列表、消息加载、按会话追加消息。
"""

from __future__ import annotations

from loguru import logger

from fsa.storage.database import Database


class ChatRepo:
    """AI 对话仓库: 管理会话和消息的增删查。"""

    def __init__(self, db: Database) -> None:
        self._db = db

    def create_session(
        self, title: str = "新对话", context_rule_id: str = ""
    ) -> int:
        """创建新的对话会话, 返回会话 ID。

        Args:
            title: 会话标题
            context_rule_id: 关联的规则 ID (点击"AI 诊断"时传入)

        Returns:
            新会话 ID
        """
        conn = self._db.connection
        cursor = conn.execute(
            """INSERT INTO chat_sessions (title, context_rule_id)
               VALUES (?, ?)""",
            (title, context_rule_id),
        )
        session_id = cursor.lastrowid
        if session_id is None:
            raise RuntimeError("创建对话会话失败, 未获取到 ID")
        conn.commit()
        logger.info(f"创建对话会话 #{session_id}: {title}")
        return session_id

    def get_sessions(self, limit: int = 50) -> list[dict]:
        """获取最近的对话会话列表。

        Args:
            limit: 最多返回的会话数

        Returns:
            会话列表, 每条为字典:
            {id, created_at, updated_at, title, context_rule_id}
        """
        conn = self._db.connection
        rows = conn.execute(
            """SELECT id, created_at, updated_at, title, context_rule_id
               FROM chat_sessions
               ORDER BY id DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()

        result: list[dict] = []
        for row in rows:
            result.append({
                "id": row["id"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "title": row["title"],
                "context_rule_id": row["context_rule_id"],
            })
        return result

    def get_messages(self, session_id: int) -> list[dict]:
        """获取指定会话的全部消息。

        Args:
            session_id: 会话 ID

        Returns:
            消息列表, 每条为字典:
            {id, role, content, created_at}
        """
        conn = self._db.connection
        rows = conn.execute(
            """SELECT id, role, content, created_at
               FROM chat_messages
               WHERE session_id = ?
               ORDER BY id""",
            (session_id,),
        ).fetchall()

        result: list[dict] = []
        for row in rows:
            result.append({
                "id": row["id"],
                "role": row["role"],
                "content": row["content"],
                "created_at": row["created_at"],
            })
        return result

    def add_message(
        self, session_id: int, role: str, content: str
    ) -> int:
        """向指定会话追加一条消息, 返回消息 ID。

        Args:
            session_id: 会话 ID
            role: 消息角色 ("user" 或 "assistant")
            content: 消息内容

        Returns:
            新消息 ID

        Raises:
            ValueError: role 不合法
        """
        if role not in ("user", "assistant"):
            raise ValueError(
                f"消息角色必须是 'user' 或 'assistant', 收到 '{role}'"
            )

        conn = self._db.connection
        cursor = conn.execute(
            """INSERT INTO chat_messages (session_id, role, content)
               VALUES (?, ?, ?)""",
            (session_id, role, content),
        )
        message_id = cursor.lastrowid
        if message_id is None:
            raise RuntimeError("追加消息失败, 未获取到 ID")

        conn.execute(
            """UPDATE chat_sessions
               SET updated_at = datetime('now','localtime')
               WHERE id = ?""",
            (session_id,),
        )
        conn.commit()
        return message_id

    def delete_session(self, session_id: int) -> None:
        """删除整个会话及其全部消息 (CASCADE)。

        Args:
            session_id: 会话 ID
        """
        conn = self._db.connection
        conn.execute(
            "DELETE FROM chat_sessions WHERE id = ?", (session_id,)
        )
        conn.commit()
        logger.info(f"删除对话会话 #{session_id}")

    def clear_messages(self, session_id: int) -> None:
        """清空指定会话的全部消息 (保留会话本身)。

        Args:
            session_id: 会话 ID
        """
        conn = self._db.connection
        conn.execute(
            "DELETE FROM chat_messages WHERE session_id = ?", (session_id,)
        )
        conn.commit()
        logger.info(f"清空会话 #{session_id} 的全部消息")

    def update_title(self, session_id: int, title: str) -> None:
        """更新会话标题。

        Args:
            session_id: 会话 ID
            title: 新标题
        """
        conn = self._db.connection
        conn.execute(
            "UPDATE chat_sessions SET title = ? WHERE id = ?",
            (title, session_id),
        )
        conn.commit()

    def count_sessions(self) -> int:
        """返回会话总数。"""
        conn = self._db.connection
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM chat_sessions"
        ).fetchone()
        return row["cnt"] if row else 0
