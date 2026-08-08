"""规则管理页面: 搜索 + 分类筛选 + 规则卡片列表。

匹配 Demo v4 设计: 搜索框 + 分类标签 + 卡片式规则列表 + 启用/禁用开关。
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import SwitchButton

from fsa.gui.app_state import AppState

# 分类标签
_CATEGORIES = ["全部", "表内平衡", "表间勾稽", "逻辑合理性"]


class RuleCard(QFrame):
    """单条规则卡片。"""

    def __init__(self, rule, is_active: bool, on_toggle) -> None:
        super().__init__()
        self._rule = rule
        self._on_toggle = on_toggle
        self._setup_ui(is_active)

    def _setup_ui(self, is_active: bool) -> None:
        self.setStyleSheet(
            """
            QFrame {
                background-color: #ffffff;
                border: 1px solid #e5e7eb;
                border-radius: 8px;
            }
            QFrame:hover {
                border-color: #d1d5db;
            }
            QFrame[disabled="true"] {
                opacity: 0.5;
            }
            """
        )
        self.setProperty("disabled", not is_active)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(16)

        # 左侧: 规则信息
        info = QVBoxLayout()
        info.setSpacing(4)

        # 标题行: badge + name
        title_row = QHBoxLayout()
        title_row.setSpacing(8)

        badge = QLabel(self._rule.rule_id)
        badge.setStyleSheet(
            "background-color: #f3f4f6; color: #6b7280; "
            "padding: 2px 8px; border-radius: 4px; "
            "font-family: 'JetBrains Mono', 'Consolas', monospace; "
            "font-size: 11px; font-weight: 600;"
        )
        title_row.addWidget(badge)

        name = QLabel(self._rule.name)
        name.setStyleSheet("font-size: 14px; font-weight: 600;")
        title_row.addWidget(name)
        title_row.addStretch()
        info.addLayout(title_row)

        # 元数据行: 分类 + 报表 + 公式
        meta = QLabel(
            f"{self._rule.category}  ·  "
            f"{', '.join(self._rule.statements)}  ·  "
            f"容差 {self._rule.tolerance}"
        )
        meta.setStyleSheet("font-size: 12px; color: #9ca3af;")
        info.addWidget(meta)

        # 公式预览
        formula = QLabel(self._rule.formula)
        formula.setStyleSheet(
            "font-size: 11px; color: #6b7280; "
            "font-family: 'JetBrains Mono', 'Consolas', monospace; "
            "background-color: #f8f9fa; padding: 2px 8px; "
            "border-radius: 4px; border: 1px solid #e5e7eb;"
        )
        info.addWidget(formula)

        layout.addLayout(info, stretch=1)

        # 右侧: 启用/禁用开关
        switch = SwitchButton()
        switch.setChecked(is_active)
        switch.checkedChanged.connect(
            lambda checked: self._on_toggle(self._rule.rule_id, checked)
        )
        layout.addWidget(switch)


class RulePage(QWidget):
    """规则管理页面: 搜索 + 筛选 + 卡片列表。"""

    def __init__(self, state: AppState) -> None:
        super().__init__()
        self.setObjectName("RulePage")
        self._state = state
        self._all_rules: list = []
        self._filtered_rules: list = []
        self._active_filter = "全部"
        self._search_text = ""
        self._setup_ui()
        self._load_rules()

    def _setup_ui(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 24, 24, 24)

        # 搜索框 + 筛选标签
        toolbar = QHBoxLayout()
        toolbar.setSpacing(12)

        self._search = QLineEdit()
        self._search.setPlaceholderText("搜索规则 ID 或名称...")
        self._search.setFixedHeight(36)
        self._search.setStyleSheet(
            "QLineEdit { border: 1px solid #e5e7eb; border-radius: 6px; "
            "padding: 8px 12px; font-size: 13px; background: #ffffff; }"
            "QLineEdit:focus { border-color: #6366f1; }"
        )
        self._search.textChanged.connect(self._on_search)
        toolbar.addWidget(self._search, stretch=1)

        # 分类筛选标签
        self._filter_btns: list[QPushButton] = []
        for cat in _CATEGORIES:
            btn = QPushButton(cat)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(36)
            btn.setStyleSheet(self._filter_btn_qss(cat == "全部"))
            btn.clicked.connect(lambda checked, c=cat: self._on_filter(c))
            self._filter_btns.append(btn)
            toolbar.addWidget(btn)

        layout.addLayout(toolbar)

        # 统计信息
        self._summary = QLabel("加载中...")
        self._summary.setStyleSheet("font-size: 13px; color: #6b7280;")
        layout.addWidget(self._summary)

        # 规则卡片列表
        self._cards_layout = QVBoxLayout()
        self._cards_layout.setSpacing(8)
        layout.addLayout(self._cards_layout)
        layout.addStretch()

        scroll.setWidget(content)
        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.addWidget(scroll)

    def _filter_btn_qss(self, active: bool) -> str:
        if active:
            return (
                "QPushButton { background-color: #4f46e5; color: white; "
                "border: none; border-radius: 6px; padding: 8px 16px; "
                "font-size: 13px; font-weight: 500; }"
            )
        return (
            "QPushButton { background-color: #ffffff; color: #6b7280; "
            "border: 1px solid #e5e7eb; border-radius: 6px; padding: 8px 16px; "
            "font-size: 13px; font-weight: 500; }"
            "QPushButton:hover { background-color: #f3f4f6; }"
        )

    def _load_rules(self) -> None:
        registry = self._state.registry
        if registry is None:
            self._summary.setText("规则库未加载")
            return

        self._all_rules = list(registry.get_all())
        self._active_ids = {r.rule_id for r in registry.get_active()}
        self._refresh()

    def _refresh(self) -> None:
        self._apply_filter()
        self._render_cards()
        self._update_summary()

    def _on_search(self, text: str) -> None:
        self._search_text = text.strip().lower()
        self._refresh()

    def _on_filter(self, cat: str) -> None:
        self._active_filter = cat
        for i, c in enumerate(_CATEGORIES):
            active = c == cat
            self._filter_btns[i].setChecked(active)
            self._filter_btns[i].setStyleSheet(self._filter_btn_qss(active))
        self._refresh()

    def _apply_filter(self) -> None:
        self._filtered_rules = []
        for rule in self._all_rules:
            if self._active_filter != "全部":
                cat_short = rule.category.split("-")[-1] if "-" in rule.category else rule.category
                if cat_short != self._active_filter:
                    continue
            if self._search_text:
                haystack = (rule.rule_id + rule.name).lower()
                if self._search_text not in haystack:
                    continue
            self._filtered_rules.append(rule)

    def _render_cards(self) -> None:
        self._clear_cards()
        registry = self._state.registry
        if registry is None:
            return
        active_ids = {r.rule_id for r in registry.get_active()}
        for rule in self._filtered_rules:
            card = RuleCard(rule, rule.rule_id in active_ids, self._on_toggle)
            self._cards_layout.addWidget(card)

    def _clear_cards(self) -> None:
        while self._cards_layout.count():
            item = self._cards_layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _update_summary(self) -> None:
        total = len(self._all_rules)
        registry = self._state.registry
        active = len(registry.get_active()) if registry else 0
        shown = len(self._filtered_rules)
        self._summary.setText(
            f"共 {total} 条规则 (启用 {active} 条) · 当前显示 {shown} 条"
        )

    def _on_toggle(self, rule_id: str, checked: bool) -> None:
        registry = self._state.registry
        if registry is None:
            return
        if checked:
            registry.enable(rule_id)
        else:
            registry.disable(rule_id)
        self._update_summary()
