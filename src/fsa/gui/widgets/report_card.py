"""报表卡片组件: 展示单张已导入报表的摘要信息。

匹配 Demo v4 设计: icon + 报表名称 + 已导入状态 badge + 元信息。
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
)
from qfluentwidgets import FluentIcon

from fsa.core.models.report import Report, ReportType

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
        icon = _REPORT_META.get(
            self._report.report_type, (FluentIcon.DOCUMENT, "")
        )[0]
        icon_label = QLabel()
        icon_label.setPixmap(icon.icon().pixmap(16, 16))
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_layout.addWidget(icon_label)

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

        period_icon = QLabel()
        period_icon.setPixmap(FluentIcon.CALENDAR.icon().pixmap(14, 14))
        meta1.addWidget(period_icon)

        period = QLabel(self._report.period or "--")
        period.setObjectName("MetaLabel")
        meta1.addWidget(period)

        items_icon = QLabel()
        items_icon.setPixmap(FluentIcon.LAYOUT.icon().pixmap(14, 14))
        meta1.addWidget(items_icon)

        items = QLabel(f"{len(self._report.items)} 项")
        items.setObjectName("MetaLabel")
        meta1.addWidget(items)

        meta1.addStretch()
        layout.addLayout(meta1)

        # 元信息行 2: 来源文件名
        meta2 = QHBoxLayout()
        meta2.setSpacing(4)

        file_icon = QLabel()
        file_icon.setPixmap(FluentIcon.DOCUMENT.icon().pixmap(14, 14))
        meta2.addWidget(file_icon)

        source = Path(self._report.source_file).name
        file_label = QLabel(source or "--")
        file_label.setObjectName("MetaLabel")
        meta2.addWidget(file_label)

        meta2.addStretch()
        layout.addLayout(meta2)
