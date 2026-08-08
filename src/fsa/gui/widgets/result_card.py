"""校验结果卡片组件 (Demo v4 设计)。

匹配 DESIGN_SYSTEM.md S14 修正:
- 白色背景 (不用彩色背景)
- 3px 左边框 (不用 4px)
- 规则 ID 用浅色底 + 深色文字 (不用彩色底 + 白字)
- 状态用图标+文字 (不用彩色 badge)
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

from fsa.core.models.result import ValidationResult
from fsa.gui.theme import get_mono_font

# 左边框颜色 (3px)
_BORDER_COLOR: dict[str, str] = {
    "pass": "#10b981",
    "fail": "#ef4444",
    "error": "#f59e0b",
}

# 状态图标 + 文字
_STATUS_ICON: dict[str, str] = {"pass": "✓", "fail": "✗", "error": "⚠"}
_STATUS_TEXT: dict[str, str] = {"pass": "通过", "fail": "不通过", "error": "异常"}
_STATUS_COLOR: dict[str, str] = {
    "pass": "#10b981",
    "fail": "#ef4444",
    "error": "#f59e0b",
}


class ResultCard(QFrame):
    """单条校验结果卡片 (Demo v4)。"""

    diagnose_clicked = Signal(str)  # rule_id

    def __init__(self, result: ValidationResult) -> None:
        super().__init__()
        self._result = result
        self.setObjectName("RuleCard")
        self._setup_ui()

    def _setup_ui(self) -> None:
        status = self._get_status_key()
        border_color = _BORDER_COLOR[status]

        self.setStyleSheet(
            f"""
            QFrame#RuleCard {{
                background-color: #ffffff;
                border: 1px solid #e5e7eb;
                border-left: 3px solid {border_color};
                border-radius: 8px;
            }}
            QFrame#RuleCard:hover {{
                border-color: #d1d5db;
            }}
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        layout.addLayout(self._build_header(status))
        layout.addLayout(self._build_values())
        layout.addWidget(self._build_formula())

        if not self._result.passed:
            msg = QLabel(self._result.message)
            msg.setWordWrap(True)
            msg.setStyleSheet("color: #6b7280; font-size: 12px;")
            layout.addWidget(msg)

        # AI 诊断按钮
        diagnose_btn = QPushButton("AI 诊断")
        diagnose_btn.setFixedSize(60, 22)
        diagnose_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        diagnose_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #eef2ff;
                color: #4338ca;
                border: 1px solid #c7d2fe;
                border-radius: 4px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #e0e7ff;
                border-color: #6366f1;
            }
            """
        )
        diagnose_btn.clicked.connect(
            lambda: self.diagnose_clicked.emit(self._result.rule_id)
        )
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(diagnose_btn)
        layout.addLayout(btn_row)

    def _get_status_key(self) -> str:
        if self._result.errored:
            return "error"
        return "pass" if self._result.passed else "fail"

    def _build_header(self, status: str) -> QHBoxLayout:
        header = QHBoxLayout()
        header.setSpacing(8)

        # 规则 ID (浅色底 + 深色文字, 不用彩色)
        id_label = QLabel(self._result.rule_id)
        id_label.setStyleSheet(
            "background-color: #f3f4f6; color: #6b7280; "
            "padding: 2px 8px; border-radius: 4px; "
            "font-family: 'JetBrains Mono', 'Consolas', monospace; "
            "font-size: 11px; font-weight: 600;"
        )
        header.addWidget(id_label)

        # 规则名称
        name_label = QLabel(self._result.rule_name)
        name_label.setStyleSheet("font-size: 14px; font-weight: 600;")
        header.addWidget(name_label, stretch=1)

        # 状态 (图标+文字, 不用 badge)
        status_label = QLabel(
            f"{_STATUS_ICON[status]} {_STATUS_TEXT[status]}"
        )
        status_label.setStyleSheet(
            f"color: {_STATUS_COLOR[status]}; "
            "font-weight: 500; font-size: 13px;"
        )
        header.addWidget(status_label)

        return header

    def _build_values(self) -> QVBoxLayout:
        values = QVBoxLayout()
        values.setSpacing(4)

        for label_text, value in [
            ("左侧值", self._result.left_value),
            ("右侧值", self._result.right_value),
            ("差额", self._result.diff),
        ]:
            row = QHBoxLayout()
            lbl = QLabel(f"{label_text}:")
            lbl.setStyleSheet("color: #6b7280; font-size: 12px;")
            row.addWidget(lbl)

            val = QLabel(f"{value:,.2f} 元")
            val.setFont(get_mono_font(10))
            val.setStyleSheet("font-weight: 600;")
            row.addWidget(val)
            row.addStretch()
            values.addLayout(row)

        return values

    def _build_formula(self) -> QLabel:
        formula = QLabel(f"公式: {self._result.formula}")
        formula.setStyleSheet(
            "color: #6b7280; font-size: 12px; "
            "font-family: 'JetBrains Mono', 'Consolas', monospace; "
            "background-color: #f8f9fa; border: 1px solid #e5e7eb; "
            "border-radius: 4px; padding: 8px 12px;"
        )
        return formula
