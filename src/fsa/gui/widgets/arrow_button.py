"""自绘向下箭头按钮。

背景/边框/文字仍走 QSS (QPushButton 渲染在你的环境已验证可靠),
右侧的向下箭头用 QPainter 直接绘制, 完全不依赖 QSS 子控件
(::down-arrow 等在你的 Windows 环境不渲染, 是日期选择器/下拉框
反复修复无效的根因)。

颜色随主题: 绘制时读 current_palette, 并通过 bind_theme_listener
在主题切换后重绘。
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPolygonF
from PySide6.QtWidgets import QPushButton

from fsa.gui.theme import bind_theme_listener, current_palette


class ArrowButton(QPushButton):
    """右侧绘制向下箭头的按钮 (箭头自绘, 不用子控件 QSS)。"""

    def __init__(self, parent: QPushButton | None = None) -> None:
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        # 主题切换后重绘箭头颜色
        bind_theme_listener(self, self.update)

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        p = current_palette()
        color_name = p.get("text_disabled", "#9ca3af") if not self.isEnabled() else p.get("text_secondary", "#6b7280")
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(color_name))
        w = self.width()
        h = self.height()
        cx = w - 14.0
        cy = h / 2.0
        triangle = QPolygonF(
            [QPointF(cx - 5, cy - 3), QPointF(cx + 5, cy - 3), QPointF(cx, cy + 3)]
        )
        painter.drawPolygon(triangle)
        painter.end()
