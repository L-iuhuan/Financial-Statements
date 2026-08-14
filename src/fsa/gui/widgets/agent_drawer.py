"""AI 助手抽屉: 可拖拽缩放 + 遮罩点击收起 + 会话持久化。

匹配 Demo v4 设计:
- 左侧 4px 拖拽手柄 (min 280px, max 600px, default 380px)
- 会话选择器 (QMenu 下拉切换/新建)
- 消息时间戳
- 快速建议气泡
- 图标式头部按钮 (28x28 bordered)

消息/建议气泡渲染在 agent_messages.py (AgentMessageMixin),
会话管理与持久化在 agent_sessions.py (AgentSessionMixin)。
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from fsa.gui.theme import current_palette, register_theme_listener
from fsa.gui.widgets.agent_messages import AgentMessageMixin
from fsa.gui.widgets.agent_sessions import AgentSessionMixin
from fsa.storage.chat_repo import ChatRepo


class AgentDrawer(AgentSessionMixin, AgentMessageMixin):
    """AI 助手抽屉面板 (继承两 mixin, QFrame 由 mixin 提供)。"""

    close_requested = Signal()
    send_requested = Signal(str)
    context_cleared = Signal()
    # P1 取消机制: 忙碌条"■ 停止"按钮触发, main_window_agent 经 getattr 防御接线
    cancelRequested = Signal()

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
        self._apply_shell_styles()
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
        self._header = QFrame()
        self._header.setObjectName("AgentDrawerHeader")
        self._header.setFixedHeight(48)
        h = QHBoxLayout(self._header)
        h.setContentsMargins(16, 0, 12, 0)
        h.setSpacing(8)

        # 左侧 16px 圆形图标占位 (主色圆底白图标, 样式在 _apply_shell_styles)
        self._header_icon = QLabel()
        self._header_icon.setFixedSize(16, 16)
        self._header_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        from qfluentwidgets import FluentIcon
        self._header_icon.setPixmap(
            FluentIcon.CHAT.colored("#ffffff", "#ffffff").icon().pixmap(10, 10)
        )
        h.addWidget(self._header_icon)

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

        return self._header

    def _build_context_bar(self) -> QFrame:
        self._context_bar = QFrame()
        self._context_bar.setObjectName("AgentContextBar")
        self._context_bar.setVisible(False)
        self._context_bar.setFixedHeight(36)

        ctx = QHBoxLayout(self._context_bar)
        ctx.setContentsMargins(16, 6, 12, 6)
        ctx.setSpacing(6)

        # 左侧 6px 主色圆点 (chip 标识)
        self._context_dot = QLabel()
        self._context_dot.setFixedSize(6, 6)
        ctx.addWidget(self._context_dot)

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

    def _build_input_area(self) -> QFrame:
        area = QFrame()
        a = QVBoxLayout(area)
        a.setContentsMargins(16, 8, 16, 12)
        a.setSpacing(8)

        # ── 忙碌条 (LLM 后台任务期间显示): 文案 + 动画 + "■ 停止" ──
        self._busy_bar = QFrame()
        self._busy_bar.setObjectName("AgentBusyBar")
        self._busy_bar.setStyleSheet(
            "QFrame#AgentBusyBar { background: rgba(128,128,128,0.10); border-radius: 8px; }"
        )
        self._busy_bar.setVisible(False)
        bar_row = QHBoxLayout(self._busy_bar)
        bar_row.setContentsMargins(10, 4, 10, 4)
        bar_row.setSpacing(8)

        self._busy_label = QLabel("AI 正在分析")
        self._busy_label.setObjectName("AgentBusyLabel")
        self._busy_label.setStyleSheet("QLabel#AgentBusyLabel { font-size: 12px; }")
        bar_row.addWidget(self._busy_label)
        bar_row.addStretch()

        self._busy_stop_btn = QPushButton("■ 停止")
        self._busy_stop_btn.setObjectName("AgentBusyStopBtn")
        self._busy_stop_btn.setToolTip("停止生成")
        self._busy_stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._busy_stop_btn.setFixedHeight(24)
        # 红弱色描边 (半透明红, 明暗主题均可读)
        self._busy_stop_btn.setStyleSheet(
            "QPushButton#AgentBusyStopBtn {"
            "  color: rgba(239,68,68,0.95); border: 1px solid rgba(239,68,68,0.45);"
            "  border-radius: 4px; background: transparent; font-size: 12px; padding: 0 8px; }"
            "QPushButton#AgentBusyStopBtn:hover { background: rgba(239,68,68,0.12); }"
        )
        self._busy_stop_btn.clicked.connect(self.cancelRequested.emit)
        bar_row.addWidget(self._busy_stop_btn)

        # 动画: 400ms 轮换 "·/··/···" 后缀
        self._busy_timer = QTimer(self)
        self._busy_timer.setInterval(400)
        self._busy_timer.timeout.connect(self._on_busy_tick)
        self._busy_base_text = "AI 正在分析"
        self._busy_dot_count = 0
        self._busy_active = False

        # 兼容别名: 既有测试经 _busy_hint 检查忙碌显隐
        self._busy_hint = self._busy_bar

        a.addWidget(self._busy_bar)

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

        # ── 免责底栏 (持久显示, 半透明灰两种主题均可读) ──
        self._disclaimer_label = QLabel(
            "AI 输出仅供参考 · 不构成审计意见 · 请以规则引擎与人工复核为准"
        )
        self._disclaimer_label.setObjectName("AgentDisclaimerLabel")
        self._disclaimer_label.setWordWrap(True)  # 280px 窄窗允许两行
        self._disclaimer_label.setStyleSheet(
            "QLabel#AgentDisclaimerLabel { font-size: 10px; color: rgba(136,136,136,0.85); }"
        )
        a.addWidget(self._disclaimer_label)

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

    # ── 消息/会话管理 (渲染见 AgentMessageMixin, 会话见 AgentSessionMixin) ──

    def set_busy(self, busy: bool) -> None:
        """LLM 后台任务期间显示/隐藏忙碌条, 并启停文案动画。"""
        self._busy_active = busy
        if busy:
            self._busy_base_text = "AI 正在分析"
            self._busy_dot_count = 1
            self._busy_label.setText(self._busy_base_text + "·")
            self._busy_timer.start()
            self._busy_bar.setVisible(True)
        else:
            self._busy_timer.stop()
            self._busy_base_text = "AI 正在分析"
            self._busy_dot_count = 0
            self._busy_label.setText(self._busy_base_text)
            self._busy_bar.setVisible(False)

    def set_stage_hint(self, text: str) -> None:
        """更新忙碌条文案 (辩论阶段提示; 空串恢复默认)。

        线程安全: 可能被后台 worker 线程直接调用, 非 GUI 线程时
        经 QTimer.singleShot(0) marshal 到 GUI 线程执行。
        """
        if QThread.currentThread() is self.thread():
            self._set_stage_hint_internal(text)
        else:
            QTimer.singleShot(0, lambda: self._set_stage_hint_internal(text))

    def _set_stage_hint_internal(self, text: str) -> None:
        """GUI 线程内实际更新文案 (非忙碌状态时忽略)。"""
        if not self._busy_active:
            return
        self._busy_base_text = text if text else "AI 正在分析"
        self._busy_dot_count = 0
        self._busy_label.setText(self._busy_base_text)

    def _on_busy_tick(self) -> None:
        """忙碌动画: 400ms 轮换 "·/··/···" 后缀。"""
        self._busy_dot_count = (self._busy_dot_count % 3) + 1
        self._busy_label.setText(self._busy_base_text + "·" * self._busy_dot_count)

    def set_context(self, rule_id: str, rule_name: str) -> None:
        self._context_rule_id = rule_id
        self._context_bar.setVisible(True)
        text = f"当前上下文: [{rule_id}] {rule_name}"
        # 超长规则名按抽屉宽度 elide (窄窗 280px 不溢出)。
        # 可用宽度 = 抽屉宽 - 左右 margin(28) - 圆点+间距(12) - 清除钮+间距(26)
        available = max(60, self.width() - 60)
        self._context_label.setText(
            self._context_label.fontMetrics().elidedText(
                text, Qt.TextElideMode.ElideRight, available
            )
        )

    def _clear_context(self) -> None:
        self._context_rule_id = None
        self._context_bar.setVisible(False)
        self._context_label.setText("")
        self.context_cleared.emit()

    def _apply_shell_styles(self) -> None:
        """应用壳层主题相关内联样式 (chip/头部图标/分隔线)。

        内联样式不随 theme QSS 自动刷新, 在 _on_theme_changed 时重应用。
        """
        p = current_palette()
        self._header.setStyleSheet(
            f"QFrame#AgentDrawerHeader {{ border-bottom: 1px solid {p['border']}; }}"
        )
        self._header_icon.setStyleSheet(
            f"QLabel {{ background: {p['brand_600']}; border-radius: 8px; }}"
        )
        self._context_bar.setStyleSheet(
            f"QFrame#AgentContextBar {{ background: {p['brand_50']}; border-radius: 12px; }}"
        )
        self._context_dot.setStyleSheet(
            f"QLabel {{ background: {p['brand_500']}; border-radius: 3px; }}"
        )

    def add_assistant_message(self, text: str) -> None:
        self._add_message("assistant", text)
        self._persist_message("assistant", text)

    def add_user_message(self, text: str) -> None:
        """外部调用: 添加用户消息并持久化 (不触发 send_requested)。"""
        self._add_message("user", text)
        self._persist_message("user", text)

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

    # ── 主题监听 ──

    def _on_theme_changed(self) -> None:
        """主题切换时刷新抽屉样式。"""
        self._apply_shell_styles()
        # 消息渲染层 (AgentMessageMixin) 的 QTextBrowser 内联 CSS
        # 不随 QSS polish 刷新, 需显式重注入深浅主题色。
        refresh = getattr(self, "refresh_theme", None)
        if callable(refresh):
            refresh()
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
