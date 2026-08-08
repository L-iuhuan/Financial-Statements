"""审计底稿页面: 表格形式展示全部校验结果。

匹配 Demo v4 设计: 审计表格 + 导出按钮。
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import InfoBar, InfoBarPosition

from fsa.gui.app_state import AppState


class AuditPage(QWidget):
    """审计底稿页面: 以表格展示校验结果。"""

    def __init__(self, state: AppState) -> None:
        super().__init__()
        self.setObjectName("AuditPage")
        self._state = state
        self._setup_ui()
        self._connect_signals()
        self._update_table()

    def _setup_ui(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 24, 24, 24)

        # 标题行
        title_row = QHBoxLayout()
        title = QLabel("审计底稿预览")
        title.setStyleSheet("font-size: 15px; font-weight: 600;")
        title_row.addWidget(title)
        title_row.addStretch()

        export_btn = QPushButton("导出 Excel")
        export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        export_btn.setStyleSheet(
            "QPushButton { background-color: #ffffff; color: #111827; "
            "border: 1px solid #e5e7eb; border-radius: 6px; "
            "padding: 8px 16px; font-size: 13px; font-weight: 500; }"
            "QPushButton:hover { background-color: #f3f4f6; }"
        )
        export_btn.clicked.connect(self._on_export)
        title_row.addWidget(export_btn)
        layout.addLayout(title_row)

        # 表格
        self._table = QTableWidget()
        self._table.setColumnCount(7)
        self._table.setHorizontalHeaderLabels([
            "规则 ID", "规则名称", "分类", "涉及报表",
            "校验结果", "差额 (元)", "容差",
        ])
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.setStyleSheet(
            "QTableWidget { background-color: #ffffff; "
            "border: 1px solid #e5e7eb; border-radius: 8px; }"
            "QHeaderView::section { background-color: #f3f4f6; "
            "color: #6b7280; font-weight: 600; font-size: 12px; "
            "padding: 8px 12px; border: none; "
            "border-bottom: 1px solid #e5e7eb; }"
            "QTableWidget::item { padding: 8px 12px; "
            "border-bottom: 1px solid #e5e7eb; }"
        )
        layout.addWidget(self._table)

        # 空状态
        self._empty = QLabel("暂无校验结果，请先在「数据导入」页面执行校验")
        self._empty.setStyleSheet(
            "font-size: 14px; color: #9ca3af; text-align: center; "
            "padding: 48px;"
        )
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setVisible(True)
        layout.addWidget(self._empty)

        layout.addStretch()
        scroll.setWidget(content)

        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.addWidget(scroll)

    def _connect_signals(self) -> None:
        self._state.results_changed.connect(self._update_table)

    def _update_table(self) -> None:
        summary = self._state.results
        if summary is None:
            self._table.setRowCount(0)
            self._empty.setVisible(True)
            return

        self._empty.setVisible(False)
        results = summary.results
        self._table.setRowCount(len(results))

        for i, result in enumerate(results):
            self._table.setItem(i, 0, QTableWidgetItem(result.rule_id))
            self._table.setItem(i, 1, QTableWidgetItem(result.rule_name))

            cat = result.rule_id.split("-")[0] if "-" in result.rule_id else ""
            cat_name = {
                "BS": "表内平衡", "IS": "表内平衡", "CF": "表内平衡",
                "SCE": "表间勾稽", "NOTES": "表间勾稽",
                "LR": "逻辑合理性",
            }.get(cat, "")
            self._table.setItem(i, 2, QTableWidgetItem(cat_name))

            # 从规则 ID 推断涉及的报表
            stmt_map = {
                "BS": "资产负债表", "IS": "利润表", "CF": "现金流量表",
                "SCE": "所有者权益变动表", "NOTES": "附注",
                "LR": "多表",
            }
            self._table.setItem(i, 3, QTableWidgetItem(stmt_map.get(cat, "")))

            if result.errored:
                status_text = "⚠ 异常"
            elif result.passed:
                status_text = "✓ 通过"
            else:
                status_text = "✗ 不通过"

            self._table.setItem(i, 4, QTableWidgetItem(status_text))

            diff_item = QTableWidgetItem(f"{result.diff:,.2f}")
            diff_item.setTextAlignment(Qt.AlignmentFlag.AlignRight)
            self._table.setItem(i, 5, diff_item)

            self._table.setItem(i, 6, QTableWidgetItem(str(result.tolerance)))

    def _on_export(self) -> None:
        summary = self._state.results
        if summary is None:
            InfoBar.warning(
                "提示", "请先执行校验，再导出底稿",
                orient=Qt.Orientation.Horizontal, isClosable=True,
                position=InfoBarPosition.TOP, duration=3000, parent=self,
            )
            return
        InfoBar.info(
            "导出功能", "Excel 导出功能正在开发中",
            orient=Qt.Orientation.Horizontal, isClosable=True,
            position=InfoBarPosition.TOP, duration=3000, parent=self,
        )
