"""主题系统: 品牌色、字体、结果卡片 QSS。

将 DESIGN_SYSTEM.md 中的设计令牌映射到 qfluentwidgets 主题。
"""

from __future__ import annotations

from PySide6.QtGui import QColor, QFont
from qfluentwidgets import Theme, setTheme, setThemeColor

# ── 设计令牌 (DESIGN_SYSTEM.md) ──
BRAND_COLOR = "#4f46e5"
SUCCESS_COLOR = "#10b981"
ERROR_COLOR = "#ef4444"
WARNING_COLOR = "#f59e0b"
INFO_COLOR = "#3b82f6"

# ── 结果卡片 QSS (亮色) ──
CARD_QSS_LIGHT = """
ResultCard[status="pass"] {
    border-left: 4px solid #10b981;
    background-color: #f0fdf4;
    border-radius: 8px;
}
ResultCard[status="fail"] {
    border-left: 4px solid #ef4444;
    background-color: #fef2f2;
    border-radius: 8px;
}
ResultCard[status="error"] {
    border-left: 4px solid #f59e0b;
    background-color: #fffbeb;
    border-radius: 8px;
}
ResultCard[status="skip"] {
    border-left: 4px solid #94a3b8;
    background-color: #f8fafc;
    border-radius: 8px;
}
"""

# ── 结果卡片 QSS (暗色) ──
CARD_QSS_DARK = """
ResultCard[status="pass"] {
    border-left: 4px solid #10b981;
    background-color: #052e16;
    border-radius: 8px;
}
ResultCard[status="fail"] {
    border-left: 4px solid #ef4444;
    background-color: #450a0a;
    border-radius: 8px;
}
ResultCard[status="error"] {
    border-left: 4px solid #f59e0b;
    background-color: #422006;
    border-radius: 8px;
}
ResultCard[status="skip"] {
    border-left: 4px solid #94a3b8;
    background-color: #1e293b;
    border-radius: 8px;
}
"""


def apply_theme(dark: bool = False) -> None:
    """应用亮色或暗色主题。"""
    setTheme(Theme.DARK if dark else Theme.LIGHT)
    setThemeColor(QColor(BRAND_COLOR))


def get_mono_font(size: int = 10) -> QFont:
    """获取等宽字体 (用于金额显示)。"""
    return QFont("Consolas", size)


def get_card_qss() -> tuple[str, str]:
    """返回结果卡片的 (light_qss, dark_qss)。"""
    return CARD_QSS_LIGHT, CARD_QSS_DARK
