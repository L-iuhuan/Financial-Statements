"""AI 助手抽屉: 可拖拽缩放 + 遮罩点击收起 + 会话持久化。

匹配 Demo v4 设计:
- 左侧 4px 拖拽手柄 (min 280px, max 600px, default 380px)
- 会话选择器 (QMenu 下拉切换/新建)
- 消息时间戳
- 快速建议气泡
- 图标式头部按钮 (28x28 bordered)
"""

from __future__ import annotations

import sqlite3
from datetime import datetime

from loguru import logger
from PySide6.QtCore import QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from fsa.gui.theme import register_theme_listener
from fsa.storage.chat_repo import ChatRepo

_SUGGESTIONS: list[str] = [
    "什么是勾稽关系",
    "BS-BAL-001 规则",
    "差额超容差怎么办",
]


class AgentDrawer(QFrame):
    """AI 助手抽屉面板。"""

    close_requested = Signal()
    send_requested = Signal(str)
    context_cleared = Signal()

    MIN_WIDTH = 280
    MAX_WIDTH = 600
    DEFAULT_WIDTH = 380

    def __init__(
        self,
        chat_repo: ChatRepo | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("AgentDrawer")
        self.setFixedWidth(self.DEFAULT_WIDTH)
        self._dragging = False
        self._chat_repo = chat_repo
        self._session_id: int | None = None
        self._context_rule_id: str | None = None
        self._setup_ui()
        self._load_sessions_if_available()
        register_theme_listener(self._on_theme_changed)

    # ── UI 构建 ──

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._resize_handle = QFrame()
        self._resize_handle.setObjectName("AgentResizeHandle")
        self._resize_handle.setFixedWidth(4)
        self._resize_handle.setCursor(Qt.CursorShape.SizeHorCursor)
        layout.addWidget(self._resize_handle)

        content = QFrame()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        content_layout.addWidget(self._build_header())
        content_layout.addWidget(self._build_context_bar())
        content_layout.addWidget(self._build_messages(), stretch=1)
        content_layout.addWidget(self._build_suggestions())
        content_layout.addWidget(self._build_input_area())

        layout.addWidget(content, stretch=1)
        self._setup_dragging()

    def _build_header(self) -> QFrame:
        header = QFrame()
        header.setFixedHeight(48)
        h = QHBoxLayout(header)
        h.setContentsMargins(16, 0, 12, 0)
        h.setSpacing(8)

        title = QLabel("AI 诊断助手")
        title.setObjectName("AgentDrawerTitle")
        title.setStyleSheet("font-size: 15px; font-weight: 600;")
        h.addWidget(title)

        self._session_btn = QPushButton("会话 ▾")
        self._session_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._session_btn.setObjectName("AgentSessionBtn")
        self._session_btn.clicked.connect(self._show_session_menu)
        h.addWidget(self._session_btn)

        h.addStretch()

        # 清空当前会话按钮 (垃圾桶图标)
        from qfluentwidgets import FluentIcon
        clear_btn = QPushButton()
        clear_btn.setIcon(FluentIcon.DELETE.icon())
        clear_btn.setFixedSize(28, 28)
        clear_btn.setToolTip("清空当前会话")
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.setObjectName("AgentHeaderBtn")
        clear_btn.clicked.connect(self._clear_current_session)
        h.addWidget(clear_btn)

        # 关闭按钮 (X 图标)
        close_btn = QPushButton()
        close_btn.setIcon(FluentIcon.CLOSE.icon())
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setObjectName("AgentHeaderBtn")
        close_btn.clicked.connect(self.close_requested.emit)
        h.addWidget(close_btn)

        return header

    def _build_context_bar(self) -> QFrame:
        self._context_bar = QFrame()
        self._context_bar.setObjectName("AgentContextBar")
        self._context_bar.setVisible(False)
        self._context_bar.setFixedHeight(36)

        ctx = QHBoxLayout(self._context_bar)
        ctx.setContentsMargins(16, 0, 12, 0)

        self._context_label = QLabel("")
        self._context_label.setObjectName("AgentContextLabel")
        ctx.addWidget(self._context_label)
        ctx.addStretch()

        from qfluentwidgets import FluentIcon
        clear_btn = QPushButton()
        clear_btn.setIcon(FluentIcon.CLOSE.icon())
        clear_btn.setFixedSize(20, 20)
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.setObjectName("AgentClearBtn")
        clear_btn.clicked.connect(self._clear_context)
        ctx.addWidget(clear_btn)

        return self._context_bar

    @property
    def context_rule_id(self) -> str | None:
        """当前诊断上下文对应的规则 ID，无上下文时返回 None。"""
        return self._context_rule_id

    def _build_messages(self) -> QScrollArea:
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._rebuild_messages([])
        return self._scroll

    def _rebuild_messages(self, messages: list[dict]) -> None:
        """重建消息区域 (初始化/切换会话时调用)。"""
        old = self._scroll.widget()
        if old is not None:
            # 先隐藏再删除, 避免脱离 scroll 视口后闪现为独立窗口
            old.hide()
            old.deleteLater()

        container = QWidget()
        self._messages_layout = QVBoxLayout(container)
        self._messages_layout.setContentsMargins(16, 12, 16, 12)
        self._messages_layout.setSpacing(8)

        if not messages:
            self._add_message(
                "assistant",
                "您好！我是 AI 诊断助手。您可以点击校验结果中的"
                "「AI 诊断」按钮，我会针对具体规则进行分析。"
                "也可以直接向我提问关于财务勾稽、规则逻辑等任何问题。",
            )
        else:
            for msg in messages:
                self._add_message(
                    msg["role"],
                    msg["content"],
                    msg.get("created_at", ""),
                )

        self._messages_layout.addStretch()
        self._scroll.setWidget(container)

    def _build_suggestions(self) -> QFrame:
        self._suggestions_frame = QFrame()
        self._suggestions_layout = QHBoxLayout(self._suggestions_frame)
        self._suggestions_layout.setContentsMargins(16, 0, 16, 8)
        self._suggestions_layout.setSpacing(6)
        self._render_suggestions(_SUGGESTIONS)
        return self._suggestions_frame

    def _render_suggestions(self, suggestions: list[str]) -> None:
        """渲染建议气泡 (清空旧的并重建)。"""
        # 清空旧气泡
        while self._suggestions_layout.count():
            item = self._suggestions_layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()

        for text in suggestions:
            btn = QPushButton(text)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setObjectName("AgentSuggestion")
            # 按内容自适应宽度, 避免文字截断; 设置最小高度保证可点
            btn.setMinimumHeight(26)
            btn.setSizePolicy(
                QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed
            )
            btn.clicked.connect(
                lambda checked=False, t=text: self._quick_ask(t)
            )
            self._suggestions_layout.addWidget(btn)
        self._suggestions_layout.addStretch()

    def set_suggestions(self, suggestions: list[str]) -> None:
        """动态更新建议气泡内容 (根据上下文智能推荐)。"""
        if not hasattr(self, "_suggestions_layout"):
            return
        self._render_suggestions(suggestions)

    def _build_input_area(self) -> QFrame:
        area = QFrame()
        a = QVBoxLayout(area)
        a.setContentsMargins(16, 8, 16, 12)
        a.setSpacing(8)

        row = QHBoxLayout()
        row.setSpacing(8)

        self._input = QPlainTextEdit()
        self._input.setObjectName("AgentInput")
        self._input.setPlaceholderText("输入您的问题...")
        # 初始高度 36, 文字增多时自动增高 (上限 120px)
        self._input.setFixedHeight(36)
        self._input.textChanged.connect(self._auto_resize_input)
        self._input.keyPressEvent = self._on_key_press  # type: ignore[method-assign]
        row.addWidget(self._input, stretch=1)

        send_btn = QPushButton("发送")
        # 宽度足够完整显示"发送"二字 (sizeHint ~58px)
        send_btn.setMinimumSize(64, 36)
        send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        send_btn.setObjectName("BtnPrimary")
        send_btn.clicked.connect(self._on_send)
        row.addWidget(send_btn)

        a.addLayout(row)
        return area

    def _auto_resize_input(self) -> None:
        """根据输入内容自动调整输入框高度 (36px 起步, 上限 120px)。

        逐块计算可视行数: 硬换行 (blockCount) + 超长行的自动换行 (按宽度估算),
        确保多行文本和长文本都能正确增高。
        """
        doc = self._input.document()
        fm = self._input.fontMetrics()
        line_height = fm.lineSpacing()
        viewport_width = max(1, self._input.viewport().width() - 16)

        visual_lines = 0
        for i in range(doc.blockCount()):
            block = doc.findBlockByNumber(i)
            text = block.text()
            if not text:
                visual_lines += 1
                continue
            # 该块文本宽度 / 视口宽度 = 换行后行数 (向上取整)
            text_width = fm.horizontalAdvance(text)
            wrapped = max(1, -(-text_width // int(viewport_width)))
            visual_lines += wrapped

        content_height = visual_lines * line_height + 16
        new_height = int(max(36, min(120, content_height)))
        if new_height != self._input.height():
            self._input.setFixedHeight(new_height)

    # ── 消息管理 ──

    def _add_message(
        self, role: str, text: str, time_str: str = ""
    ) -> None:
        """添加一条消息 (气泡 + 时间戳)。"""
        if not time_str:
            time_str = datetime.now().strftime("%H:%M")
        elif " " in time_str:
            time_str = time_str.split(" ")[1][:5]

        is_user = role == "user"
        sender = "您" if is_user else "AI 助手"

        bubble = QLabel(text)
        bubble.setWordWrap(True)
        if is_user:
            bubble.setObjectName("AgentBubbleUser")
            # 用户气泡宽度随抽屉自适应 (约70%), 避免固定300px换行过碎
            bubble.setMaximumWidth(max(220, int(self.width() * 0.72)))
        else:
            bubble.setObjectName("AgentBubbleAssistant")
            bubble.setMaximumWidth(max(260, int(self.width() * 0.85)))

        time_label = QLabel(f"{sender} · {time_str}")
        time_label.setObjectName("AgentTimeLabel")

        bubble_row = QHBoxLayout()
        if is_user:
            bubble_row.addStretch()
            bubble_row.addWidget(bubble)
        else:
            bubble_row.addWidget(bubble)
            bubble_row.addStretch()

        time_row = QHBoxLayout()
        if is_user:
            time_row.addStretch()
            time_row.addWidget(time_label)
        else:
            time_row.addWidget(time_label)
            time_row.addStretch()

        msg_layout = QVBoxLayout()
        msg_layout.setSpacing(2)
        msg_layout.setContentsMargins(0, 0, 0, 0)
        msg_layout.addLayout(bubble_row)
        msg_layout.addLayout(time_row)

        self._messages_layout.insertLayout(
            self._messages_layout.count() - 1, msg_layout
        )

        # 记录最新消息 widget, 用于自动滚动
        self._last_bubble = bubble
        if is_user:
            self._last_user_bubble = bubble
            # 用户发送后, 延迟滚动到该用户消息 (等布局完成)
            QTimer.singleShot(50, self._scroll_to_latest_user)

    def set_context(self, rule_id: str, rule_name: str) -> None:
        self._context_rule_id = rule_id
        self._context_bar.setVisible(True)
        self._context_label.setText(f"当前上下文: [{rule_id}] {rule_name}")

    def _clear_context(self) -> None:
        self._context_rule_id = None
        self._context_bar.setVisible(False)
        self._context_label.setText("")
        self.context_cleared.emit()

    def add_assistant_message(self, text: str) -> None:
        self._add_message("assistant", text)
        self._persist_message("assistant", text)

    def add_user_message(self, text: str) -> None:
        """外部调用: 添加用户消息并持久化 (不触发 send_requested)。"""
        self._add_message("user", text)
        self._persist_message("user", text)

    def _scroll_to_latest_user(self) -> None:
        """滚动到最新用户消息 (而非最底部, 便于从问题开头阅读长回答)。"""
        bubble = getattr(self, "_last_user_bubble", None)
        if bubble is None:
            return
        # 用 ensureWidgetVisible 将该气泡滚动到可视区顶部附近
        self._scroll.ensureWidgetVisible(bubble, 0, 20)

    # ── 发送 / 快速提问 ──

    def _on_key_press(self, event) -> None:

        if (
            event.key() == Qt.Key.Key_Return
            and not event.modifiers() & Qt.KeyboardModifier.ShiftModifier
        ):
            self._on_send()
        else:
            QPlainTextEdit.keyPressEvent(self._input, event)

    def _on_send(self) -> None:
        # 手动发送不防抖: 用户打字快是合法操作
        text = self._input.toPlainText().strip()
        if not text:
            return
        self._add_message("user", text)
        self._persist_message("user", text)
        self._input.clear()
        self.send_requested.emit(text)

    def _quick_ask(self, question: str) -> None:
        """点击建议气泡直接发送 (防抖: 避免快速双击产生重复消息)。"""
        if self._is_send_locked():
            return
        self._add_message("user", question)
        self._persist_message("user", question)
        self.send_requested.emit(question)

    def _is_send_locked(self) -> bool:
        """建议气泡防抖: 500ms 内的重复点击被忽略 (仅用于 _quick_ask)。

        Returns:
            True 表示处于锁定期 (应忽略本次点击)
        """
        import time
        now = time.monotonic()
        last = getattr(self, "_last_send_time", 0.0)
        if now - last < 0.5:
            return True
        self._last_send_time = now
        return False

    # ── 会话管理 ──

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
        """更新会话按钮显示文本。"""
        display = title if len(title) <= 12 else title[:11] + "…"
        self._session_btn.setText(f"{display} ▾")

    # ── 持久化 ──

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

    def get_chat_history(self, limit: int = 10) -> list:
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
        history: list = []
        for m in messages[-limit:]:
            role = m.get("role", "user")
            content = m.get("content", "")
            if role in ("user", "assistant") and content:
                history.append(ChatMessage(role=role, content=content))
        return history

    # ── 主题监听 ──

    def _on_theme_changed(self) -> None:
        """主题切换时刷新抽屉样式。"""
        self.style().unpolish(self)
        self.style().polish(self)
        for child in self.findChildren(QWidget):
            child.style().unpolish(child)
            child.style().polish(child)

    # ── 拖拽缩放 ──

    def _setup_dragging(self) -> None:
        self._resize_handle.mousePressEvent = self._on_handle_press  # type: ignore[method-assign]
        self._resize_handle.mouseMoveEvent = self._on_handle_move  # type: ignore[method-assign]
        self._resize_handle.mouseReleaseEvent = self._on_handle_release  # type: ignore[method-assign]

    def _on_handle_press(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._drag_start_x = event.globalPosition().toPoint().x()
            self._drag_start_width = self.width()

    def _on_handle_move(self, event) -> None:
        if not self._dragging:
            return
        delta = self._drag_start_x - event.globalPosition().toPoint().x()
        new_width = self._drag_start_width + delta
        new_width = max(self.MIN_WIDTH, min(self.MAX_WIDTH, new_width))
        self.setFixedWidth(new_width)
        # 改宽后让父窗口重新定位: 抽屉右缘始终贴合窗口右侧 (锚定右缘)。
        # 否则仅 setFixedWidth 会让右缘随宽度右移 (拖左无反应/内容右扩),
        # 或左缘固定导致抽屉脱离右缘 (拖右时露出底层内容)。
        parent = self.parentWidget()
        position_fn = getattr(parent, "_position_drawer", None)
        if callable(position_fn):
            position_fn()

    def _on_handle_release(self, event) -> None:
        self._dragging = False
