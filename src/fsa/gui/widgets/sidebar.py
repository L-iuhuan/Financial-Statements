"""自定义侧边栏: logo + 导航项 + 底部版本信息。

替代 FluentWindow 默认导航, 完全匹配 Demo v4 设计。
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from PySide6.QtGui import QFont

# 导航项配置: (object_name, label, icon_text)
_NAV_ITEMS: list[tuple[str, str, str, str]] = [
    # (section, object_name, label, icon)
    ("工作区", "navImport", "数据导入", "📥"),
    ("工作区", "navAudit", "审计底稿", "📋"),
    ("系统", "navRules", "规则管理", "📐"),
    ("系统", "navHistory", "历史记录", "🕐"),
    ("系统", "navSettings", "系统设置", "⚙"),
]


class NavButton(QPushButton):
    """侧边栏导航按钮。"""

    clicked_nav = Signal(str)

    def __init__(self, object_name: str, label: str, icon: str = "") -> None:
        super().__init__()
        self.setObjectName("NavItem")
        self._nav_id = object_name
        self.setText(f"  {icon}  {label}" if icon else f"  {label}")
        self.setFixedHeight(36)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setProperty("active", False)
        self.clicked.connect(lambda: self.clicked_nav.emit(self._nav_id))

    def set_active(self, active: bool) -> None:
        self.setProperty("active", active)
        self.style().polish(self)


class Sidebar(QFrame):
    """自定义侧边栏: logo + 导航 + 底部。"""

    nav_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(240)
        self._nav_buttons: dict[str, NavButton] = {}
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 12, 8, 0)
        layout.setSpacing(0)

        # Logo 区域
        logo_frame = QFrame()
        logo_frame.setObjectName("SidebarLogo")
        logo_layout = QHBoxLayout(logo_frame)
        logo_layout.setContentsMargins(12, 4, 12, 4)
        logo_layout.setSpacing(12)

        logo_icon = QLabel("稽")
        logo_icon.setObjectName("SidebarLogoIcon")
        logo_icon.setFixedSize(32, 32)
        logo_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_icon.setStyleSheet(
            "background-color: #4f46e5; color: white; "
            "border-radius: 6px; font-size: 16px; font-weight: bold;"
        )
        logo_layout.addWidget(logo_icon)

        logo_text = QLabel("勾稽校验系统")
        logo_text.setObjectName("SidebarLogoText")
        logo_layout.addWidget(logo_text)
        logo_layout.addStretch()

        layout.addWidget(logo_frame)
        layout.addSpacing(24)

        # 导航项
        current_section = ""
        for section, nav_id, label, icon in _NAV_ITEMS:
            if section != current_section:
                section_label = QLabel(section)
                section_label.setObjectName("SidebarSectionLabel")
                layout.addWidget(section_label)
                current_section = section

            btn = NavButton(nav_id, label, icon)
            btn.clicked_nav.connect(self._on_nav)
            self._nav_buttons[nav_id] = btn
            layout.addWidget(btn)
            layout.addSpacing(2)

        layout.addStretch()

        # 底部版本信息
        footer = QFrame()
        footer.setObjectName("SidebarFooter")
        footer_layout = QVBoxLayout(footer)
        footer_layout.setContentsMargins(12, 8, 12, 8)

        version = QLabel("版本 0.1.0 (MVP)")
        version.setObjectName("SidebarVersion")
        footer_layout.addWidget(version)

        license_label = QLabel("MIT 开源 · 内部使用")
        license_label.setObjectName("SidebarVersion")
        footer_layout.addWidget(license_label)

        layout.addWidget(footer)

    def _on_nav(self, nav_id: str) -> None:
        for nid, btn in self._nav_buttons.items():
            btn.set_active(nid == nav_id)
        self.nav_changed.emit(nav_id)

    def set_active_nav(self, nav_id: str) -> None:
        for nid, btn in self._nav_buttons.items():
            btn.set_active(nid == nav_id)
        self.nav_changed.emit(nav_id)
