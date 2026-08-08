"""AI 浮动按钮: 固定在右下角的纯色圆形按钮。

匹配 Demo v4 设计: 纯色 brand-600, 消息气泡图标, 无渐变。
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QPushButton, QWidget


class AgentFAB(QPushButton):
    """AI 助手浮动按钮。"""

    clicked_fab = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("AgentFAB")
        self.setFixedSize(48, 48)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("AI 诊断助手")
        self.setText("AI")
        self.setStyleSheet(
            """
            QPushButton#AgentFAB {
                background-color: #4f46e5;
                color: white;
                border: none;
                border-radius: 24px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton#AgentFAB:hover {
                background-color: #4338ca;
            }
            """
        )
        self.clicked.connect(self.clicked_fab.emit)
