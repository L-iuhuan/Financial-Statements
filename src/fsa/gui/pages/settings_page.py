"""系统设置页面: 报告期间、深色模式、关于。"""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget
from qfluentwidgets import LineEdit, SwitchButton

from fsa.gui.app_state import AppState
from fsa.gui.theme import apply_theme


class SettingsPage(QWidget):
    """系统设置页面。"""

    def __init__(self, state: AppState) -> None:
        super().__init__()
        self.setObjectName("SettingsPage")
        self._state = state
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("系统设置")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        layout.addWidget(title)

        period_title = QLabel("报告期间")
        period_title.setStyleSheet("font-size: 14px; font-weight: 500;")
        layout.addWidget(period_title)

        self._period_input = LineEdit()
        self._period_input.setPlaceholderText("如: 2024-12")
        self._period_input.setText(self._state.period)
        self._period_input.textChanged.connect(self._on_period_changed)
        layout.addWidget(self._period_input)

        theme_title = QLabel("深色模式")
        theme_title.setStyleSheet("font-size: 14px; font-weight: 500;")
        layout.addWidget(theme_title)

        self._theme_switch = SwitchButton()
        self._theme_switch.checkedChanged.connect(self._on_theme_toggled)
        layout.addWidget(self._theme_switch)

        about = QLabel(
            "财务报表勾稽校验系统 v0.1.0\n"
            "离线、CAS 专用、确定性规则驱动\n"
            "MIT License"
        )
        about.setStyleSheet("color: #64748b; font-size: 12px;")
        layout.addWidget(about)

        layout.addStretch()

    def _on_period_changed(self, text: str) -> None:
        self._state.set_period(text)

    def _on_theme_toggled(self, checked: bool) -> None:
        apply_theme(dark=checked)
