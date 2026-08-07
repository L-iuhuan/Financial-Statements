"""规则管理页面: 查看、启用/禁用勾稽校验规则。"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import SwitchButton

from fsa.gui.app_state import AppState


class RulePage(QWidget):
    """规则管理页面: 以表格展示所有规则, 支持启用/禁用。"""

    def __init__(self, state: AppState) -> None:
        super().__init__()
        self.setObjectName("RulePage")
        self._state = state
        self._setup_ui()
        self._load_rules()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("规则管理")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        layout.addWidget(title)

        self._summary = QLabel("加载中...")
        self._summary.setStyleSheet("color: #64748b;")
        layout.addWidget(self._summary)

        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(
            ["规则编号", "规则名称", "分类", "严重级别", "启用"]
        )
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self._table)

    def _load_rules(self) -> None:
        registry = self._state.registry
        if registry is None:
            self._summary.setText("规则库未加载")
            return

        rules = registry.get_all()
        active_ids = {r.rule_id for r in registry.get_active()}
        self._summary.setText(
            f"共 {len(rules)} 条规则 (启用 {len(active_ids)} 条)"
        )

        self._table.setRowCount(len(rules))
        for i, rule in enumerate(rules):
            self._table.setItem(i, 0, QTableWidgetItem(rule.rule_id))
            self._table.setItem(i, 1, QTableWidgetItem(rule.name))
            self._table.setItem(i, 2, QTableWidgetItem(rule.category))
            self._table.setItem(i, 3, QTableWidgetItem(rule.severity.value))

            switch = SwitchButton()
            switch.setChecked(rule.rule_id in active_ids)
            switch.checkedChanged.connect(
                lambda checked, rid=rule.rule_id: self._on_toggle(rid, checked)
            )
            self._table.setCellWidget(i, 4, switch)

    def _on_toggle(self, rule_id: str, checked: bool) -> None:
        registry = self._state.registry
        if registry is None:
            return
        if checked:
            registry.enable(rule_id)
        else:
            registry.disable(rule_id)
        active = len(registry.get_active())
        total = registry.count()
        self._summary.setText(f"共 {total} 条规则 (启用 {active} 条)")
