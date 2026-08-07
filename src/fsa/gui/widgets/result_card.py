"""校验结果卡片组件。

每张卡片显示一条 ValidationResult, 带有颜色编码的左侧边框:
- 绿色: 通过
- 红色: 不通过
- 琥珀色: 异常 (无法执行校验)
"""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout
from qfluentwidgets import CardWidget

from fsa.core.models.result import ValidationResult
from fsa.gui.theme import get_mono_font

_BORDER_STYLE: dict[str, str] = {
    "pass": "border-left: 4px solid #10b981; background-color: #f0fdf4; border-radius: 8px;",
    "fail": "border-left: 4px solid #ef4444; background-color: #fef2f2; border-radius: 8px;",
    "error": "border-left: 4px solid #f59e0b; background-color: #fffbeb; border-radius: 8px;",
}

_STATUS_ICON: dict[str, str] = {"pass": "✓", "fail": "✗", "error": "⚠"}
_STATUS_TEXT: dict[str, str] = {"pass": "通过", "fail": "不通过", "error": "异常"}
_STATUS_COLOR: dict[str, str] = {
    "pass": "#10b981",
    "fail": "#ef4444",
    "error": "#f59e0b",
}


class ResultCard(CardWidget):
    """单条校验结果卡片。"""

    def __init__(self, result: ValidationResult) -> None:
        super().__init__()
        self._result = result
        self._setup_ui()

    def _setup_ui(self) -> None:
        status = self._get_status_key()
        self.setStyleSheet(_BORDER_STYLE[status])

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        layout.addLayout(self._build_header(status))
        layout.addLayout(self._build_values())
        layout.addWidget(self._build_formula())

        if not self._result.passed:
            msg = QLabel(self._result.message)
            msg.setWordWrap(True)
            msg.setStyleSheet("color: #64748b; font-size: 12px;")
            layout.addWidget(msg)

    def _get_status_key(self) -> str:
        if self._result.errored:
            return "error"
        return "pass" if self._result.passed else "fail"

    def _build_header(self, status: str) -> QHBoxLayout:
        header = QHBoxLayout()

        id_label = QLabel(self._result.rule_id)
        id_label.setStyleSheet(
            "background-color: #eef2ff; color: #4f46e5; "
            "padding: 2px 8px; border-radius: 4px; font-weight: bold;"
        )
        header.addWidget(id_label)

        name_label = QLabel(self._result.rule_name)
        name_label.setStyleSheet("font-size: 14px; font-weight: 500;")
        header.addWidget(name_label, stretch=1)

        status_label = QLabel(f"{_STATUS_ICON[status]} {_STATUS_TEXT[status]}")
        status_label.setStyleSheet(
            f"color: {_STATUS_COLOR[status]}; font-weight: bold; font-size: 14px;"
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
            lbl = QLabel(f"{label_text}: {value:,.2f} 元")
            lbl.setFont(get_mono_font())
            values.addWidget(lbl)

        return values

    def _build_formula(self) -> QLabel:
        formula = QLabel(f"公式: {self._result.formula}")
        formula.setStyleSheet("color: #64748b; font-size: 12px;")
        return formula
