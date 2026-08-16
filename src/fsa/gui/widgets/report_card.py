"""报表卡片组件: 展示单张已导入报表的摘要信息。

匹配 Demo v4 设计: icon + 报表名称 + 已导入状态 badge + 元信息。
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import FluentIcon, IconWidget

from fsa.core.models.report import Report, ReportType
from fsa.gui.theme import current_palette, get_mono_font

# 报表类型到图标和简短名称的映射
_REPORT_META: dict[ReportType, tuple[FluentIcon, str]] = {
    ReportType.BALANCE_SHEET: (FluentIcon.DOCUMENT, "BS"),
    ReportType.INCOME_STATEMENT: (FluentIcon.UP, "IS"),
    ReportType.CASH_FLOW_STATEMENT: (FluentIcon.SYNC, "CF"),
    ReportType.STATEMENT_OF_CHANGES_IN_EQUITY: (FluentIcon.PEOPLE, "SCE"),
    ReportType.NOTES: (FluentIcon.BOOK_SHELF, "NOTES"),
}


class ReportCard(QFrame):
    """单张已导入报表的卡片。

    包含: 图标、报表名称、状态 badge、期间、项目数、来源文件名。
    """

    def __init__(self, report: Report) -> None:
        super().__init__()
        self._report = report
        self.setObjectName("ReportCard")
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        # 标题行: 图标 + 名称 + 状态
        header = QHBoxLayout()
        header.setSpacing(8)

        icon_frame = QFrame()
        icon_frame.setObjectName("ReportCardIcon")
        icon_frame.setFixedSize(32, 32)
        icon_layout = QHBoxLayout(icon_frame)
        icon_layout.setContentsMargins(0, 0, 0, 0)

        # 注: 不用元组解包 (icon, _) — mypy 2.3.0 对 .get() 元组默认值
        # 的解包路径有内部崩溃 (check_multi_assignment_from_tuple)
        icon = _REPORT_META.get(self._report.report_type, (FluentIcon.DOCUMENT, ""))[0]
        # IconWidget: 主题同步图标 (QLabel+pixmap 会在构造时烘焙颜色, 切主题后不刷新)
        icon_widget = IconWidget(icon)
        icon_widget.setFixedSize(16, 16)
        icon_layout.addWidget(icon_widget)

        header.addWidget(icon_frame)

        name = QLabel(self._report.report_type.value)
        name.setObjectName("RuleName")
        header.addWidget(name, stretch=1)

        status = QLabel("已导入")
        status.setObjectName("ReportCardStatus")
        header.addWidget(status)

        layout.addLayout(header)

        # 元信息行 1: 期间 + 项目数
        meta1 = QHBoxLayout()
        meta1.setSpacing(12)

        period_icon = IconWidget(FluentIcon.CALENDAR)
        period_icon.setFixedSize(14, 14)
        meta1.addWidget(period_icon)

        period = QLabel(self._report.period or "--")
        period.setObjectName("MetaLabel")
        meta1.addWidget(period)

        items_icon = IconWidget(FluentIcon.LAYOUT)
        items_icon.setFixedSize(14, 14)
        meta1.addWidget(items_icon)

        items = QLabel(f"{len(self._report.items)} 项 · 单位 {self._report.amount_unit}")
        items.setObjectName("MetaLabel")
        if self._report.unit_warning:
            items.setToolTip(self._report.unit_warning)
        meta1.addWidget(items)

        meta1.addStretch()
        layout.addLayout(meta1)

        # 元信息行 2: 来源文件名
        meta2 = QHBoxLayout()
        meta2.setSpacing(4)

        file_icon = IconWidget(FluentIcon.DOCUMENT)
        file_icon.setFixedSize(14, 14)
        meta2.addWidget(file_icon)

        source = Path(self._report.source_file).name
        file_label = QLabel(source or "--")
        file_label.setObjectName("MetaLabel")
        meta2.addWidget(file_label)

        meta2.addStretch()
        layout.addLayout(meta2)

        # 未映射清单提示 (可视化)
        unmapped_count = len(self._report.unmapped_names)
        self._unmapped_label = QLabel(f"未映射 {unmapped_count} 项" if unmapped_count else "科目全部映射")
        self._unmapped_label.setObjectName("MetaLabel")
        if unmapped_count:
            self._unmapped_label.setToolTip("未映射科目: " + "、".join(self._report.unmapped_names[:10]))
        layout.addWidget(self._unmapped_label)

        # 查看已提取科目金额与原始行列
        self._detail_btn = QPushButton("查看科目清单")
        self._detail_btn.setObjectName("TextBtn")
        self._detail_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._detail_btn.setToolTip("查看已识别科目金额与原始行列, 以及未映射清单")
        self._detail_btn.clicked.connect(self._show_items_dialog)
        layout.addWidget(self._detail_btn)

    def _show_items_dialog(self) -> None:
        """打开科目清单对话框: 已识别科目与未映射清单两个标签页。"""
        dialog = QDialog(self)
        dialog.setWindowTitle(f"{self._report.report_type.value} · 科目清单")
        dialog.resize(720, 480)
        layout = QVBoxLayout(dialog)

        tabs = QTabWidget()
        tabs.addTab(self._build_identified_tab(), "已识别科目")
        tabs.addTab(self._build_unmapped_tab(), f"未映射清单 ({len(self._report.unmapped_names)})")
        layout.addWidget(tabs)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        buttons.clicked.connect(dialog.accept)
        layout.addWidget(buttons)
        dialog.exec()

    def _build_identified_tab(self) -> QWidget:
        """已识别科目表: 名称/key/金额/期初/原始行/原始列, 与 ReportItem 一一对应。"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        items = self._report.items
        table = QTableWidget(len(items), 6)
        table.setHorizontalHeaderLabels(["科目名称", "标准变量", "金额(元)", "期初金额(元)", "原始行", "原始列"])
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        p = current_palette()
        for row_idx, item in enumerate(items):
            values = [
                item.name,
                item.key,
                f"{item.amount:,.2f}",
                f"{item.beginning_amount:,.2f}" if item.beginning_amount is not None else "",
                str(item.row) if item.row > 0 else "",
                item.column or "",
            ]
            for col_idx, value in enumerate(values):
                cell = QTableWidgetItem(value)
                if col_idx in (2, 3):
                    # 金额列: 等宽字体右对齐, 负数红色呈现
                    cell.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                    cell.setFont(get_mono_font(10))
                    amount = item.amount if col_idx == 2 else item.beginning_amount
                    if amount is not None and amount < 0:
                        cell.setForeground(QColor(p["amount_negative"]))
                table.setItem(row_idx, col_idx, cell)
        table.resizeColumnsToContents()
        layout.addWidget(table)
        return widget

    def _build_unmapped_tab(self) -> QWidget:
        """未映射清单: 有金额但未能识别为标准科目的项目。"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        names = self._report.unmapped_names
        if names:
            hint = QLabel(
                f"共 {len(names)} 个项目未能映射为标准科目 (不参与校验)。通常是'其中:'明细、非标准科目或别名缺失。"
            )
            hint.setObjectName("MetaLabel")
            layout.addWidget(hint)
            table = QTableWidget(len(names), 1)
            table.setHorizontalHeaderLabels(["项目名称"])
            table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            for row_idx, name in enumerate(names):
                table.setItem(row_idx, 0, QTableWidgetItem(name))
            table.resizeColumnsToContents()
            layout.addWidget(table)
        else:
            empty = QLabel("所有有金额的项目均已映射为标准科目。")
            empty.setObjectName("MetaLabel")
            layout.addWidget(empty)
        return widget
