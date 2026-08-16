"""汇总卡片组件: 圆点指示器 + 数字 + 标签。

匹配 Demo v4 设计: 22px 数字, 深色文字, 左上角小圆点。
"""

from __future__ import annotations

from PySide6.QtCore import QEvent
from PySide6.QtGui import QEnterEvent
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
)

from fsa.gui.theme import (
    bind_theme_listener,
    get_mono_font,
    get_shadow_color,
)

# 圆点类型 -> 主题调色板语义色键名
_DOT_PALETTE_KEYS: dict[str, str] = {
    "success": "success",
    "error": "error",
    "warning": "warning",
    "info": "info",
}


class SummaryCard(QFrame):
    """单张汇总卡片: 圆点 + 数字 + 标签。"""

    def __init__(self, dot_type: str = "info") -> None:
        super().__init__()
        self.setObjectName("SummaryCard")
        self._dot_type = dot_type
        self._setup_ui()
        self._on_theme_changed()
        # 注册主题监听并随控件销毁自动注销, 防止死监听器累积泄漏
        bind_theme_listener(self, self._on_theme_changed)

    def enterEvent(self, event: QEnterEvent) -> None:
        """hover 时挂阴影 (QSS 不支持 box-shadow, 用 QGraphicsDropShadowEffect)。

        参数取「阴影克制」原则: 小模糊半径 + 低透明度 + 2px 纵向偏移。
        """
        if self.graphicsEffect() is None:
            effect = QGraphicsDropShadowEffect(self)
            effect.setBlurRadius(10)
            effect.setOffset(0, 2)
            effect.setColor(get_shadow_color(hover=True))
            self.setGraphicsEffect(effect)
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
        """离开时卸载阴影, 恢复轻量渲染。"""
        self.setGraphicsEffect(None)  # type: ignore[arg-type]  # Qt 允许 None 卸载 effect
        super().leaveEvent(event)

    def _on_theme_changed(self) -> None:
        """主题切换: 刷新圆点颜色 + 已挂载阴影的颜色 (深浅主题透明度不同)。"""
        self._apply_dot_color()
        effect = self.graphicsEffect()
        if isinstance(effect, QGraphicsDropShadowEffect):
            effect.setColor(get_shadow_color(hover=True))

    def _apply_dot_color(self) -> None:
        """圆点颜色跟随当前主题调色板 (深色下用暗色语义色, 避免刺眼)。"""
        self._dot.setProperty("dot_type", self._dot_type)
        self._dot.style().unpolish(self._dot)
        self._dot.style().polish(self._dot)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)

        # 上方: 圆点 + 标签
        top = QHBoxLayout()
        top.setSpacing(8)

        self._dot = QLabel("●")
        self._dot.setObjectName("SummaryCardDot")
        self._dot.setProperty("dot_type", self._dot_type)
        top.addWidget(self._dot)

        self._label = QLabel("")
        self._label.setObjectName("SummaryCardLabel")
        top.addWidget(self._label)
        top.addStretch()
        layout.addLayout(top)

        # 中间: 大数字
        self._value = QLabel("0")
        self._value.setObjectName("SummaryCardValue")
        self._value.setFont(get_mono_font(16))
        layout.addWidget(self._value)

        # 下方: 辅助文本
        self._sub = QLabel("")
        self._sub.setObjectName("SummaryCardSub")
        layout.addWidget(self._sub)

    def set_data(self, label: str, value: int | str, sub: str = "") -> None:
        self._label.setText(label)
        self._value.setText(str(value))
        self._sub.setText(sub)
