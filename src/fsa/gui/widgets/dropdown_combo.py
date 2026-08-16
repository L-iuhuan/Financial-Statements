"""下拉选择控件 (DropdownCombo): QComboBox 的轻量替代。

背景: QComboBox 的 ::drop-down/::down-arrow 子控件 QSS 在部分
Windows 环境完全不渲染 (箭头缺失/按钮区无区分), 多次纯 QSS 修复无效。
本控件用 QPushButton (文字) + ArrowButton 自绘箭头 + QMenu 弹出列表
重新实现, 三者均为已验证可正常渲染的普通控件路径。

对调用方暴露 QComboBox 的常用子集 API (settings_sections 所需):
addItem / findData / setCurrentIndex / currentIndex / currentData /
currentIndexChanged 信号。
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QHBoxLayout, QMenu, QWidget

from fsa.gui.widgets.arrow_button import ArrowButton


class DropdownCombo(QWidget):
    """按钮 + 弹出菜单的下拉选择控件。"""

    currentIndexChanged = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._items: list[tuple[str, object]] = []
        self._current = -1
        self._button = ArrowButton()
        self._button.setObjectName("DropdownButton")
        self._button.clicked.connect(self._show_menu)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._button)

    def addItem(self, text: str, userData: object | None = None) -> None:
        """追加一项; 首个选项默认选中。"""
        self._items.append((text, userData))
        if self._current < 0:
            self.setCurrentIndex(0)

    def findData(self, data: object) -> int:
        """按用户数据查找索引, 不存在返回 -1。"""
        for index, (_, item_data) in enumerate(self._items):
            if item_data == data:
                return index
        return -1

    def setCurrentIndex(self, index: int) -> None:
        """设置当前项 (不发射信号, 与构造期回填场景匹配)。"""
        if index < 0 or index >= len(self._items):
            return
        if index != self._current:
            self._current = index
            self._button.setText(self._items[index][0])

    def currentIndex(self) -> int:
        """当前索引。"""
        return self._current

    def currentData(self) -> object:
        """当前项的用户数据; 无选项时返回 None。"""
        if 0 <= self._current < len(self._items):
            return self._items[self._current][1]
        return None

    def _show_menu(self) -> None:
        """弹出选项菜单 (QMenu 走全局 QSS, 已验证可正常渲染)。"""
        menu = QMenu(self._button)
        for index, (text, _) in enumerate(self._items):
            action: QAction = menu.addAction(text)
            action.setCheckable(True)
            action.setChecked(index == self._current)
            action.triggered.connect(
                lambda checked=False, idx=index: self._select(idx)
            )
        pos = self._button.mapToGlobal(QPoint(0, self._button.height()))
        menu.exec(pos)

    def _select(self, index: int) -> None:
        """菜单选择: 更新当前项并通知外部。"""
        if index != self._current:
            self._current = index
            self._button.setText(self._items[index][0])
            self.currentIndexChanged.emit(index)
