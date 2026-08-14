"""汇总卡片组件: 圆点指示器 + 数字 + 标签。

匹配 Demo v4 设计: 22px 数字, 深色文字, 左上角小圆点。
"""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from fsa.gui.theme import current_palette, get_mono_font, register_theme_listener

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
        self._apply_dot_color()
        register_theme_listener(self._apply_dot_color)

    def _apply_dot_color(self) -> None:
        """圆点颜色跟随当前主题调色板 (深色下用暗色语义色, 避免刺眼)。"""
        key = _DOT_PALETTE_KEYS.get(self._dot_type, "info")
        color = current_palette()[key]
        self._dot.setStyleSheet(f"color: {color}; font-size: 10px;")

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)

        # 上方: 圆点 + 标签
        top = QHBoxLayout()
        top.setSpacing(8)

        self._dot = QLabel("●")
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
