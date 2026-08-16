"""AI 浮动按钮: 固定在右下角的纯色圆形按钮。

匹配 Demo v4 设计: 纯色 brand-600, 消息气泡图标, 无渐变。
带红色角标，当校验存在失败时显示。
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QPushButton, QWidget

from fsa.gui.theme import current_palette


class AgentFAB(QPushButton):
    """AI 助手浮动按钮。"""

    clicked_fab = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("AgentFAB")
        self.setFixedSize(48, 48)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("AI 诊断助手")
        # 对话气泡图标, 显式白色 (默认黑图标在靛蓝底上不可读)
        from PySide6.QtGui import QColor
        from qfluentwidgets import FluentIcon
        self.setIcon(
            FluentIcon.MESSAGE.icon(color=QColor("white"))
        )
        from PySide6.QtCore import QSize
        self.setIconSize(QSize(22, 22))
        self._setup_style()

        self._badge = QLabel("!", self)
        self._badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._badge.setFixedSize(16, 16)
        # 角标完全落在按钮范围内 (48px 按钮, 16px 角标), 避免越界被裁剪
        self._badge.move(self.width() - 18, 2)
        self._badge.hide()
        self._update_badge_style()

        self.clicked.connect(self.clicked_fab.emit)

    def _setup_style(self) -> None:
        p = current_palette()
        self.setStyleSheet(
            f"""
            QPushButton#AgentFAB {{
                background-color: {p['brand_600']};
                color: white;
                border: none;
                border-radius: 24px;
                font-size: 12px;
                font-weight: bold;
            }}
            QPushButton#AgentFAB:hover {{
                background-color: {p['brand_700']};
            }}
            """
        )

    def _update_badge_style(self) -> None:
        p = current_palette()
        self._badge.setStyleSheet(
            f"""
            QLabel {{
                background-color: {p['error']};
                color: white;
                border-radius: 8px;
                font-size: 10px;
                font-weight: bold;
            }}
            """
        )

    def set_badge(self, visible: bool) -> None:
        """显示或隐藏角标。"""
        if visible:
            self._badge.show()
        else:
            self._badge.hide()
