"""报告期间选择器 (PeriodPicker): QDateEdit 日历下拉的替代实现。

背景: QDateEdit 的下拉按钮/箭头依赖 QSS 子控件渲染, 在部分 Windows
环境不可靠。本控件用 QLineEdit (可手输 yyyy-MM) + ArrowButton (自绘
箭头) + QCalendarWidget 弹出日历重新实现, 全部为已验证的普通控件路径。
"""

from __future__ import annotations

from PySide6.QtCore import QDate, QPoint, Qt, Signal
from PySide6.QtWidgets import (
    QCalendarWidget,
    QDialog,
    QHBoxLayout,
    QLineEdit,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from fsa.gui.widgets.arrow_button import ArrowButton


class PeriodPicker(QWidget):
    """报告期间选择器: 文本框 + 日历下拉按钮。"""

    dateChanged = Signal(QDate)

    def __init__(self, date: QDate, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._date = date
        self._line = QLineEdit(date.toString("yyyy-MM"))
        self._line.setObjectName("PeriodInput")
        self._line.editingFinished.connect(self._on_edit_finished)
        self._btn = ArrowButton()
        self._btn.setObjectName("PeriodArrowBtn")
        self._btn.setFixedWidth(28)
        # 竖直 Ignored: 忽略按钮自身 sizeHint, 由布局按输入框高度分配,
        # 保证箭头按钮与输入框同高 (默认 Fixed 保持自身高度, 两者不一致)
        self._btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Ignored)
        self._btn.setToolTip("打开日历选择月份")
        self._btn.clicked.connect(self._show_calendar)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._line, stretch=1)
        layout.addWidget(self._btn)

    def date(self) -> QDate:
        """当前日期。"""
        return self._date

    def setDate(self, date: QDate) -> None:
        """设置日期 (与 QDateEdit 一致: 变化时发射 dateChanged;

        历史回看等回填场景由调用方 blockSignals 屏蔽)。
        """
        if date == self._date:
            return
        self._date = date
        self._line.setText(date.toString("yyyy-MM"))
        self.dateChanged.emit(date)

    def _on_edit_finished(self) -> None:
        """手输完成: 解析 yyyy-MM, 非法时回退当前日期。"""
        text = self._line.text().strip()
        parsed = QDate.fromString(text, "yyyy-MM")
        if not parsed.isValid():
            parsed = self._date
            self._line.setText(parsed.toString("yyyy-MM"))
        if parsed != self._date:
            self._date = parsed
            self.dateChanged.emit(parsed)

    def _show_calendar(self) -> None:
        """弹出日历 (Qt.Popup: 点击外部自动关闭)。"""
        popup = QDialog(self, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        layout = QVBoxLayout(popup)
        layout.setContentsMargins(8, 8, 8, 8)
        calendar = QCalendarWidget(popup)
        calendar.setSelectedDate(self._date)
        calendar.setFirstDayOfWeek(Qt.DayOfWeek.Monday)
        layout.addWidget(calendar)

        def _on_picked(picked: QDate) -> None:
            self._date = picked
            self._line.setText(picked.toString("yyyy-MM"))
            self.dateChanged.emit(picked)
            popup.accept()

        calendar.clicked.connect(_on_picked)
        popup.adjustSize()
        pos = self._btn.mapToGlobal(QPoint(0, self._btn.height() + 4))
        popup.move(pos)
        popup.exec()
