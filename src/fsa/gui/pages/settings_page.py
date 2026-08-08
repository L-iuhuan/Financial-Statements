"""系统设置页面: 外观/校验参数/数据存储/关于。

匹配 Demo v4 设计: 多分区设置面板。
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from fsa.gui.app_state import AppState
from fsa.gui.theme import apply_theme, get_qss


class SettingsPage(QWidget):
    """系统设置页面。"""

    def __init__(self, state: AppState) -> None:
        super().__init__()
        self.setObjectName("SettingsPage")
        self._state = state
        self._dark = False
        self._setup_ui()

    def _setup_ui(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        layout.addWidget(self._build_appearance())
        layout.addWidget(self._build_validation_params())
        layout.addWidget(self._build_storage())
        layout.addWidget(self._build_about())
        layout.addStretch()

        scroll.setWidget(content)
        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.addWidget(scroll)

    def _section(self, title: str) -> tuple[QFrame, QVBoxLayout]:
        """创建设置分区。"""
        frame = QFrame()
        frame.setStyleSheet(
            "QFrame { background-color: #ffffff; border: 1px solid #e5e7eb; "
            "border-radius: 8px; }"
        )
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        label = QLabel(title)
        label.setStyleSheet("font-size: 14px; font-weight: 600;")
        layout.addWidget(label)

        return frame, layout

    def _row(self, label_text: str, desc: str = "") -> tuple[QHBoxLayout, QLabel]:
        """创建设置行: 标签 + 描述 + 右侧控件区。"""
        row = QHBoxLayout()
        row.setSpacing(8)

        info = QVBoxLayout()
        info.setSpacing(2)
        label = QLabel(label_text)
        label.setStyleSheet("font-size: 13px; font-weight: 500;")
        info.addWidget(label)
        if desc:
            d = QLabel(desc)
            d.setStyleSheet("font-size: 12px; color: #9ca3af;")
            info.addWidget(d)
        row.addLayout(info)
        row.addStretch()

        return row, label

    def _build_appearance(self) -> QFrame:
        frame, layout = self._section("外观")

        row, _ = self._row("主题模式", "选择浅色、深色或跟随系统")

        self._light_btn = QPushButton("浅色")
        self._dark_btn = QPushButton("深色")
        for btn in [self._light_btn, self._dark_btn]:
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(32)
            btn.setFixedSize(64, 32)

        self._light_btn.setChecked(True)
        self._light_btn.clicked.connect(lambda: self._set_theme(False))
        self._dark_btn.clicked.connect(lambda: self._set_theme(True))
        row.addWidget(self._light_btn)
        row.addWidget(self._dark_btn)
        layout.addLayout(row)

        self._update_theme_btns()
        return frame

    def _build_validation_params(self) -> QFrame:
        frame, layout = self._section("校验参数")

        # 默认容差
        row1, _ = self._row("默认容差 (绝对值)", "平衡类规则使用的默认容差，单位: 元")
        self._tolerance_input = QLineEdit("0.01")
        self._tolerance_input.setFixedSize(100, 32)
        self._tolerance_input.setStyleSheet(
            "QLineEdit { border: 1px solid #e5e7eb; border-radius: 6px; "
            "padding: 8px; font-family: 'Consolas', monospace; font-size: 12px; }"
        )
        row1.addWidget(self._tolerance_input)
        layout.addLayout(row1)

        # 毛利率波动阈值
        row2, _ = self._row("毛利率波动阈值", "同比波动超过此比例触发警告")
        threshold_row = QHBoxLayout()
        threshold_row.setSpacing(4)
        self._threshold_input = QLineEdit("30")
        self._threshold_input.setFixedSize(60, 32)
        self._threshold_input.setStyleSheet(self._tolerance_input.styleSheet())
        threshold_row.addWidget(self._threshold_input)
        pct = QLabel("%")
        pct.setStyleSheet("font-size: 12px; color: #9ca3af;")
        threshold_row.addWidget(pct)
        row2.addLayout(threshold_row)
        layout.addLayout(row2)

        return frame

    def _build_storage(self) -> QFrame:
        frame, layout = self._section("数据存储")

        # 数据库位置
        row1, _ = self._row("数据库位置", "SQLite 数据库文件路径")
        db_path = QLabel("C:\\Users\\...\\fsa_data.db (待初始化)")
        db_path.setStyleSheet(
            "font-size: 13px; color: #6b7280; "
            "font-family: 'Consolas', monospace;"
        )
        row1.addWidget(db_path)
        layout.addLayout(row1)

        # 历史保留天数
        row2, _ = self._row("历史记录保留", "自动清理超过此天数的校验记录")
        days_row = QHBoxLayout()
        days_row.setSpacing(4)
        self._days_input = QLineEdit("90")
        self._days_input.setFixedSize(60, 32)
        self._days_input.setStyleSheet(self._tolerance_input.styleSheet())
        days_row.addWidget(self._days_input)
        days_label = QLabel("天")
        days_label.setStyleSheet("font-size: 12px; color: #9ca3af;")
        days_row.addWidget(days_label)
        row2.addLayout(days_row)
        layout.addLayout(row2)

        return frame

    def _build_about(self) -> QFrame:
        frame, layout = self._section("关于")

        for label_text, value in [
            ("软件版本", "0.1.0 (MVP)"),
            ("开源许可", "MIT License"),
            ("规则库版本", "CAS v1.0.0 (44 条规则)"),
        ]:
            row, _ = self._row(label_text)
            val = QLabel(value)
            val.setStyleSheet(
                "font-size: 13px; color: #6b7280; "
                "font-family: 'Consolas', monospace;"
            )
            row.addWidget(val)
            layout.addLayout(row)

        return frame

    def _set_theme(self, dark: bool) -> None:
        self._dark = dark
        apply_theme(dark=dark)
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if isinstance(app, QApplication):
            app.setStyleSheet(get_qss(dark))
        self._update_theme_btns()

    def _update_theme_btns(self) -> None:
        active_qss = (
            "QPushButton { background-color: #4f46e5; color: white; "
            "border: none; border-radius: 6px; font-size: 12px; font-weight: 500; }"
        )
        inactive_qss = (
            "QPushButton { background-color: #ffffff; color: #6b7280; "
            "border: 1px solid #e5e7eb; border-radius: 6px; font-size: 12px; }"
            "QPushButton:hover { background-color: #f3f4f6; }"
        )
        self._light_btn.setStyleSheet(active_qss if not self._dark else inactive_qss)
        self._dark_btn.setStyleSheet(active_qss if self._dark else inactive_qss)
