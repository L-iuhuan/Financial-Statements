"""顶栏: 页面标题 + 副标题 + 操作按钮组。

匹配 Demo v4 设计: 半透明毛玻璃背景, 右侧操作按钮。
图标使用 FluentIcon (离线可用), 不使用 Emoji。
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)
from qfluentwidgets import FluentIcon


class Topbar(QFrame):
    """顶栏组件: 标题 + 副标题 + 操作按钮。"""

    theme_clicked = Signal()
    reset_clicked = Signal()
    validate_clicked = Signal()
    export_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Topbar")
        self.setFixedHeight(48)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 0, 24, 0)
        layout.setSpacing(16)

        self._title = QLabel("数据导入与校验")
        self._title.setObjectName("TopbarTitle")
        layout.addWidget(self._title)

        self._subtitle = QLabel("准备导入报表")
        self._subtitle.setObjectName("TopbarSubtitle")
        layout.addWidget(self._subtitle)

        layout.addStretch()

        # 主题切换按钮 (图标)
        self._theme_btn = QPushButton()
        self._theme_btn.setObjectName("BtnIcon")
        self._theme_btn.setFixedSize(36, 36)
        self._theme_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._theme_btn.setToolTip("切换深色/浅色 (Ctrl+D)")
        self._theme_btn.clicked.connect(self.theme_clicked.emit)
        self.set_theme_icon(False)
        layout.addWidget(self._theme_btn)

        self._reset_btn = QPushButton(" 重置")
        # qicon(): 主题同步图标引擎 (icon() 会在构造时烘焙颜色, 切主题后不刷新)
        self._reset_btn.setIcon(FluentIcon.ROTATE.qicon())
        self._reset_btn.setObjectName("BtnSecondary")
        self._reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._reset_btn.clicked.connect(self.reset_clicked.emit)
        layout.addWidget(self._reset_btn)

        self._validate_btn = QPushButton(" 执行校验")
        self._validate_btn.setIcon(
            FluentIcon.PLAY.icon(color=QColor("white"))
        )
        self._validate_btn.setIconSize(QSize(16, 16))
        self._validate_btn.setObjectName("BtnPrimary")
        self._validate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._validate_btn.setEnabled(False)
        self._validate_btn.clicked.connect(self.validate_clicked.emit)
        layout.addWidget(self._validate_btn)

        self._export_btn = QPushButton(" 导出底稿")
        self._export_btn.setIcon(FluentIcon.DOWNLOAD.qicon())
        self._export_btn.setObjectName("BtnSecondary")
        self._export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._export_btn.setEnabled(False)
        self._export_btn.clicked.connect(self.export_clicked.emit)
        layout.addWidget(self._export_btn)

    def set_title(self, title: str, subtitle: str = "") -> None:
        self._title.setText(title)
        self._subtitle.setText(subtitle)

    def set_validate_enabled(self, enabled: bool) -> None:
        self._validate_btn.setEnabled(enabled)

    def set_export_enabled(self, enabled: bool) -> None:
        self._export_btn.setEnabled(enabled)

    def set_theme_icon(self, dark: bool) -> None:
        # 深色模式显示太阳(切到浅色), 浅色模式显示月亮(切到深色)
        icon = FluentIcon.QUIET_HOURS if dark else FluentIcon.BRIGHTNESS
        # qicon(): 随主题自动重绘, 无需在每次切换时重建
        self._theme_btn.setIcon(icon.qicon())
