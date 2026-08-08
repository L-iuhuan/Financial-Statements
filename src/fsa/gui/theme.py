"""主题系统: 设计令牌 + QSS 生成。

将 DESIGN_SYSTEM.md 中的设计令牌映射到 PySide6 QSS。
支持亮色/暗色双套配色, 运行时切换。
"""

from __future__ import annotations

from PySide6.QtGui import QColor, QFont
from qfluentwidgets import Theme, setTheme, setThemeColor

# ── 设计令牌 (DESIGN_SYSTEM.md) ──

# 品牌色
BRAND_50 = "#eef2ff"
BRAND_100 = "#e0e7ff"
BRAND_200 = "#c7d2fe"
BRAND_500 = "#6366f1"
BRAND_600 = "#4f46e5"
BRAND_700 = "#4338ca"

# 语义色
SUCCESS = "#10b981"
SUCCESS_BG = "#ecfdf5"
SUCCESS_BORDER = "#a7f3d0"
ERROR = "#ef4444"
ERROR_BG = "#fef2f2"
ERROR_BORDER = "#fecaca"
WARNING = "#f59e0b"
WARNING_BG = "#fffbeb"
WARNING_BORDER = "#fde68a"
INFO = "#3b82f6"
INFO_BG = "#eff6ff"

# 间距
SPACE = {
    0: "0px", 1: "4px", 2: "8px", 3: "12px", 4: "16px",
    5: "20px", 6: "24px", 8: "32px", 10: "40px", 12: "48px", 16: "64px",
}

# 圆角
RADIUS_SM = "4px"
RADIUS_MD = "6px"
RADIUS_LG = "8px"
RADIUS_XL = "12px"


def _light_palette() -> dict[str, str]:
    """亮色配色字典。"""
    return {
        "bg_app": "#f8f9fa",
        "bg_surface": "#ffffff",
        "bg_surface_hover": "#f3f4f6",
        "bg_surface_active": "#e5e7eb",
        "bg_sidebar": "#fafafa",
        "bg_acrylic": "rgba(255,255,255,0.72)",
        "text_primary": "#111827",
        "text_secondary": "#6b7280",
        "text_tertiary": "#9ca3af",
        "text_disabled": "#d1d5db",
        "border": "#e5e7eb",
        "border_strong": "#d1d5db",
        "success": SUCCESS, "success_bg": SUCCESS_BG,
        "error": ERROR, "error_bg": ERROR_BG,
        "warning": WARNING, "warning_bg": WARNING_BG,
        "info": INFO, "info_bg": INFO_BG,
        "brand_50": BRAND_50, "brand_100": BRAND_100,
        "brand_200": BRAND_200, "brand_500": BRAND_500,
        "brand_600": BRAND_600, "brand_700": BRAND_700,
    }


def _dark_palette() -> dict[str, str]:
    """暗色配色字典。"""
    return {
        "bg_app": "#0a0a0b",
        "bg_surface": "#18181b",
        "bg_surface_hover": "#27272a",
        "bg_surface_active": "#3f3f46",
        "bg_sidebar": "#0f0f10",
        "bg_acrylic": "rgba(24,24,27,0.72)",
        "text_primary": "#f9fafb",
        "text_secondary": "#9ca3af",
        "text_tertiary": "#6b7280",
        "text_disabled": "#4b5563",
        "border": "#27272a",
        "border_strong": "#3f3f46",
        "success": "#34d399", "success_bg": "#052e1b",
        "error": "#f87171", "error_bg": "#450a0a",
        "warning": "#fbbf24", "warning_bg": "#422006",
        "info": "#60a5fa", "info_bg": "#0c1c33",
        "brand_50": "#1e1b4b", "brand_100": "#312e81",
        "brand_200": "#3730a3", "brand_500": "#818cf8",
        "brand_600": "#6366f1", "brand_700": "#4f46e5",
    }


def _generate_qss(p: dict[str, str]) -> str:
    """根据配色字典生成完整 QSS。"""
    return f"""
    /* ── 全局 ── */
    QWidget {{
        font-family: "HarmonyOS Sans SC", "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", sans-serif;
        font-size: 13px;
        color: {p["text_primary"]};
    }}
    QMainWindow, QWidget#MainWindow {{
        background-color: {p["bg_app"]};
    }}

    /* ── 侧边栏 ── */
    QFrame#Sidebar {{
        background-color: {p["bg_sidebar"]};
        border-right: 1px solid {p["border"]};
    }}
    QFrame#SidebarLogo {{
        background: transparent;
    }}
    QLabel#SidebarLogoText {{
        font-size: 15px;
        font-weight: 600;
        color: {p["text_primary"]};
    }}
    QFrame#SidebarLogoIcon {{
        background-color: {p["brand_600"]};
        border-radius: 6px;
    }}
    QLabel#SidebarSectionLabel {{
        font-size: 11px;
        font-weight: 500;
        color: {p["text_tertiary"]};
        padding: 8px 12px 4px 12px;
    }}
    QPushButton#NavItem {{
        text-align: left;
        padding: 8px 12px;
        border: none;
        border-radius: 4px;
        font-size: 13px;
        font-weight: 500;
        color: {p["text_secondary"]};
        background: transparent;
    }}
    QPushButton#NavItem:hover {{
        background-color: {p["bg_surface_hover"]};
        color: {p["text_primary"]};
    }}
    QPushButton#NavItem[active="true"] {{
        background-color: {p["brand_50"]};
        color: {p["brand_700"]};
    }}
    QFrame#SidebarFooter {{
        border-top: 1px solid {p["border"]};
    }}
    QLabel#SidebarVersion {{
        font-size: 11px;
        color: {p["text_tertiary"]};
    }}

    /* ── 顶栏 ── */
    QFrame#Topbar {{
        background-color: {p["bg_acrylic"]};
        border-bottom: 1px solid {p["border"]};
    }}
    QLabel#TopbarTitle {{
        font-size: 15px;
        font-weight: 600;
        color: {p["text_primary"]};
    }}
    QLabel#TopbarSubtitle {{
        font-size: 12px;
        color: {p["text_tertiary"]};
    }}

    /* ── 按钮 ── */
    QPushButton#BtnPrimary {{
        background-color: {p["brand_600"]};
        color: white;
        border: none;
        border-radius: 6px;
        padding: 8px 16px;
        font-size: 13px;
        font-weight: 500;
    }}
    QPushButton#BtnPrimary:hover {{
        background-color: {p["brand_700"]};
    }}
    QPushButton#BtnPrimary:disabled {{
        background-color: {p["brand_600"]};
        color: rgba(255,255,255,0.5);
    }}
    QPushButton#BtnSecondary {{
        background-color: {p["bg_surface"]};
        color: {p["text_primary"]};
        border: 1px solid {p["border"]};
        border-radius: 6px;
        padding: 8px 16px;
        font-size: 13px;
        font-weight: 500;
    }}
    QPushButton#BtnSecondary:hover {{
        background-color: {p["bg_surface_hover"]};
        border-color: {p["border_strong"]};
    }}
    QPushButton#BtnIcon {{
        background-color: {p["bg_surface"]};
        color: {p["text_secondary"]};
        border: 1px solid {p["border"]};
        border-radius: 6px;
        padding: 6px;
    }}
    QPushButton#BtnIcon:hover {{
        background-color: {p["bg_surface_hover"]};
        color: {p["text_primary"]};
        border-color: {p["border_strong"]};
    }}

    /* ── 拖放区 ── */
    QFrame#DropZone {{
        border: 2px dashed {p["border_strong"]};
        border-radius: 8px;
        background-color: {p["bg_surface"]};
    }}
    QFrame#DropZone[drag="true"] {{
        border-color: {p["brand_500"]};
        background-color: {p["brand_50"]};
    }}
    QLabel#DropZoneText {{
        font-size: 15px;
        font-weight: 500;
        color: {p["text_primary"]};
    }}
    QLabel#DropZoneHint {{
        font-size: 12px;
        color: {p["text_tertiary"]};
    }}

    /* ── 汇总卡片 ── */
    QFrame#SummaryCard {{
        background-color: {p["bg_surface"]};
        border: 1px solid {p["border"]};
        border-radius: 8px;
    }}
    QFrame#SummaryCard:hover {{
        border-color: {p["border_strong"]};
    }}
    QLabel#SummaryCardLabel {{
        font-size: 12px;
        font-weight: 500;
        color: {p["text_secondary"]};
    }}
    QLabel#SummaryCardValue {{
        font-size: 22px;
        font-weight: 600;
        color: {p["text_primary"]};
        font-family: "JetBrains Mono", "Cascadia Code", "Consolas", monospace;
    }}
    QLabel#SummaryCardSub {{
        font-size: 11px;
        color: {p["text_tertiary"]};
    }}

    /* ── 规则卡片 ── */
    QFrame#RuleCard {{
        background-color: {p["bg_surface"]};
        border: 1px solid {p["border"]};
        border-radius: 8px;
    }}
    QFrame#RuleCard:hover {{
        border-color: {p["border_strong"]};
    }}
    QLabel#RuleBadge {{
        font-size: 11px;
        font-weight: 600;
        font-family: "JetBrains Mono", "Consolas", monospace;
        background-color: {p["bg_surface_hover"]};
        color: {p["text_secondary"]};
        padding: 2px 8px;
        border-radius: 4px;
    }}
    QLabel#RuleName {{
        font-size: 14px;
        font-weight: 600;
        color: {p["text_primary"]};
    }}
    QLabel#FormulaLabel {{
        font-size: 12px;
        font-family: "JetBrains Mono", "Consolas", monospace;
        color: {p["text_secondary"]};
        background-color: {p["bg_app"]};
        border: 1px solid {p["border"]};
        border-radius: 4px;
        padding: 8px 12px;
    }}

    /* ── AI 浮动按钮 ── */
    QPushButton#AgentFAB {{
        background-color: {p["brand_600"]};
        color: white;
        border: none;
        border-radius: 24px;
    }}
    QPushButton#AgentFAB:hover {{
        background-color: {p["brand_700"]};
    }}

    /* ── AI 抽屉 ── */
    QFrame#AgentDrawer {{
        background-color: {p["bg_surface"]};
        border-left: 1px solid {p["border"]};
    }}
    QFrame#AgentResizeHandle {{
        background-color: {p["border"]};
    }}
    QFrame#AgentResizeHandle:hover {{
        background-color: {p["brand_500"]};
    }}
    QFrame#AgentOverlay {{
        background-color: rgba(0,0,0,0.2);
    }}
    QFrame#AgentContextBar {{
        background-color: {p["brand_50"]};
        border-bottom: 1px solid {p["border"]};
    }}
    QPlainTextEdit#AgentInput {{
        background-color: {p["bg_app"]};
        border: 1px solid {p["border"]};
        border-radius: 6px;
        color: {p["text_primary"]};
        font-size: 13px;
        padding: 8px;
    }}

    /* ── 表格 ── */
    QTableWidget {{
        background-color: {p["bg_surface"]};
        border: 1px solid {p["border"]};
        border-radius: 8px;
        gridline-color: {p["border"]};
    }}
    QHeaderView::section {{
        background-color: {p["bg_surface_hover"]};
        color: {p["text_secondary"]};
        font-weight: 600;
        font-size: 12px;
        padding: 8px 12px;
        border: none;
        border-bottom: 1px solid {p["border"]};
    }}
    QTableWidget::item {{
        padding: 8px 12px;
        border-bottom: 1px solid {p["border"]};
    }}

    /* ── 滚动区域 ── */
    QScrollArea {{
        border: none;
        background: transparent;
    }}
    QScrollBar:vertical {{
        background: transparent;
        width: 8px;
        margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background: {p["border_strong"]};
        border-radius: 4px;
        min-height: 30px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {p["text_tertiary"]};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}
    """


_LIGHT_QSS = _generate_qss(_light_palette())
_DARK_QSS = _generate_qss(_dark_palette())


def apply_theme(dark: bool = False) -> None:
    """应用亮色或暗色主题。"""
    setTheme(Theme.DARK if dark else Theme.LIGHT)
    setThemeColor(QColor(BRAND_600))


def get_qss(dark: bool = False) -> str:
    """返回当前主题的 QSS。"""
    return _DARK_QSS if dark else _LIGHT_QSS


def get_mono_font(size: int = 10) -> QFont:
    """获取等宽字体 (用于金额显示)。"""
    return QFont("JetBrains Mono", size)


def get_ui_font(size: int = 10) -> QFont:
    """获取 UI 字体。"""
    return QFont("HarmonyOS Sans SC", size)


def get_color(name: str, dark: bool = False) -> str:
    """按名称获取颜色值。"""
    p = _dark_palette() if dark else _light_palette()
    return p.get(name, "")
