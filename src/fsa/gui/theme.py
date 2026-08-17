"""主题系统: 设计令牌 + QSS 生成。

将 DESIGN_SYSTEM.md 中的设计令牌映射到 PySide6 QSS。
支持亮色/暗色双套配色, 运行时切换。
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable

from loguru import logger
from PySide6.QtCore import QEasingCurve, QObject, QPropertyAnimation, Qt
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication, QGraphicsOpacityEffect, QLabel, QWidget
from qfluentwidgets import Theme, setTheme, setThemeColor

# ── 设计令牌 (DESIGN_SYSTEM.md) ──

# 品牌色 — 精炼靛蓝 (refined indigo): 现代、活泼且专业, 与语义色明确区分
# 色相 ~245° 远离 success 绿(~160°)/error 红/warning 黄, 同时与 info 天蓝(~200°)拉开距离
# 白字在 BRAND_500/600 上对比度均 ≥4.5:1, 满足 WCAG AA
BRAND_50 = "#eef2ff"
BRAND_100 = "#e0e7ff"
BRAND_200 = "#c7d2fe"
BRAND_500 = "#5b5ee6"
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
INFO = "#0ea5e9"
INFO_BG = "#f0f9ff"
INFO_BORDER = "#7dd3fc"

# 金额语义色
AMOUNT_NEGATIVE = ERROR
AMOUNT_HIGHLIGHT = BRAND_600

# UI 字体栈: Windows 上 Microsoft YaHei UI 可用性最好, HarmonyOS Sans SC 作为回退
# 统一使用单一主族, 避免不同控件因回退字体不同导致的 hinting/粗细差异
UI_FONT_FAMILY = "Microsoft YaHei UI"
UI_FONT_FALLBACKS = '"HarmonyOS Sans SC", "Microsoft YaHei", "Segoe UI", system-ui, sans-serif'

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
RADIUS_FULL = "9999px"


# ── 模块级主题状态 ──

_current_dark: bool = False
_theme_listeners: list[Callable[[], None]] = []


def _light_palette() -> dict[str, str]:
    """亮色配色字典。"""
    return {
        "bg_app": "#f8f9fa",
        "bg_surface": "#ffffff",
        "bg_surface_hover": "#f3f4f6",
        "bg_surface_active": "#e5e7eb",
        "bg_sidebar": "#fafafa",
        "bg_acrylic": "rgba(255,255,255,0.72)",
        "overlay": "rgba(0,0,0,0.2)",
        "text_primary": "#111827",
        "text_secondary": "#6b7280",
        "text_tertiary": "#9ca3af",
        "text_disabled": "#d1d5db",
        "border": "#e5e7eb",
        "border_strong": "#d1d5db",
        "success": SUCCESS, "success_bg": SUCCESS_BG, "success_border": SUCCESS_BORDER,
        "error": ERROR, "error_bg": ERROR_BG, "error_border": ERROR_BORDER,
        "warning": WARNING, "warning_bg": WARNING_BG, "warning_border": WARNING_BORDER,
        "info": INFO, "info_bg": INFO_BG, "info_border": INFO_BORDER,
        "brand_50": BRAND_50, "brand_100": BRAND_100,
        "brand_200": BRAND_200, "brand_500": BRAND_500,
        "brand_600": BRAND_600, "brand_700": BRAND_700,
        "amount_negative": AMOUNT_NEGATIVE,
        "amount_highlight": AMOUNT_HIGHLIGHT,
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
        "overlay": "rgba(0,0,0,0.4)",
        "text_primary": "#f9fafb",
        "text_secondary": "#9ca3af",
        "text_tertiary": "#6b7280",
        "text_disabled": "#4b5563",
        "border": "#27272a",
        "border_strong": "#3f3f46",
        "success": "#34d399", "success_bg": "#052e1b", "success_border": "#065f46",
        "error": "#f87171", "error_bg": "#450a0a", "error_border": "#991b1b",
        "warning": "#fbbf24", "warning_bg": "#422006", "warning_border": "#92400e",
        "info": "#38bdf8", "info_bg": "#082f49", "info_border": "#0369a1",
        "brand_50": "#1e1b4b", "brand_100": "#312e81",
        "brand_200": "#4338ca", "brand_500": "#818cf8",
        "brand_600": "#5b5ee6", "brand_700": "#4f46e5",
        "amount_negative": "#f87171",
        "amount_highlight": "#818cf8",
    }


def _generate_qss(p: dict[str, str]) -> str:
    """根据配色字典生成完整 QSS。"""
    return f"""
    /* ── 全局 ── */
    QWidget {{
        font-family: "{UI_FONT_FAMILY}", {UI_FONT_FALLBACKS};
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
    QLabel#SidebarLogoIcon {{
        /* logo PNG 自带圆角方形品牌底色, 标签不再叠底, 避免双重底色边缘伪影 */
        background: transparent;
        color: white;
        font-size: 16px;
        font-weight: bold;
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
    QPushButton#NavItem:pressed {{
        background-color: {p["bg_surface_active"]};
    }}
    QPushButton#NavItem[active="true"] {{
        background-color: {p["brand_50"]};
        color: {p["brand_700"]};
        border-left: 3px solid {p["brand_600"]};
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

    /* ── 顶栏更新角标 (发现新版本常驻红点) ── */
    QPushButton#UpdateBadgeBtn {{
        background-color: {p["bg_surface"]};
        color: {p["text_secondary"]};
        border: 1px solid {p["border"]};
        border-radius: 6px;
        padding: 6px;
    }}
    QPushButton#UpdateBadgeBtn:hover {{
        background-color: {p["bg_surface_hover"]};
        color: {p["text_primary"]};
        border-color: {p["border_strong"]};
    }}
    QPushButton#UpdateBadgeBtn:pressed {{
        background-color: {p["bg_surface_active"]};
    }}
    QLabel#UpdateBadgeDot {{
        background-color: {p["error"]};
        border-radius: 4px;
    }}

    /* ── 更新对话框 ── */
    QTextBrowser#UpdateNotes {{
        background-color: {p["bg_app"]};
        color: {p["text_primary"]};
        border: 1px solid {p["border"]};
        border-radius: 6px;
        padding: 8px;
        font-size: 13px;
    }}
    QProgressBar#UpdateProgress {{
        background-color: {p["bg_surface_hover"]};
        border: 1px solid {p["border"]};
        border-radius: 4px;
        text-align: center;
        color: {p["text_secondary"]};
        font-size: 11px;
    }}
    QProgressBar#UpdateProgress::chunk {{
        background-color: {p["brand_500"]};
        border-radius: 4px;
    }}

    /* ── 按钮 ── */
    QPushButton#BtnPrimary {{
        background-color: {p["brand_600"]};
        color: white;
        border: none;
        border-radius: 6px;
        padding: 8px 16px;
        font-size: 13px;
        font-weight: 600;
    }}
    QPushButton#BtnPrimary:hover {{
        background-color: {p["brand_700"]};
    }}
    QPushButton#BtnPrimary:pressed {{
        background-color: {p["brand_700"]};
        padding-top: 9px;
        padding-bottom: 7px;
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
    QPushButton#BtnSecondary:pressed {{
        background-color: {p["bg_surface_active"]};
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
    QPushButton#BtnIcon:pressed {{
        background-color: {p["bg_surface_active"]};
    }}
    QPushButton#FilterTab {{
        background-color: {p["bg_surface"]};
        color: {p["text_secondary"]};
        border: 1px solid {p["border"]};
        border-radius: 6px;
        padding: 8px 16px;
        font-size: 13px;
        font-weight: 500;
    }}
    QPushButton#FilterTab:hover {{
        background-color: {p["bg_surface_hover"]};
        border-color: {p["border_strong"]};
    }}
    QPushButton#FilterTab:pressed {{
        background-color: {p["bg_surface_active"]};
    }}
    QPushButton#FilterTab[active="true"] {{
        background-color: {p["brand_50"]};
        color: {p["brand_700"]};
        border: 1px solid {p["brand_200"]};
        border-left: 3px solid {p["brand_600"]};
    }}
    QPushButton#TextBtn {{
        background-color: {p["bg_surface"]};
        color: {p["text_secondary"]};
        border: 1px solid {p["border"]};
        border-radius: 6px;
        padding: 6px 12px;
        font-size: 12px;
    }}
    QPushButton#TextBtn:hover {{
        background-color: {p["bg_surface_hover"]};
    }}
    QPushButton#TextBtn:pressed {{
        background-color: {p["bg_surface_active"]};
    }}
    QPushButton#DangerBtn {{
        background-color: {p["bg_surface"]};
        color: {p["error"]};
        border: 1px solid {p["error_border"]};
        border-radius: 6px;
        padding: 8px 16px;
        font-size: 13px;
        font-weight: 500;
    }}
    QPushButton#DangerBtn:hover {{
        background-color: {p["error_bg"]};
        border-color: {p["error"]};
    }}
    QPushButton#DangerBtn:pressed {{
        background-color: {p["error_border"]};
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
    QFrame#RuleCard:pressed {{
        background-color: {p["bg_surface_active"]};
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
    QFrame#RuleCard[disabled="true"] QLabel {{
        color: {p["text_disabled"]};
    }}
    QFrame#RuleCard[disabled="true"] QLabel#RuleBadge {{
        background-color: {p["bg_surface"]};
        color: {p["text_disabled"]};
    }}
    QLabel#RuleSeverityLabel[status="error"] {{
        color: {p["error"]};
        font-size: 12px;
        font-weight: 600;
    }}
    QLabel#RuleSeverityLabel[status="warning"] {{
        color: {p["warning"]};
        font-size: 12px;
        font-weight: 600;
    }}
    QLabel#RuleSeverityLabel[status="info"] {{
        color: {p["info"]};
        font-size: 12px;
        font-weight: 600;
    }}

    /* ── 报表卡片 ── */
    QFrame#ReportCard {{
        background-color: {p["bg_surface"]};
        border: 1px solid {p["border"]};
        border-radius: 8px;
    }}
    QFrame#ReportCard:hover {{
        border-color: {p["border_strong"]};
    }}
    QFrame#ReportCard:pressed {{
        background-color: {p["bg_surface_active"]};
    }}
    QFrame#ReportCardIcon {{
        background-color: {p["brand_50"]};
        border-radius: 6px;
    }}
    QLabel#ReportCardStatus {{
        font-size: 11px;
        font-weight: 600;
        color: {p["success"]};
        background-color: {p["success_bg"]};
        border: 1px solid {p["success_border"]};
        border-radius: 4px;
        padding: 2px 8px;
    }}

    /* ── 分区卡片 ── */
    QFrame#SectionCard {{
        background-color: {p["bg_surface"]};
        border: 1px solid {p["border"]};
        border-radius: 8px;
    }}

    /* ── 历史卡片 ── */
    QFrame#HistoryCard {{
        background-color: {p["bg_surface"]};
        border: 1px solid {p["border"]};
        border-radius: 8px;
    }}
    QFrame#HistoryCard:hover {{
        border-color: {p["border_strong"]};
    }}
    QFrame#HistoryCard:pressed {{
        background-color: {p["bg_surface_active"]};
    }}

    /* ── 历史回看横幅 ── */
    QFrame#HistoryViewBanner {{
        background-color: {p["brand_50"]};
        border: 1px solid {p["brand_200"]};
        border-radius: 8px;
    }}
    QLabel#HistoryViewBannerText {{
        font-size: 12px;
        color: {p["brand_700"]};
    }}

    /* ── 空状态 ── */
    QLabel#EmptyLabel {{
        font-size: 14px;
        color: {p["text_tertiary"]};
    }}
    QFrame#EmptyContainer {{
        background-color: {p["bg_surface"]};
        border: 2px dashed {p["border"]};
        border-radius: 8px;
    }}
    QLabel#EmptyTitle {{
        font-size: 15px;
        font-weight: 600;
        color: {p["text_secondary"]};
    }}

    /* ── 元信息/值标签 ── */
    QLabel#MetaLabel {{
        font-size: 12px;
        color: {p["text_tertiary"]};
    }}
    QLabel#ValueLabel {{
        font-size: 13px;
        color: {p["text_secondary"]};
        font-family: "JetBrains Mono", "Cascadia Code", "Consolas", monospace;
    }}
    QLabel#SaveHintLabel {{
        font-size: 12px;
        color: {p["success"]};
        background-color: {p["success_bg"]};
        border: 1px solid {p["success_border"]};
        border-radius: 6px;
        padding: 6px 12px;
    }}
    QLabel#FormulaPreviewLabel {{
        font-size: 12px;
        color: {p["info"]};
        background-color: {p["info_bg"]};
        border: 1px solid {p["info_border"]};
        border-radius: 6px;
        padding: 6px 10px;
    }}

    /* ── 图标框架 ── */
    QFrame#IconFrame {{
        background-color: {p["brand_50"]};
        border-radius: 6px;
    }}

    /* ── 输入框 ── */
    QLineEdit#StyledInput {{
        background-color: {p["bg_surface"]};
        color: {p["text_primary"]};
        border: 1px solid {p["border"]};
        border-radius: 6px;
        padding: 8px;
        font-family: "Consolas", monospace;
        font-size: 12px;
    }}
    QLineEdit#StyledInput:focus {{
        border-color: {p["brand_500"]};
    }}
    QLineEdit#SearchInput {{
        background-color: {p["bg_surface"]};
        color: {p["text_primary"]};
        border: 1px solid {p["border"]};
        border-radius: 6px;
        padding: 8px 12px;
        font-size: 13px;
    }}
    QLineEdit#SearchInput:focus {{
        border-color: {p["brand_500"]};
    }}

    /* ── 日期选择器 (PeriodPicker: 文本框+箭头按钮复合控件, 不用子控件 QSS) ── */
    QLineEdit#PeriodInput {{
        background-color: {p["bg_surface"]};
        color: {p["text_primary"]};
        border: 1px solid {p["border"]};
        border-top-left-radius: 6px;
        border-bottom-left-radius: 6px;
        padding: 8px 10px;
        font-size: 13px;
        selection-background-color: {p["brand_500"]};
        selection-color: white;
    }}
    QLineEdit#PeriodInput:focus {{
        border-color: {p["brand_500"]};
    }}
    QPushButton#PeriodArrowBtn {{
        background-color: {p["bg_surface"]};
        border: 1px solid {p["border"]};
        border-left: none;
        border-top-right-radius: 6px;
        border-bottom-right-radius: 6px;
    }}
    QPushButton#PeriodArrowBtn:hover {{
        background-color: {p["bg_surface_hover"]};
    }}
    QPushButton#PeriodArrowBtn:pressed {{
        background-color: {p["bg_surface_active"]};
    }}

    /* ── 下拉选择控件 (DropdownCombo 按钮) ── */
    QPushButton#DropdownButton {{
        background-color: {p["bg_surface"]};
        color: {p["text_primary"]};
        border: 1px solid {p["border"]};
        border-radius: 6px;
        /* 右侧 36px 为自绘箭头预留区, 文字永不与箭头重叠 */
        padding: 0px 36px 0px 12px;
        font-size: 13px;
        min-height: 32px;
        text-align: left;
    }}
    QPushButton#DropdownButton:hover {{
        border-color: {p["border_strong"]};
    }}
    QPushButton#DropdownButton:pressed {{
        background-color: {p["bg_surface_active"]};
    }}
    QPushButton#DropdownButton:focus {{
        border-color: {p["brand_500"]};
    }}

    /* ── 下拉框 (custom_rule_dialog 的 QComboBox) ── */
    QComboBox {{
        background-color: {p["bg_surface"]};
        color: {p["text_primary"]};
        border: 1px solid {p["border"]};
        border-radius: 6px;
        /* 纵向 padding 置 0: Qt 对 QComboBox 的 QSS padding 会二次计入高度
           (每 2px 纵向 padding → 高 4px), 置 0 后高度 34px 与 FilterTab 一致 */
        padding: 0px 12px;
        font-size: 13px;
        min-height: 32px;
    }}
    QComboBox:hover {{
        border-color: {p["border_strong"]};
    }}
    QComboBox:pressed {{
        background-color: {p["bg_surface_active"]};
    }}
    QComboBox:focus {{
        border-color: {p["brand_500"]};
    }}
    QComboBox::drop-down {{
        /* origin=border + 底色区分: 按钮区与主体明显分离, 不再是"纯文本框"观感 */
        subcontrol-origin: border;
        subcontrol-position: top right;
        width: 28px;
        background-color: {p["bg_surface_hover"]};
        border: none;
        border-left: 1px solid {p["border"]};
        border-top-right-radius: 5px;
        border-bottom-right-radius: 5px;
    }}
    QComboBox::down-arrow {{
        width: 10px;
        height: 6px;
        border-left: 5px solid transparent;
        border-right: 5px solid transparent;
        border-top: 6px solid {p["text_primary"]};
        border-bottom: none;
    }}
    QComboBox QAbstractItemView {{
        background-color: {p["bg_surface"]};
        color: {p["text_primary"]};
        border: 1px solid {p["border"]};
        border-radius: 6px;
        padding: 4px;
        outline: none;
        selection-background-color: {p["brand_50"]};
        selection-color: {p["brand_700"]};
    }}
    QComboBox QAbstractItemView::item {{
        border-radius: 4px;
        padding: 6px 8px;
        min-height: 28px;
    }}
    QComboBox QAbstractItemView::item:hover {{
        background-color: {p["bg_surface_hover"]};
        color: {p["text_primary"]};
    }}
    QComboBox QAbstractItemView::item:selected {{
        background-color: {p["brand_50"]};
        color: {p["brand_700"]};
    }}

    /* ── 日历弹窗 ── */
    QCalendarWidget {{
        background-color: {p["bg_surface"]};
        color: {p["text_primary"]};
        border: 1px solid {p["border"]};
        border-radius: 8px;
    }}
    QCalendarWidget QWidget#qt_calendar_navigationbar {{
        background-color: {p["bg_surface_hover"]};
        border-top-left-radius: 8px;
        border-top-right-radius: 8px;
        padding: 4px;
    }}
    QCalendarWidget QToolButton {{
        background-color: transparent;
        color: {p["text_primary"]};
        border-radius: 4px;
        padding: 4px 8px;
        font-size: 13px;
        font-weight: 500;
    }}
    QCalendarWidget QToolButton:hover {{
        background-color: {p["brand_50"]};
    }}
    QCalendarWidget QToolButton:pressed {{
        background-color: {p["brand_100"]};
    }}
    QCalendarWidget QTableView {{
        background-color: {p["bg_surface"]};
        color: {p["text_primary"]};
        selection-background-color: {p["brand_500"]};
        selection-color: white;
        gridline-color: {p["border"]};
        border-bottom-left-radius: 8px;
        border-bottom-right-radius: 8px;
    }}
    QCalendarWidget QTableView::item:selected {{
        background-color: {p["brand_500"]};
        color: white;
        border-radius: 4px;
    }}
    QCalendarWidget QTableView::item:hover {{
        background-color: {p["brand_50"]};
    }}
    QCalendarWidget QHeaderView::section {{
        background-color: {p["bg_surface"]};
        color: {p["text_secondary"]};
        font-weight: 600;
        padding: 6px;
        border: none;
    }}
    QPushButton#AgentFAB {{
        background-color: {p["brand_600"]};
        color: white;
        border: none;
        border-radius: {RADIUS_FULL};
    }}
    QPushButton#AgentFAB:hover {{
        background-color: {p["brand_700"]};
    }}
    QPushButton#AgentFAB:pressed {{
        background-color: {p["brand_700"]};
    }}

    /* ── AI 抽屉 ── */
    QFrame#AgentDrawer {{
        background-color: {p["bg_surface"]};
        /* V1: 抽屉与主内容的层次边界用 1px 强调边框分隔线 (随主题), 不用重阴影 */
        border-left: 1px solid {p["border_strong"]};
    }}
    QFrame#AgentResizeHandle {{
        background-color: {p["border"]};
    }}
    QFrame#AgentResizeHandle:hover {{
        background-color: {p["brand_500"]};
    }}
    QFrame#AgentOverlay {{
        background-color: {p["overlay"]};
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
    }}
    QPushButton#AgentHeaderBtn {{
        background-color: {p["bg_surface"]};
        color: {p["text_secondary"]};
        border: 1px solid {p["border"]};
        border-radius: 4px;
        font-size: 13px;
    }}
    QPushButton#AgentHeaderBtn:hover {{
        background-color: {p["bg_surface_hover"]};
        border-color: {p["border_strong"]};
        color: {p["text_primary"]};
    }}
    QPushButton#AgentHeaderBtn:pressed {{
        background-color: {p["bg_surface_active"]};
    }}
    QPushButton#AgentSessionBtn {{
        background-color: {p["bg_surface"]};
        color: {p["text_secondary"]};
        border: 1px solid {p["border"]};
        border-radius: 4px;
        padding: 2px 8px;
        font-size: 12px;
    }}
    QPushButton#AgentSessionBtn:hover {{
        background-color: {p["bg_surface_hover"]};
    }}
    QLabel#AgentContextLabel {{
        font-size: 12px;
        color: {p["brand_700"]};
    }}
    QPushButton#AgentClearBtn {{
        border: none;
        background: transparent;
        font-size: 11px;
        color: {p["text_tertiary"]};
    }}
    QPushButton#AgentClearBtn:hover {{
        color: {p["error"]};
    }}
    QPushButton#AgentSuggestion {{
        background-color: {p["bg_surface"]};
        color: {p["text_secondary"]};
        border: 1px solid {p["border"]};
        border-radius: 12px;
        padding: 4px 12px;
        font-size: 12px;
    }}
    QPushButton#AgentSuggestion:hover {{
        border-color: {p["brand_500"]};
        color: {p["brand_700"]};
        background-color: {p["brand_50"]};
    }}
    QPushButton#AgentSuggestion:pressed {{
        background-color: {p["brand_100"]};
    }}
    QLabel#AgentBubbleUser {{
        background-color: {p["brand_700"]};
        color: white;
        border-radius: 8px;
        padding: 10px 14px;
        font-size: 13px;
    }}
    QTextBrowser#AgentBubbleAssistant {{
        background-color: {p["bg_surface_hover"]};
        color: {p["text_primary"]};
        border: 1px solid {p["border_strong"]};
        border-radius: 10px;
        padding: 2px;
    }}
    QLabel#AgentBubbleAssistant {{
        background-color: {p["bg_surface_hover"]};
        color: {p["text_primary"]};
        border: 1px solid {p["border_strong"]};
        border-radius: 8px;
        padding: 10px 14px;
        font-size: 13px;
    }}
    QLabel#AgentTimeLabel {{
        font-size: 11px;
        color: {p["text_secondary"]};
    }}

    /* ── 诊断按钮 ── */
    QPushButton#DiagnoseBtn {{
        background-color: {p["brand_50"]};
        color: {p["brand_700"]};
        border: 1px solid {p["brand_200"]};
        border-radius: 4px;
        font-size: 11px;
        font-weight: 600;
    }}
    QPushButton#DiagnoseBtn:hover {{
        background-color: {p["brand_100"]};
        border-color: {p["brand_500"]};
    }}
    QPushButton#DiagnoseBtn:pressed {{
        background-color: {p["brand_200"]};
    }}

    /* ── 深度辩论按钮 (深色填充, 区别于诊断按钮) ── */
    QPushButton#DebateBtn {{
        background-color: {p["brand_600"]};
        color: #ffffff;
        border: none;
        border-radius: 4px;
        font-size: 11px;
        font-weight: 600;
    }}
    QPushButton#DebateBtn:hover {{
        background-color: {p["brand_700"]};
    }}
    QPushButton#DebateBtn:pressed {{
        background-color: {p["brand_700"]};
    }}

    /* ── 结果卡片内部标签 ── */
    QLabel#ResultIdLabel {{
        background-color: {p["bg_surface"]};
        color: {p["text_secondary"]};
        padding: 2px 8px;
        border-radius: 4px;
        font-family: "JetBrains Mono", "Consolas", monospace;
        font-size: 11px;
        font-weight: 600;
    }}
    QLabel#ResultFormula {{
        color: {p["text_secondary"]};
        background-color: {p["bg_surface"]};
        border: 1px solid {p["border"]};
        border-radius: 4px;
        padding: 8px 12px;
        font-size: 12px;
    }}
    QLabel#ResultMessage {{
        color: {p["text_secondary"]};
        font-size: 12px;
    }}
    QLabel#ResultGridLabel {{
        color: {p["text_secondary"]};
        font-size: 12px;
    }}
    QLabel#ResultGridValue {{
        font-weight: 600;
        font-size: 13px;
        color: {p["text_primary"]};
    }}
    QLabel#ResultTolerance {{
        color: {p["text_tertiary"]};
        font-size: 12px;
    }}

    /* ── 结果卡片状态色 ── */
    QFrame#ResultCard[status="pass"] {{
        background-color: {p["success_bg"]};
        border: 1px solid {p["success_border"]};
        border-radius: 8px;
    }}
    QFrame#ResultCard[status="fail"] {{
        background-color: {p["error_bg"]};
        border: 1px solid {p["error_border"]};
        border-radius: 8px;
    }}
    QFrame#ResultCard[status="error"] {{
        background-color: {p["warning_bg"]};
        border: 1px solid {p["warning_border"]};
        border-radius: 8px;
    }}
    QFrame#ResultCard[status="skip"] {{
        background-color: {p["bg_surface_hover"]};
        border: 1px solid {p["border"]};
        border-radius: 8px;
    }}
    QFrame#ResultCard[status="pass"]:hover {{
        border-color: {p["success"]};
    }}
    QFrame#ResultCard[status="fail"]:hover {{
        border-color: {p["error"]};
    }}
    QFrame#ResultCard[status="error"]:hover {{
        border-color: {p["warning"]};
    }}
    QFrame#ResultCard[status="skip"]:hover {{
        border-color: {p["border_strong"]};
    }}
    QFrame#ResultCard[status="pass"]:pressed {{
        background-color: {p["success_border"]};
    }}
    QFrame#ResultCard[status="fail"]:pressed {{
        background-color: {p["error_border"]};
    }}
    QFrame#ResultCard[status="error"]:pressed {{
        background-color: {p["warning_border"]};
    }}
    QFrame#ResultCard[status="skip"]:pressed {{
        background-color: {p["bg_surface_active"]};
    }}
    QLabel#ResultStatusLabel[status="pass"] {{
        color: {p["success"]};
    }}
    QLabel#ResultStatusLabel[status="fail"] {{
        color: {p["error"]};
    }}
    QLabel#ResultStatusLabel[status="error"] {{
        color: {p["warning"]};
    }}
    QLabel#ResultStatusLabel[status="skip"] {{
        color: {p["text_secondary"]};
    }}
    QLabel#ResultDiffLabel[status="pass"] {{
        color: {p["success"]};
    }}
    QLabel#ResultDiffLabel[status="fail"] {{
        color: {p["error"]};
    }}
    QLabel#ResultDiffLabel[status="error"] {{
        color: {p["warning"]};
    }}
    QLabel#ResultDiffLabel[status="skip"] {{
        color: {p["text_secondary"]};
    }}
    QLabel#ResultDiffLabel[negative="true"] {{
        color: {p["amount_negative"]};
    }}

    /* ── 汇总卡片圆点 ── */
    QLabel#SummaryCardDot[dot_type="success"] {{
        color: {p["success"]};
    }}
    QLabel#SummaryCardDot[dot_type="error"] {{
        color: {p["error"]};
    }}
    QLabel#SummaryCardDot[dot_type="warning"] {{
        color: {p["warning"]};
    }}
    QLabel#SummaryCardDot[dot_type="info"] {{
        color: {p["info"]};
    }}

    /* ── 菜单 ── */
    QMenu {{
        background-color: {p["bg_surface"]};
        border: 1px solid {p["border"]};
        border-radius: 6px;
        padding: 4px;
    }}
    QMenu::item {{
        padding: 6px 16px;
        border-radius: 4px;
        font-size: 12px;
        color: {p["text_secondary"]};
    }}
    QMenu::item:selected {{
        background-color: {p["brand_50"]};
        color: {p["brand_700"]};
    }}
    QMenu::separator {{
        height: 1px;
        background: {p["border"]};
        margin: 4px 8px;
    }}

    /* ── 表格 ── */
    QTableWidget {{
        background-color: {p["bg_surface"]};
        border: 1px solid {p["border"]};
        border-radius: 8px;
        gridline-color: {p["border"]};
        outline: none;
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
    QTableWidget::item:alternate {{
        background-color: {p["bg_surface_hover"]};
    }}
    QTableWidget::item:selected {{
        /* 显式选中态: 缺省时系统高亮会让单元格文字与底色相近, 看似"点击后内容消失" */
        background-color: {p["brand_100"]};
        color: {p["text_primary"]};
    }}

    /* ── 页面标题 ── */
    QLabel#PageTitle {{
        font-size: 15px;
        font-weight: 600;
        color: {p["text_primary"]};
    }}
    QLabel#SectionTitle {{
        font-size: 15px;
        font-weight: 600;
        color: {p["text_primary"]};
    }}
    QLabel#AgentDrawerTitle {{
        font-size: 15px;
        font-weight: 600;
        color: {p["text_primary"]};
    }}
    QLabel#AboutVersionSummary {{
        font-size: 14px;
        font-weight: 500;
        color: {p["text_secondary"]};
        padding-bottom: 4px;
    }}

    /* ── 滚动区域 ── */
    QScrollArea {{
        border: none;
        background: transparent;
    }}
    /* 页面内容容器: 背景随主题切换 */
    QWidget#PageContent {{
        background-color: {p["bg_app"]};
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


# ── 公共 API ──


def _build_palette(p: dict[str, str]) -> QPalette:
    """由设计令牌构建 QPalette。

    覆盖没有 QSS 规则命中的原生控件 (普通 QPushButton、QMessageBox、
    QDialog、QCheckBox 等): 它们用调色板自绘, 不设置暗色调色板时
    深色主题下仍为浅色 (白底白字)。
    """
    palette = QPalette()
    window = QColor(p["bg_app"])
    surface = QColor(p["bg_surface"])
    surface_hover = QColor(p["bg_surface_hover"])
    text = QColor(p["text_primary"])
    text_disabled = QColor(p["text_disabled"])
    tertiary = QColor(p["text_tertiary"])
    brand = QColor(p["brand_500"])
    white = QColor("#ffffff")
    for group in (QPalette.ColorGroup.Active, QPalette.ColorGroup.Inactive):
        palette.setColor(group, QPalette.ColorRole.Window, window)
        palette.setColor(group, QPalette.ColorRole.WindowText, text)
        palette.setColor(group, QPalette.ColorRole.Base, surface)
        palette.setColor(group, QPalette.ColorRole.AlternateBase, surface_hover)
        palette.setColor(group, QPalette.ColorRole.Text, text)
        palette.setColor(group, QPalette.ColorRole.Button, surface)
        palette.setColor(group, QPalette.ColorRole.ButtonText, text)
        palette.setColor(group, QPalette.ColorRole.Highlight, brand)
        palette.setColor(group, QPalette.ColorRole.HighlightedText, white)
        palette.setColor(group, QPalette.ColorRole.PlaceholderText, tertiary)
        palette.setColor(group, QPalette.ColorRole.ToolTipBase, surface_hover)
        palette.setColor(group, QPalette.ColorRole.ToolTipText, text)
        palette.setColor(group, QPalette.ColorRole.Link, brand)
    disabled = QPalette.ColorGroup.Disabled
    palette.setColor(disabled, QPalette.ColorRole.Window, window)
    palette.setColor(disabled, QPalette.ColorRole.Base, surface)
    palette.setColor(disabled, QPalette.ColorRole.Button, surface)
    palette.setColor(disabled, QPalette.ColorRole.WindowText, text_disabled)
    palette.setColor(disabled, QPalette.ColorRole.Text, text_disabled)
    palette.setColor(disabled, QPalette.ColorRole.ButtonText, text_disabled)
    return palette


def apply_theme(dark: bool = False) -> None:
    """应用亮色或暗色主题。"""
    global _current_dark
    _current_dark = dark
    setTheme(Theme.DARK if dark else Theme.LIGHT)
    setThemeColor(QColor(BRAND_600))
    # 无 QSS 规则的原生控件靠调色板自绘: 同步设置明暗调色板,
    # 修复深色主题下普通按钮/对话框/复选框等保持浅色 (白底白字) 的问题
    app = QApplication.instance()
    if isinstance(app, QApplication):
        app.setPalette(_build_palette(_dark_palette() if dark else _light_palette()))


def get_qss(dark: bool = False) -> str:
    """返回当前主题的 QSS。"""
    return _DARK_QSS if dark else _LIGHT_QSS


def get_mono_font(size: int = 10) -> QFont:
    """获取等宽字体 (用于金额显示)。"""
    font = QFont("JetBrains Mono", size)
    # 未安装 JetBrains Mono 时回退到系统等宽字体 (Qt 按平台选择)
    font.setStyleHint(QFont.StyleHint.Monospace)
    return font


def get_shadow_color(hover: bool = False) -> QColor:
    """卡片阴影颜色: 深色主题下加深以保证可见性。"""
    if _current_dark:
        return QColor(0, 0, 0, 90 if hover else 60)
    return QColor(0, 0, 0, 25 if hover else 10)


def get_ui_font(size: int = 13) -> QFont:
    """获取 UI 字体 (size 为像素尺寸, 与 QSS 保持一致)。"""
    font = QFont(UI_FONT_FAMILY)
    font.setPixelSize(size)
    font.setWeight(QFont.Weight.Normal)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias | QFont.StyleStrategy.PreferQuality)
    return font


def get_color(name: str, dark: bool = False) -> str:
    """按名称获取颜色值。"""
    p = _dark_palette() if dark else _light_palette()
    return p.get(name, "")


def is_dark_mode() -> bool:
    """返回当前是否为暗色模式。"""
    return _current_dark


def get_palette(dark: bool | None = None) -> dict[str, str]:
    """返回指定主题的配色字典。dark=None 表示当前主题。"""
    if dark is None:
        dark = _current_dark
    return _dark_palette() if dark else _light_palette()


def current_palette() -> dict[str, str]:
    """返回当前主题的配色字典。"""
    return get_palette(_current_dark)


def register_theme_listener(fn: Callable[[], None]) -> None:
    """注册主题切换监听器。"""
    _theme_listeners.append(fn)


def unregister_theme_listener(fn: Callable[[], None]) -> None:
    """注销主题切换监听器; 若未注册则静默。"""
    with contextlib.suppress(ValueError):
        _theme_listeners.remove(fn)


def bind_theme_listener(widget: QObject, fn: Callable[[], None]) -> None:
    """注册主题监听器，并随控件销毁自动注销（防死监听器泄漏）。

    替代直接调用 register_theme_listener 的推荐方式。
    """
    register_theme_listener(fn)

    def _cleanup(*_args: object) -> None:
        unregister_theme_listener(fn)

    widget.destroyed.connect(_cleanup)


def notify_theme_listeners() -> None:
    """通知所有监听器主题已切换, 并清理已失效的条目。"""
    dead: list[Callable[[], None]] = []
    for fn in _theme_listeners:
        try:
            fn()
        except RuntimeError as exc:
            # Qt C++ 对象已销毁, 该监听器失效, 予以清理
            msg = str(exc)
            if "already deleted" in msg or "C++ object" in msg:
                dead.append(fn)
        except Exception as exc:
            # 避免单个监听器异常影响其他监听器, 但须留痕便于排查
            logger.warning(f"主题监听器执行异常, 已跳过: {exc}")
            continue
    for fn in dead:
        with contextlib.suppress(ValueError):
            _theme_listeners.remove(fn)


# 进行中的主题过渡动画 (防止被 GC 提前回收)
_active_transition_anims: list[QPropertyAnimation] = []


def run_theme_transition(window: QWidget, apply_fn: Callable[[], None]) -> None:
    """主题切换过渡: 旧画面截图遮罩淡出 (200ms), 避免瞬间反色闪烁。

    先对窗口当前外观截屏作为遮罩, 再应用新主题, 最后淡出遮罩露出新外观。
    以下情况直接应用不做动画: 测试环境 (PYTEST_CURRENT_TEST)、无法截屏、
    上一次过渡动画仍在进行 (快速连续切换时避免截屏/动画堆积)。
    """
    import os

    in_test = os.environ.get("PYTEST_CURRENT_TEST") is not None
    if in_test or _active_transition_anims:
        apply_fn()
        return
    pixmap = window.grab()
    if pixmap.isNull():
        apply_fn()
        return
    overlay = QLabel(window)
    overlay.setPixmap(pixmap)
    overlay.setGeometry(window.rect())
    overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    apply_fn()
    overlay.show()
    overlay.raise_()
    effect = QGraphicsOpacityEffect(overlay)
    overlay.setGraphicsEffect(effect)
    anim = QPropertyAnimation(effect, b"opacity", overlay)
    anim.setDuration(200)
    anim.setStartValue(1.0)
    anim.setEndValue(0.0)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def _cleanup() -> None:
        overlay.deleteLater()
        if anim in _active_transition_anims:
            _active_transition_anims.remove(anim)

    anim.finished.connect(_cleanup)
    _active_transition_anims.append(anim)
    anim.start()
