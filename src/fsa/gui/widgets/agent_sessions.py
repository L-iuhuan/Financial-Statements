"""AI 抽屉会话管理与消息持久化 (mixin)。

从 agent_drawer 拆分的会话列表/切换/新建/清空与消息持久化逻辑 (纯移动, 不改行为)。
由 AgentDrawer 继承, 与 AgentMessageMixin 共同组成完整抽屉。

依赖宿主 AgentDrawer 提供的属性 (均在 __init__ 中初始化):
_chat_repo / _session_btn / _session_id。
"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from loguru import logger
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QFrame, QMenu, QPushButton

from fsa.gui.widgets.agent_messages import _AgentDrawerContracts
from fsa.storage.chat_repo import ChatRepo

if TYPE_CHECKING:
    from fsa.agent.llm_client import ChatMessage


class AgentSessionMixin(QFrame, _AgentDrawerContracts):
    """会话管理与消息持久化逻辑 (继承 QFrame 以便访问 QWidget 方法)。"""

    _chat_repo: ChatRepo | None
    _session_btn: QPushButton
    _session_id: int | None

    def _load_sessions_if_available(self) -> None:
        """初始化时加载最近会话。"""
        if self._chat_repo is None:
            self._session_btn.setVisible(False)
            return
        try:
            sessions = self._chat_repo.get_sessions(limit=1)
        except (sqlite3.DatabaseError, RuntimeError):
            logger.exception("加载会话列表失败")
            return
        if sessions:
            sid = sessions[0]["id"]
            self._session_id = sid
            self._update_session_btn(sessions[0]["title"])
            self._load_session_messages(sid)

    def _show_session_menu(self) -> None:
        """弹出会话选择菜单。"""
        if self._chat_repo is None:
            return
        try:
            sessions = self._chat_repo.get_sessions()
        except (sqlite3.DatabaseError, RuntimeError):
            logger.exception("加载会话列表失败")
            return

        menu = QMenu(self._session_btn)
        # 使用全局 QSS, 不设置 inline stylesheet

        for s in sessions:
            label = s.get("title") or f"会话 #{s['id']}"
            action = QAction(label, menu)
            action.setCheckable(True)
            action.setChecked(s["id"] == self._session_id)
            action.triggered.connect(
                lambda checked=False, sid=s["id"]: self._switch_session(sid)
            )
            menu.addAction(action)

        menu.addSeparator()
        new_action = QAction("+ 新建会话", menu)
        new_action.triggered.connect(self._new_session)
        menu.addAction(new_action)

        pos = self._session_btn.mapToGlobal(
            QPoint(0, self._session_btn.height())
        )
        menu.exec(pos)

    def _switch_session(self, session_id: int) -> None:
        """切换到指定会话。"""
        if session_id == self._session_id:
            return
        self._session_id = session_id
        try:
            sessions = self._chat_repo.get_sessions()  # type: ignore[union-attr]
            for s in sessions:
                if s["id"] == session_id:
                    self._update_session_btn(
                        s.get("title") or f"会话 #{session_id}"
                    )
                    break
        except (sqlite3.DatabaseError, RuntimeError):
            logger.exception("查找会话信息失败")
        self._load_session_messages(session_id)

    def _new_session(self) -> None:
        """创建新会话。"""
        if self._chat_repo is None:
            return
        try:
            self._session_id = self._chat_repo.create_session()
        except (sqlite3.DatabaseError, RuntimeError):
            logger.exception("创建对话会话失败")
            return
        self._update_session_btn("新对话")
        self._rebuild_messages([])

    def _clear_current_session(self) -> None:
        """清空当前会话的全部消息 (保留会话本身)。"""
        if self._chat_repo is None or self._session_id is None:
            return
        from PySide6.QtWidgets import QMessageBox

        reply = QMessageBox.question(
            self, "确认清空",
            "确定要清空当前会话的全部对话吗？此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self._chat_repo.clear_messages(self._session_id)
        except (sqlite3.DatabaseError, RuntimeError):
            logger.exception("清空会话消息失败")
            return
        self._rebuild_messages([])

    def _load_session_messages(self, session_id: int) -> None:
        """从数据库加载指定会话的消息。"""
        if self._chat_repo is None:
            return
        try:
            messages = self._chat_repo.get_messages(session_id)
        except (sqlite3.DatabaseError, RuntimeError):
            logger.exception("加载会话消息失败")
            return
        self._rebuild_messages(messages)

    def _update_session_btn(self, title: str) -> None:
        """更新会话按钮显示文本 (窄窗 elide, 防止长标题撑破布局)。"""
        btn = self._session_btn
        btn.setMaximumWidth(140)
        display = btn.fontMetrics().elidedText(
            title or "会话", Qt.TextElideMode.ElideRight, 120
        )
        btn.setText(f"{display} ▾")

    def _ensure_session(self) -> None:
        if self._session_id is not None:
            return
        if self._chat_repo is None:
            return
        try:
            self._session_id = self._chat_repo.create_session()
            self._update_session_btn("新对话")
        except (sqlite3.DatabaseError, RuntimeError):
            logger.exception("创建对话会话失败")

    def _persist_message(self, role: str, content: str) -> None:
        self._ensure_session()
        if self._session_id is None or self._chat_repo is None:
            return
        try:
            self._chat_repo.add_message(
                self._session_id, role, content
            )
            # 首条用户消息 -> 自动重命名会话
            if role == "user":
                self._auto_rename_session(content)
        except (sqlite3.DatabaseError, RuntimeError):
            logger.exception("保存对话消息失败")
        except ValueError as e:
            logger.error(f"保存对话消息失败: {e}")

    def _auto_rename_session(self, first_message: str) -> None:
        """根据首条用户消息自动重命名会话。

        仅在会话仍是默认标题时生效, 取首条消息前 12 字作为标题。
        """
        if self._chat_repo is None or self._session_id is None:
            return
        try:
            sessions = self._chat_repo.get_sessions()
            current = next(
                (s for s in sessions if s["id"] == self._session_id), None
            )
            if current is None:
                return
            # 仅在默认标题时重命名 (避免覆盖用户已命名的会话)
            if current["title"] not in ("新对话", "新会话", ""):
                return
            # 取首条消息前 12 字, 去除换行
            title = first_message.replace("\n", " ").strip()[:12]
            if not title:
                return
            self._chat_repo.update_title(self._session_id, title)
            self._update_session_btn(title)
        except (sqlite3.DatabaseError, RuntimeError):
            logger.exception("自动重命名会话失败")

    def get_chat_history(self, limit: int = 10) -> list[ChatMessage]:
        """获取当前会话的最近 N 条消息 (转为 ChatMessage, 供 AgentLoop 多轮上下文)。

        Returns:
            ChatMessage 列表, 按时间正序
        """
        from fsa.agent.llm_client import ChatMessage

        if self._session_id is None or self._chat_repo is None:
            return []
        try:
            messages = self._chat_repo.get_messages(self._session_id)
        except (sqlite3.DatabaseError, RuntimeError):
            logger.exception("读取会话历史失败")
            return []
        history: list[ChatMessage] = []
        for m in messages[-limit:]:
            role = m.get("role", "user")
            content = m.get("content", "")
            if role in ("user", "assistant") and content:
                history.append(ChatMessage(role=role, content=content))
        return history
