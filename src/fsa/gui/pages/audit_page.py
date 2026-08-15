"""审计底稿页面: 表格形式展示全部校验结果。

匹配 Demo v4 设计: 审计表格 + 导出按钮 + 打印预览。
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtPrintSupport import QPrinter, QPrintPreviewDialog
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

from fsa.core.models.rule import Severity
from fsa.gui.app_state import AppState
from fsa.gui.export_helper import export_audit_workbook
from fsa.gui.theme import current_palette, get_mono_font


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
        content.setObjectName("PageContent")
        layout = QVBoxLayout(content)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 24, 24, 24)

        # 标题行
        title_row = QHBoxLayout()
        title = QLabel("审计底稿预览")
        title.setObjectName("PageTitle")
        title_row.addWidget(title)
        title_row.addStretch()

        export_btn = QPushButton("导出 Excel")
        export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        export_btn.setObjectName("BtnSecondary")
        export_btn.clicked.connect(self._on_export)
        title_row.addWidget(export_btn)

        print_btn = QPushButton("打印预览")
        print_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        print_btn.setObjectName("BtnSecondary")
        print_btn.clicked.connect(self._on_print_preview)
        title_row.addWidget(print_btn)
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
        layout.addWidget(self._table)

        # 空状态
        self._empty = QLabel("暂无校验结果，请先在「数据导入」页面执行校验")
        self._empty.setObjectName("EmptyLabel")
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
        p = current_palette()

        for i, result in enumerate(results):
            self._table.setItem(i, 0, QTableWidgetItem(result.rule_id))
            self._table.setItem(i, 1, QTableWidgetItem(result.rule_name))

            # 使用引擎提供的真实分类
            cat_text = result.category if result.category else ""
            self._table.setItem(i, 2, QTableWidgetItem(cat_text))

            # 涉及报表 (从 registry 查找规则获取 statements)
            stmts = ""
            registry = self._state.registry
            if registry is not None:
                rule = registry.get_by_id(result.rule_id)
                if rule is not None:
                    stmts = ", ".join(rule.statements)
            self._table.setItem(i, 3, QTableWidgetItem(stmts))

            # 校验结果 + 颜色 (跳过先于通过判断: skipped=True 且 passed=True)
            if result.errored:
                status_text = "异常"
                status_color = p["warning"]
            elif result.skipped:
                status_text = "跳过"
                status_color = p["text_secondary"]
            elif result.passed:
                status_text = "通过"
                status_color = p["success"]
            else:
                if result.severity is Severity.ERROR:
                    status_text = "不通过"
                    status_color = p["error"]
                else:
                    status_text = "警告"
                    status_color = p["warning"]

            status_item = QTableWidgetItem(status_text)
            status_item.setForeground(QColor(status_color))
            self._table.setItem(i, 4, status_item)

            diff_item = QTableWidgetItem(f"{result.diff:,.2f}")
            diff_item.setTextAlignment(Qt.AlignmentFlag.AlignRight)
            diff_item.setFont(get_mono_font(10))
            self._table.setItem(i, 5, diff_item)

            tol_item = QTableWidgetItem(str(result.tolerance))
            tol_item.setFont(get_mono_font(10))
            self._table.setItem(i, 6, tol_item)

    def _on_export(self) -> None:
        """导出审计底稿 (公共逻辑见 export_helper.py)。"""
        export_audit_workbook(self, self._state.results, show_progress=False)

    def _on_print_preview(self) -> None:
        summary = self._state.results
        if summary is None:
            InfoBar.warning(
                "提示", "请先执行校验，再打印底稿",
                orient=Qt.Orientation.Horizontal, isClosable=True,
                position=InfoBarPosition.TOP, duration=3000, parent=self,
            )
            return

        dialog = QPrintPreviewDialog(self)
        dialog.paintRequested.connect(self._render_print)
        dialog.exec()

    def _render_print(self, printer: QPrinter) -> None:
        from PySide6.QtGui import QTextDocument

        summary = self._state.results
        if summary is None:
            return

        rows = []
        for result in summary.results:
            status = (
                "异常" if result.errored
                else "跳过" if result.skipped
                else "通过" if result.passed
                else "不通过" if result.severity is Severity.ERROR
                else "警告"
            )
            rows.append(
                f"<tr>"
                f"<td>{result.rule_id}</td>"
                f"<td>{result.rule_name}</td>"
                f"<td>{result.category}</td>"
                f"<td>{status}</td>"
                f"<td align='right'>{result.diff:,.2f}</td>"
                f"<td>{result.tolerance}</td>"
                f"</tr>"
            )

        html = (
            "<html><head><style>"
            "table { border-collapse: collapse; width: 100%; }"
            "th, td { border: 1px solid #ccc; padding: 6px; font-size: 12px; }"
            "th { background-color: #f3f4f6; }"
            "</style></head><body>"
            "<h2>审计底稿</h2>"
            "<table>"
            "<tr><th>规则 ID</th><th>规则名称</th><th>分类</th>"
            "<th>校验结果</th><th>差额 (元)</th><th>容差</th></tr>"
            f"{''.join(rows)}"
            "</table></body></html>"
        )

        doc = QTextDocument()
        doc.setHtml(html)
        # print 是 QTextDocument 的有效方法 (PySide6 将 C++ print 映射至此)
        doc.print_(printer)
