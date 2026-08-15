"""校验结果卡片组件 (Demo v4 浅色填充版)。

改版: 左边框 -> 浅色背景填充 + 呼吸感 hover + 点击展开详情。
"""

from __future__ import annotations

from typing import cast

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from fsa.core.models.result import ValidationResult
from fsa.gui.theme import (
    bind_theme_listener,
    current_palette,
    get_mono_font,
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
        self._detail_built = False
        self._status = self._get_status_key()
        self.setObjectName("ResultCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._setup_ui()
        # 注册主题监听并在控件销毁时注销, 防止死监听器累积泄漏
        bind_theme_listener(self, self._on_theme_changed)

    def toggle_expanded(self) -> None:
        """展开或收起详情区域 (详情内容在首次展开时懒加载)。"""
        self._expanded = not self._expanded
        if self._expanded and not self._detail_built:
            self._ensure_detail_built()
        self._detail.setVisible(self._expanded)

    def update_result(self, result: ValidationResult) -> None:
        """用新校验结果更新卡片所有展示字段 (复用卡片对象, 不销毁重建)。

        刷新: 状态文本/样式、差额行、详情(数值/公式/trace/消息)、展开状态、
        诊断/辩论按钮可见性。信号连接保持不变。
        """
        self._result = result
        self._status = self._get_status_key()
        self._apply_card_style()
        self._apply_status_style()

        # 更新头部状态标签
        self._status_label.setText(_STATUS_TEXT[self._status])
        self._status_label.setProperty("status", self._status)

        # 更新差额行 (通过/不通过之间切换显隐)
        diff_visible = not result.passed
        self._diff_row_widget.setVisible(diff_visible)
        self._diff_label.setText(f"差额: {result.diff:,.2f}")
        self._diff_label.setProperty("status", self._status)
        self._tol_label.setText(f"  ·  容差: {result.tolerance}")

        # 更新诊断/辩论按钮行显隐
        self._diagnose_row_widget.setVisible(not result.passed)

        # 重置展开状态: 不通过默认展开, 通过默认收起。
        # 旧详情内容先释放; 展开时按新结果懒加载, 避免通过卡片也持有 trace 表格等重控件
        self._expanded = not result.passed
        if self._detail_built:
            self._clear_detail_contents()
        if self._expanded:
            self._ensure_detail_built()
        self._detail.setVisible(self._expanded)

    def _apply_status_style(self) -> None:
        """刷新状态标签和差额标签的内联样式 (主题切换时复用)。"""
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

    def _clear_detail_contents(self) -> None:
        """清空详情区域的所有子控件 (隐藏详情时不保留 trace 表格等重控件)。"""
        layout = cast(QVBoxLayout, self._detail.layout())
        if layout is None:
            return
        while layout.count():
            item = layout.takeAt(0)
            if item is None:
                continue
            w = item.widget()
            if w is not None:
                w.hide()
                w.deleteLater()
            sub = item.layout()
            if sub is not None:
                self._clear_layout(sub)
        self._detail_built = False

    def _ensure_detail_built(self) -> None:
        """首次展开时构建详情内容 (数值网格、公式、trace 表格、消息)。"""
        if self._detail_built:
            return
        layout = cast(QVBoxLayout, self._detail.layout())
        if layout is None:
            return

        # 数值网格
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

        # 公式块
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
        else:
            empty = QLabel("— 无科目追溯 —")
            empty.setObjectName("MetaLabel")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(empty)

        # 消息
        if self._result.message and not self._result.passed:
            msg = QLabel(self._result.message)
            msg.setWordWrap(True)
            msg.setObjectName("ResultMessage")
            layout.addWidget(msg)

        self._detail_built = True

    @staticmethod
    def _clear_layout(sub_layout: QLayout) -> None:
        """递归清除布局中的所有子项。"""
        while sub_layout.count():
            item = sub_layout.takeAt(0)
            if item is None:
                continue
            w = item.widget()
            if w is not None:
                w.hide()
                w.deleteLater()

    def _get_status_key(self) -> str:
        if self._result.errored:
            return "error"
        return "pass" if self._result.passed else "fail"

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

        # 差额行: 始终创建, 通过时隐藏
        self._diff_row_widget = QWidget()
        self._diff_row_widget.setLayout(self._build_diff_line())
        self._diff_row_widget.setVisible(not self._result.passed)
        layout.addWidget(self._diff_row_widget)

        self._detail = self._build_detail()
        self._detail.setVisible(self._expanded)
        layout.addWidget(self._detail)
        if self._expanded:
            self._ensure_detail_built()

        # 诊断按钮行: 始终创建, 通过时隐藏
        self._diagnose_row_widget = QWidget()
        self._diagnose_row_widget.setLayout(self._build_diagnose_button())
        self._diagnose_row_widget.setVisible(not self._result.passed)
        layout.addWidget(self._diagnose_row_widget)

    def _build_header(self) -> QHBoxLayout:
        header = QHBoxLayout()
        header.setSpacing(8)
        id_label = QLabel(self._result.rule_id)
        id_label.setObjectName("ResultIdLabel")
        header.addWidget(id_label)
        name_label = QLabel(self._result.rule_name)
        name_label.setObjectName("RuleName")
        name_label.setWordWrap(False)
        header.addWidget(name_label, stretch=1)
        if self._result.category:
            cat = QLabel(self._result.category)
            cat.setObjectName("MetaLabel")
            header.addWidget(cat)
        self._status_label = QLabel(_STATUS_TEXT[self._status])
        self._status_label.setObjectName("ResultStatusLabel")
        self._status_label.setProperty("status", self._status)
        self._status_label.setStyleSheet("")
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
        self._diff_label.setStyleSheet("")
        row.addWidget(self._diff_label)
        tol_label = QLabel(f"  ·  容差: {self._result.tolerance}")
        tol_label.setObjectName("ResultTolerance")
        self._tol_label = tol_label
        row.addWidget(tol_label)
        row.addStretch()
        return row

    def _build_detail(self) -> QWidget:
        """创建空详情容器；具体内容在首次展开时由 _ensure_detail_built 懒加载。"""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)
        return container

    def _build_trace_table(self) -> QTableWidget:
        table = QTableWidget(len(self._result.trace), 4)
        table.setObjectName("TraceTable")
        table.setHorizontalHeaderLabels(["科目", "金额", "侧", "位置"])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        table.setAlternatingRowColors(True)
        table.horizontalHeader().setStretchLastSection(True)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        table.setFixedHeight(180)
        for i, t in enumerate(self._result.trace):
            table.setItem(i, 0, QTableWidgetItem(t.name))
            amt = QTableWidgetItem(f"{t.amount:,.2f}")
            amt.setTextAlignment(Qt.AlignmentFlag.AlignRight)
            amt.setFont(get_mono_font(10))
            table.setItem(i, 1, amt)
            side_text = "左" if t.side == "left" else "右" if t.side == "right" else t.side
            table.setItem(i, 2, QTableWidgetItem(side_text))
            pos = self._format_trace_pos(t.row, t.column)
            table.setItem(i, 3, QTableWidgetItem(pos))
        table.resizeColumnsToContents()
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

    @staticmethod
    def _format_trace_pos(row: int, column: str) -> str:
        """格式化追溯位置，PDF 来源解码为「第X页表内第N行」。"""
        _PDF_ROW_BASE = 10_000_000
        if row <= 0:
            return column
        if row >= _PDF_ROW_BASE:
            page, table_row = divmod(row, _PDF_ROW_BASE)
            return f"第{page}页表内第{table_row}行"
        return f"行{row} · {column}"

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

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            widget = self.childAt(event.position().toPoint())
            if not isinstance(widget, QPushButton):
                self.toggle_expanded()
        super().mousePressEvent(event)
