"""AI 助手抽屉: 可拖拽缩放 + 遮罩点击收起 + 会话管理。

匹配 Demo v4 设计:
- 左侧 4px 拖拽手柄 (min 280px, max 600px, default 380px)
- 遮罩层点击收起
- 会话选择器
- 上下文栏
- 导出/导入按钮
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class AgentDrawer(QFrame):
    """AI 助手抽屉面板。"""

    close_requested = Signal()
    send_requested = Signal(str)
    context_cleared = Signal()

    MIN_WIDTH = 280
    MAX_WIDTH = 600
    DEFAULT_WIDTH = 380

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("AgentDrawer")
        self.setFixedWidth(self.DEFAULT_WIDTH)
        self._dragging = False
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 拖拽手柄
        self._resize_handle = QFrame()
        self._resize_handle.setObjectName("AgentResizeHandle")
        self._resize_handle.setFixedWidth(4)
        self._resize_handle.setCursor(Qt.CursorShape.SizeHorCursor)
        layout.addWidget(self._resize_handle)

        # 主内容
        content = QFrame()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        content_layout.addWidget(self._build_header())
        content_layout.addWidget(self._build_context_bar())
        content_layout.addWidget(self._build_messages(), stretch=1)
        content_layout.addWidget(self._build_input_area())

        layout.addWidget(content, stretch=1)

        self._setup_dragging()

    def _build_header(self) -> QFrame:
        header = QFrame()
        header.setFixedHeight(48)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(20, 0, 16, 0)

        title = QLabel("AI 诊断助手")
        title.setStyleSheet("font-size: 15px; font-weight: 600;")
        h_layout.addWidget(title)

        h_layout.addStretch()

        # 导出按钮
        export_btn = QPushButton("导出")
        export_btn.setFixedSize(32, 28)
        export_btn.setToolTip("导出对话到内网共享文件夹")
        export_btn.setStyleSheet(
            "QPushButton { border: 1px solid #e5e7eb; border-radius: 4px; "
            "background: transparent; font-size: 11px; color: #6b7280; }"
            "QPushButton:hover { background: #f3f4f6; }"
        )
        h_layout.addWidget(export_btn)

        # 导入按钮
        import_btn = QPushButton("导入")
        import_btn.setFixedSize(32, 28)
        import_btn.setToolTip("从内网共享文件夹导入对话")
        import_btn.setStyleSheet(export_btn.styleSheet())
        h_layout.addWidget(import_btn)

        # 关闭按钮
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(
            "QPushButton { border: none; background: transparent; "
            "font-size: 14px; color: #6b7280; }"
            "QPushButton:hover { background: #f3f4f6; border-radius: 4px; }"
        )
        close_btn.clicked.connect(self.close_requested.emit)
        h_layout.addWidget(close_btn)

        return header

    def _build_context_bar(self) -> QFrame:
        self._context_bar = QFrame()
        self._context_bar.setObjectName("AgentContextBar")
        self._context_bar.setVisible(False)
        self._context_bar.setFixedHeight(36)

        ctx_layout = QHBoxLayout(self._context_bar)
        ctx_layout.setContentsMargins(20, 0, 16, 0)

        self._context_label = QLabel("")
        self._context_label.setStyleSheet("font-size: 12px; color: #4338ca;")
        ctx_layout.addWidget(self._context_label)

        ctx_layout.addStretch()

        clear_btn = QPushButton("✕")
        clear_btn.setFixedSize(20, 20)
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.setStyleSheet(
            "QPushButton { border: none; background: transparent; "
            "font-size: 11px; color: #9ca3af; }"
            "QPushButton:hover { color: #ef4444; }"
        )
        clear_btn.clicked.connect(self._clear_context)
        ctx_layout.addWidget(clear_btn)

        return self._context_bar

    def _build_messages(self) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        self._messages_layout = QVBoxLayout(container)
        self._messages_layout.setContentsMargins(20, 16, 20, 16)
        self._messages_layout.setSpacing(12)

        # 欢迎消息
        self._add_message(
            "assistant",
            "您好！我是 AI 诊断助手。您可以点击校验结果中的「AI 诊断」按钮，"
            "我会针对具体规则进行分析。也可以直接向我提问关于财务勾稽、规则逻辑等任何问题。",
        )

        self._messages_layout.addStretch()
        scroll.setWidget(container)
        return scroll

    def _build_input_area(self) -> QFrame:
        area = QFrame()
        area_layout = QVBoxLayout(area)
        area_layout.setContentsMargins(20, 12, 20, 16)
        area_layout.setSpacing(8)

        input_row = QHBoxLayout()
        input_row.setSpacing(8)

        self._input = QPlainTextEdit()
        self._input.setObjectName("AgentInput")
        self._input.setPlaceholderText("输入您的问题...")
        self._input.setFixedHeight(36)
        self._input.keyPressEvent = self._on_key_press  # type: ignore
        input_row.addWidget(self._input, stretch=1)

        send_btn = QPushButton("发送")
        send_btn.setFixedSize(48, 36)
        send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        send_btn.setStyleSheet(
            "QPushButton { background-color: #4f46e5; color: white; "
            "border: none; border-radius: 6px; font-size: 12px; font-weight: 500; }"
            "QPushButton:hover { background-color: #4338ca; }"
        )
        send_btn.clicked.connect(self._on_send)
        input_row.addWidget(send_btn)

        area_layout.addLayout(input_row)
        return area

    def _setup_dragging(self) -> None:
        self._resize_handle.mousePressEvent = self._on_handle_press  # type: ignore
        self._resize_handle.mouseMoveEvent = self._on_handle_move  # type: ignore
        self._resize_handle.mouseReleaseEvent = self._on_handle_release  # type: ignore

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

    def _on_handle_release(self, event) -> None:
        self._dragging = False

    def _on_key_press(self, event) -> None:
        from PySide6.QtCore import QEvent
        from PySide6.QtGui import QKeyEvent

        if event.key() == Qt.Key.Key_Return and not event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            self._on_send()
        else:
            QPlainTextEdit.keyPressEvent(self._input, event)

    def _on_send(self) -> None:
        text = self._input.toPlainText().strip()
        if not text:
            return
        self._add_message("user", text)
        self._input.clear()
        self.send_requested.emit(text)

    def _add_message(self, role: str, text: str) -> None:
        bubble = QLabel(text)
        bubble.setWordWrap(True)

        if role == "user":
            bubble.setStyleSheet(
                "background-color: #4f46e5; color: white; "
                "border-radius: 8px; padding: 10px 14px; font-size: 13px;"
            )
            bubble.setMaximumWidth(300)
            wrap = QHBoxLayout()
            wrap.addStretch()
            wrap.addWidget(bubble)
        else:
            bubble.setStyleSheet(
                "background-color: #f3f4f6; color: #111827; "
                "border-radius: 8px; padding: 10px 14px; font-size: 13px;"
            )
            wrap = QHBoxLayout()
            wrap.addWidget(bubble)
            wrap.addStretch()

        self._messages_layout.insertLayout(self._messages_layout.count() - 1, wrap)

    def set_context(self, rule_id: str, rule_name: str) -> None:
        self._context_bar.setVisible(True)
        self._context_label.setText(f"当前上下文: [{rule_id}] {rule_name}")

    def _clear_context(self) -> None:
        self._context_bar.setVisible(False)
        self._context_label.setText("")
        self.context_cleared.emit()

    def add_assistant_message(self, text: str) -> None:
        self._add_message("assistant", text)
