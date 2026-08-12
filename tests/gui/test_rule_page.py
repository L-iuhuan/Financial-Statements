"""RulePage 规则管理页测试。"""

from __future__ import annotations

from fsa.core.models.rule import Severity
from fsa.gui.pages.rule_page import RuleCard, RulePage
from tests.gui.helpers import make_rule


class TestRuleCardTolerance:
    """测试 RuleCard 容差编辑。"""

    def test_tolerance_callback_called(self, qapp, qtbot) -> None:
        """编辑容差后回调被调用。"""
        calls = []

        def on_tol(rule_id: str, value: float) -> None:
            calls.append((rule_id, value))

        rule = make_rule(rule_id="A-001", tolerance=0.01)
        card = RuleCard(
            rule, True, False,
            lambda rid, checked: None, on_tol, lambda rid: None,
        )
        qtbot.addWidget(card)

        card._tol_input.setText("2.50")
        card._on_tol_changed()

        assert len(calls) == 1
        assert calls[0] == ("A-001", 2.5)

    def test_invalid_tolerance_ignored(self, qapp, qtbot) -> None:
        """无效容差文本被忽略。"""
        calls = []

        def on_tol(rule_id: str, value: float) -> None:
            calls.append((rule_id, value))

        rule = make_rule(rule_id="A-001", tolerance=0.01)
        card = RuleCard(
            rule, True, False,
            lambda rid, checked: None, on_tol, lambda rid: None,
        )
        qtbot.addWidget(card)

        card._tol_input.setText("abc")
        card._on_tol_changed()

        assert len(calls) == 0


class TestRuleCardSeverity:
    """测试 severity 标签显示。"""

    def test_error_severity_label(self, qapp, qtbot) -> None:
        from PySide6.QtWidgets import QLabel
        rule = make_rule(severity=Severity.ERROR)
        card = RuleCard(
            rule, True, False,
            lambda rid, checked: None, lambda rid, val: None, lambda rid: None,
        )
        qtbot.addWidget(card)
        assert card.findChild(QLabel, "RuleSeverityLabel") is not None


class TestRulePageFilter:
    """测试规则页筛选。"""

    def test_search_filters_by_id(self, qapp, qtbot, app_state) -> None:
        page = RulePage(app_state)
        qtbot.addWidget(page)
        page._on_search("A-001")
        assert len(page._filtered_rules) == 1
        assert page._filtered_rules[0].rule_id == "A-001"

    def test_search_filters_by_name(self, qapp, qtbot, app_state) -> None:
        page = RulePage(app_state)
        qtbot.addWidget(page)
        page._on_search("测试规则")
        assert len(page._filtered_rules) == 3
