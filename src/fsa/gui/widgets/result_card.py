"""校验结果卡片组件 (Demo v4 浅色填充版)。

改版: 左边框 -> 浅色背景填充 + 呼吸感 hover + 点击展开详情。
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from fsa.core.models.result import ValidationResult
from fsa.gui.theme import (
    current_palette,
    get_mono_font,
    register_theme_listener,
)

_STATUS_TEXT: dict[str, str] = {"pass": "通过", "fail": "不通过", "error": "异常"}
# 状态到 palette 键的映射
_STATUS_PALETTE: dict[str, str] = {"pass": "success", "fail": "error", "error": "warning"}


class ResultCard(QFrame):
    """单条校验结果卡片 (浅色填充 + 呼吸感 + 可展开)。

    - 浅色背景填充替代左边框
    - hover 时阴影加深 (呼吸感)
    - 点击卡片展开/收起详情 (公式 + 左右值 + 差额 + 容差 + trace)
    """

    diagnose_clicked = Signal(str)  # rule_id
    debate_clicked = Signal(str)  # rule_id -> 深度辩论

    def __init__(self, result: ValidationResult) -> None:
        super().__init__()
        self._result = result
        self._expanded = not result.passed
        self._status = self._get_status_key()
        self.setObjectName("ResultCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._setup_shadow()
        self._setup_ui()
        register_theme_listener(self._on_theme_changed)

    def toggle_expanded(self) -> None:
        """展开或收起详情区域。"""
        self._expanded = not self._expanded
        self._detail.setVisible(self._expanded)

    def _get_status_key(self) -> str:
        if self._result.errored:
            return "error"
        return "pass" if self._result.passed else "fail"

    def _setup_shadow(self) -> None:
        self._shadow = QGraphicsDropShadowEffect()
        self._shadow.setBlurRadius(6)
        self._shadow.setColor(QColor(0, 0, 0, 10))
        self._shadow.setOffset(0, 1)
        self.setGraphicsEffect(self._shadow)

    def _apply_card_style(self) -> None:
        p = current_palette()
        status = self._status
        pal_key = _STATUS_PALETTE[status]
        bg = p[f"{pal_key}_bg"]
        border_color = p[f"{pal_key}_border"]
        accent = p[pal_key]
        self.setStyleSheet(
            f"""
            QFrame#ResultCard {{
                background-color: {bg};
                border: 1px solid {border_color};
                border-radius: 8px;
            }}
            QFrame#ResultCard:hover {{
                border: 1px solid {accent};
            }}
            """
        )

    def _setup_ui(self) -> None:
        self._apply_card_style()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)
        layout.addLayout(self._build_header())
        if not self._result.passed:
            layout.addLayout(self._build_diff_line())
        self._detail = self._build_detail()
        self._detail.setVisible(self._expanded)
        layout.addWidget(self._detail)
        if not self._result.passed:
            layout.addLayout(self._build_diagnose_button())

    def _build_header(self) -> QHBoxLayout:
        header = QHBoxLayout()
        header.setSpacing(8)
        id_label = QLabel(self._result.rule_id)
        id_label.setObjectName("ResultIdLabel")
        header.addWidget(id_label)
        name_label = QLabel(self._result.rule_name)
        name_label.setStyleSheet("font-size: 14px; font-weight: 600;")
        name_label.setWordWrap(False)
        header.addWidget(name_label, stretch=1)
        if self._result.category:
            cat = QLabel(self._result.category)
            cat.setObjectName("MetaLabel")
            header.addWidget(cat)
        self._status_label = QLabel(_STATUS_TEXT[self._status])
        self._status_label.setObjectName("ResultStatusLabel")
        self._status_label.setProperty("status", self._status)
        self._status_label.setStyleSheet("font-weight: 500; font-size: 13px;")
        header.addWidget(self._status_label)
        return header

    def _build_diff_line(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(4)
        diff_text = f"差额: {self._result.diff:,.2f}"
        self._diff_label = QLabel(diff_text)
        self._diff_label.setFont(get_mono_font(11))
        self._diff_label.setObjectName("ResultDiffLabel")
        self._diff_label.setProperty("status", self._status)
        self._diff_label.setStyleSheet("font-size: 12px; font-weight: 600;")
        row.addWidget(self._diff_label)
        tol_label = QLabel(f"  ·  容差: {self._result.tolerance}")
        tol_label.setObjectName("ResultTolerance")
        row.addWidget(tol_label)
        row.addStretch()
        return row

    def _build_detail(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)
        # 数值网格 (2x2)
        grid = QGridLayout()
        grid.setSpacing(4)
        items = [
            ("左侧计算值", self._result.left_value),
            ("右侧计算值", self._result.right_value),
            ("差额", self._result.diff),
            ("容差阈值", self._result.tolerance),
        ]
        for row_idx, (label_text, value) in enumerate(items):
            r, c = divmod(row_idx, 2)
            lbl = QLabel(label_text)
            lbl.setObjectName("ResultGridLabel")
            grid.addWidget(lbl, r, c * 2)
            val = QLabel(f"{value:,.2f}")
            val.setFont(get_mono_font(11))
            val.setObjectName("ResultGridValue")
            grid.addWidget(val, r, c * 2 + 1)
        layout.addLayout(grid)
        # 公式块 (中文显示, 英文原版见 tooltip)
        from fsa.gui.formula_display import formula_to_chinese
        formula = QLabel(f"  {formula_to_chinese(self._result.formula)}")
        formula.setFont(get_mono_font(10))
        formula.setObjectName("ResultFormula")
        formula.setWordWrap(True)
        formula.setToolTip(f"英文公式: {self._result.formula}")
        layout.addWidget(formula)
        # trace 表格
        if self._result.trace:
            layout.addWidget(self._build_trace_table())
        # 消息
        if self._result.message and not self._result.passed:
            msg = QLabel(self._result.message)
            msg.setWordWrap(True)
            msg.setObjectName("ResultMessage")
            layout.addWidget(msg)
        return container

    def _build_trace_table(self) -> QTableWidget:
        table = QTableWidget(len(self._result.trace), 4)
        table.setObjectName("TraceTable")
        table.setHorizontalHeaderLabels(["科目", "金额", "侧", "位置"])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        table.horizontalHeader().setStretchLastSection(True)
        for i, t in enumerate(self._result.trace):
            table.setItem(i, 0, QTableWidgetItem(t.name))
            amt = QTableWidgetItem(f"{t.amount:,.2f}")
            amt.setTextAlignment(Qt.AlignmentFlag.AlignRight)
            amt.setFont(get_mono_font(10))
            table.setItem(i, 1, amt)
            side_text = "左" if t.side == "left" else "右" if t.side == "right" else t.side
            table.setItem(i, 2, QTableWidgetItem(side_text))
            pos = f"行{t.row} · {t.column}" if t.row > 0 else t.column
            table.setItem(i, 3, QTableWidgetItem(pos))
        table.resizeColumnsToContents()
        table.setMaximumHeight(table.horizontalHeader().height() + table.rowCount() * 36 + 4)
        return table

    def _build_diagnose_button(self) -> QHBoxLayout:
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        # 深度辩论按钮 (多模型对抗分析, 用于疑难差异)
        debate_btn = QPushButton("深度辩论")
        debate_btn.setMinimumSize(80, 26)
        debate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        debate_btn.setObjectName("DebateBtn")
        debate_btn.setToolTip("多模型辩论: 分析师/反方/裁判三方对抗, 深度分析差异根因")
        debate_btn.clicked.connect(
            lambda: self.debate_clicked.emit(self._result.rule_id)
        )
        btn_row.addWidget(debate_btn)

        diagnose_btn = QPushButton("AI 诊断")
        diagnose_btn.setMinimumSize(72, 26)
        diagnose_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        diagnose_btn.setObjectName("DiagnoseBtn")
        diagnose_btn.clicked.connect(
            lambda: self.diagnose_clicked.emit(self._result.rule_id)
        )
        btn_row.addWidget(diagnose_btn)
        return btn_row

    def _on_theme_changed(self) -> None:
        self._apply_card_style()
        p = current_palette()
        accent = p[_STATUS_PALETTE[self._status]]
        if hasattr(self, "_status_label"):
            self._status_label.setStyleSheet(
                f"color: {accent}; font-weight: 500; font-size: 13px;"
            )
        if hasattr(self, "_diff_label"):
            self._diff_label.setStyleSheet(
                f"color: {accent}; font-size: 12px; font-weight: 600;"
            )

    def enterEvent(self, event) -> None:  # type: ignore[override]
        self._shadow.setBlurRadius(12)
        self._shadow.setColor(QColor(0, 0, 0, 25))
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # type: ignore[override]
        self._shadow.setBlurRadius(6)
        self._shadow.setColor(QColor(0, 0, 0, 10))
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            widget = self.childAt(event.position().toPoint())
            if not isinstance(widget, QPushButton):
                self.toggle_expanded()
        super().mousePressEvent(event)
