"""规则管理页面: 搜索 + 分类筛选 + 规则卡片列表。

匹配 Demo v4 设计: 搜索框 + 分类标签 + 卡片式规则列表 + 启用/禁用开关 + 容差编辑。
"""

from __future__ import annotations

from collections.abc import Callable

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

from fsa.core.models.rule import ReconciliationRule, Severity
from fsa.gui.app_state import AppState
from fsa.gui.theme import get_mono_font
from fsa.gui.widgets.custom_rule_dialog import CustomRuleDialog

# 分类标签
_CATEGORIES = ["全部", "表内平衡", "表间勾稽", "逻辑合理性"]

# severity 到中文和 QSS status 的映射
_SEV_META: dict[Severity, tuple[str, str]] = {
    Severity.ERROR: ("错误", "error"),
    Severity.WARNING: ("警告", "warning"),
    Severity.INFO: ("提示", "info"),
}


class RuleCard(QFrame):
    """单条规则卡片 (重设计: 垂直分层, 清晰易读)。

    结构:
    - 行1: badge + 名称 + [自定义标记] + severity 标签 + 启用开关 (右对齐)
    - 行2: 分类 · 涉及报表 · 容差类型
    - 行3: 公式 (mono, 自动换行, 不溢出)
    - 行4: 容差编辑 + [删除按钮(仅自定义规则)]
    """

    def __init__(
        self,
        rule: ReconciliationRule,
        is_active: bool,
        is_custom: bool,
        on_toggle: Callable[[str, bool], None],
        on_tolerance_change: Callable[[str, float], None],
        on_delete: Callable[[str], None],
    ) -> None:
        super().__init__()
        self._rule = rule
        self._is_custom = is_custom
        self._on_toggle = on_toggle
        self._on_tolerance_change = on_tolerance_change
        self._on_delete = on_delete
        self._setup_ui(is_active)

    def _setup_ui(self, is_active: bool) -> None:
        self.setObjectName("RuleCard")
        self.setProperty("disabled", not is_active)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        layout.addLayout(self._build_header(is_active))
        layout.addLayout(self._build_meta())
        layout.addWidget(self._build_formula())
        layout.addLayout(self._build_footer())

    def _build_header(self, is_active: bool) -> QHBoxLayout:
        """行1: badge + 名称 + severity + 开关。"""
        row = QHBoxLayout()
        row.setSpacing(8)

        badge = QLabel(self._rule.rule_id)
        badge.setObjectName("RuleBadge")
        row.addWidget(badge)

        name = QLabel(self._rule.name)
        name.setObjectName("RuleName")
        row.addWidget(name)

        if self._is_custom:
            custom_tag = QLabel("自定义")
            custom_tag.setObjectName("CustomRuleTag")
            row.addWidget(custom_tag)

        row.addStretch()

        sev_text, sev_status = _SEV_META.get(
            self._rule.severity, ("未知", "info")
        )
        sev_label = QLabel(sev_text)
        sev_label.setObjectName("RuleSeverityLabel")
        sev_label.setProperty("status", sev_status)
        row.addWidget(sev_label)

        switch = SwitchButton()
        switch.setChecked(is_active)
        switch.checkedChanged.connect(
            lambda checked: self._on_toggle(self._rule.rule_id, checked)
        )
        row.addWidget(switch)
        return row

    def _build_meta(self) -> QHBoxLayout:
        """行2: 分类 · 涉及报表 · 容差类型。"""
        row = QHBoxLayout()
        row.setSpacing(8)
        tol_type_text = {
            "exact": "精确", "absolute": "绝对",
            "relative": "相对", "threshold": "阈值",
        }.get(self._rule.tolerance_type.value, self._rule.tolerance_type.value)
        meta = QLabel(
            f"{self._rule.category}  ·  {', '.join(self._rule.statements)}"
            f"  ·  容差类型: {tol_type_text}"
        )
        meta.setObjectName("MetaLabel")
        meta.setMinimumWidth(0)
        row.addWidget(meta)
        row.addStretch()
        return row

    def _build_formula(self) -> QLabel:
        """行3: 公式块 (中文显示, 自动换行, 英文原版见 tooltip)。"""
        from fsa.gui.formula_display import formula_to_chinese
        formula = QLabel(formula_to_chinese(self._rule.formula))
        formula.setObjectName("FormulaLabel")
        formula.setWordWrap(True)
        formula.setMinimumWidth(0)
        formula.setToolTip(f"英文公式: {self._rule.formula}")
        return formula

    def _build_footer(self) -> QHBoxLayout:
        """行4: 容差编辑 + 删除按钮 (仅自定义规则)。"""
        row = QHBoxLayout()
        row.setSpacing(8)

        tol_label = QLabel("容差")
        tol_label.setObjectName("MetaLabel")
        row.addWidget(tol_label)

        self._tol_input = QLineEdit(str(self._rule.tolerance))
        self._tol_input.setFixedWidth(100)
        self._tol_input.setObjectName("StyledInput")
        self._tol_input.setFont(get_mono_font(10))
        self._tol_input.editingFinished.connect(self._on_tol_changed)
        row.addWidget(self._tol_input)

        row.addStretch()

        if self._is_custom:
            delete_btn = QPushButton("删除")
            delete_btn.setObjectName("DangerBtn")
            delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            delete_btn.clicked.connect(
                lambda: self._on_delete(self._rule.rule_id)
            )
            row.addWidget(delete_btn)
        return row

    def _on_tol_changed(self) -> None:
        text = self._tol_input.text().strip()
        try:
            value = float(text)
        except ValueError:
            return
        self._on_tolerance_change(self._rule.rule_id, value)


class RulePage(QWidget):
    """规则管理页面: 搜索 + 筛选 + 卡片列表。"""

    def __init__(self, state: AppState) -> None:
        super().__init__()
        self.setObjectName("RulePage")
        self._state = state
        self._all_rules: list[ReconciliationRule] = []
        self._filtered_rules: list[ReconciliationRule] = []
        self._active_filter = "全部"
        self._search_text = ""
        self._rule_cards: dict[str, RuleCard] = {}  # 卡片缓存 (消除筛选闪动)
        self._setup_ui()
        self._load_rules()

    def _setup_ui(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        content.setObjectName("PageContent")
        layout = QVBoxLayout(content)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 24, 24, 24)

        # 搜索框 + 筛选标签
        toolbar = QHBoxLayout()
        toolbar.setSpacing(12)

        self._search = QLineEdit()
        self._search.setPlaceholderText("搜索规则 ID 或名称...")
        self._search.setFixedHeight(36)
        self._search.setMinimumWidth(200)
        self._search.setObjectName("SearchInput")
        self._search.textChanged.connect(self._on_search)
        toolbar.addWidget(self._search, stretch=1)

        # 分类筛选标签
        self._filter_btns: list[QPushButton] = []
        for cat in _CATEGORIES:
            btn = QPushButton(cat)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(36)
            btn.setObjectName("FilterTab")
            btn.clicked.connect(lambda checked, c=cat: self._on_filter(c))
            self._filter_btns.append(btn)
            toolbar.addWidget(btn)

        # 新增规则按钮
        add_btn = QPushButton("+ 新增规则")
        add_btn.setObjectName("BtnPrimary")
        add_btn.setFixedHeight(36)
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.clicked.connect(self._on_add_rule)
        toolbar.addWidget(add_btn)

        layout.addLayout(toolbar)

        # 统计信息
        self._summary = QLabel("加载中...")
        self._summary.setObjectName("MetaLabel")
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

    def _load_rules(self) -> None:
        registry = self._state.registry
        if registry is None:
            self._summary.setText("规则库未加载")
            return

        self._all_rules = list(registry.get_all())
        self._active_ids = {r.rule_id for r in registry.get_active()}
        self._rebuild_cards()  # 规则集合变化才重建
        self._refresh()

    def _refresh(self) -> None:
        self._apply_filter()
        self._render_cards()  # 仅切可见性
        self._update_summary()

    def _on_search(self, text: str) -> None:
        self._search_text = text.strip().lower()
        self._refresh()

    def _on_filter(self, cat: str) -> None:
        self._active_filter = cat
        for i, c in enumerate(_CATEGORIES):
            active = c == cat
            btn = self._filter_btns[i]
            btn.setChecked(active)
            btn.setProperty("active", active)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
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
        """筛选/搜索变化时仅切换卡片可见性 (不销毁重建, 消除闪动)。"""
        visible_ids = {r.rule_id for r in self._filtered_rules}
        for rule_id, card in self._rule_cards.items():
            card.setVisible(rule_id in visible_ids)

    def _rebuild_cards(self) -> None:
        """规则集合变化时 (加载/新增/删除) 重建全部卡片并缓存。"""
        self._clear_cards()
        registry = self._state.registry
        if registry is None:
            return
        active_ids = {r.rule_id for r in registry.get_active()}
        self._rule_cards.clear()
        for rule in self._all_rules:
            card = RuleCard(
                rule,
                rule.rule_id in active_ids,
                registry.is_custom(rule.rule_id),
                self._on_toggle,
                self._on_tolerance_change,
                self._on_delete_rule,
            )
            self._cards_layout.addWidget(card)
            self._rule_cards[rule.rule_id] = card

    def _clear_cards(self) -> None:
        while self._cards_layout.count():
            item = self._cards_layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                # 先隐藏再删除, 避免脱离父容器后闪现为独立窗口
                widget.hide()
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

    def _on_tolerance_change(self, rule_id: str, value: float) -> None:
        registry = self._state.registry
        if registry is None:
            return
        registry.set_tolerance(rule_id, value)
        # 持久化容差覆写
        override_repo = self._state.override_repo
        if override_repo is not None:
            override_repo.set(rule_id, value)

    def _on_add_rule(self) -> None:
        """打开新增规则对话框, 校验并保存自定义规则。"""

        registry = self._state.registry
        if registry is None:
            self._show_toast("规则库未加载", "error")
            return

        dialog = CustomRuleDialog(self)
        if dialog.exec() != CustomRuleDialog.DialogCode.Accepted:
            return

        rule = dialog.build_rule()
        if rule is None:
            return  # 校验失败, 对话框已提示

        if not registry.add_rule(rule, custom=True):
            self._show_toast(f"规则编号 {rule.rule_id} 已存在", "error")
            return

        self._persist_custom_rules()
        self._load_rules()
        self._show_toast(f"已添加自定义规则 {rule.rule_id}", "success")

    def _on_delete_rule(self, rule_id: str) -> None:
        """删除自定义规则 (仅自定义规则可删)。"""
        registry = self._state.registry
        if registry is None:
            return
        from PySide6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定删除自定义规则 {rule_id} 吗？此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        if not registry.remove_rule(rule_id):
            self._show_toast("内置规则不可删除", "warning")
            return
        self._persist_custom_rules()
        self._load_rules()
        self._show_toast(f"已删除规则 {rule_id}", "success")

    def _persist_custom_rules(self) -> None:
        """将注册表中的自定义规则写入 custom_rules.json。"""
        from fsa.core.engine.custom_rules import save_custom_rules
        registry = self._state.registry
        if registry is None:
            return
        custom = [
            r for r in registry.get_all() if registry.is_custom(r.rule_id)
        ]
        save_custom_rules(custom)

    def _show_toast(self, message: str, kind: str) -> None:
        """显示顶部提示条。"""
        from qfluentwidgets import InfoBar, InfoBarPosition
        method = {
            "success": InfoBar.success, "warning": InfoBar.warning,
            "error": InfoBar.error, "info": InfoBar.info,
        }.get(kind, InfoBar.info)
        method(
            "提示", message, orient=Qt.Orientation.Horizontal, isClosable=True,
            position=InfoBarPosition.TOP, duration=2500, parent=self,
        )
