"""B3-5 存储降级文案测试: 历史/覆写仓储不可用时用户可感知。"""

from __future__ import annotations

from fsa.gui.pages.history_page import HistoryPage
from fsa.gui.pages.rule_page import RulePage


class TestHistoryStorageDegraded:
    """历史仓储不可用时的空态文案。"""

    def test_unavailable_text_when_repo_none(self, qapp, qtbot, app_state) -> None:
        """repo 为 None 时明示「历史存储不可用，本次校验结果将不被保存」。"""
        app_state._history_repo = None
        page = HistoryPage(app_state)
        qtbot.addWidget(page)

        page._load_history()

        assert page._empty_title.text() == "历史存储不可用"
        assert "本次校验结果将不被保存" in page._empty_desc.text()

    def test_default_empty_text(self, qapp, qtbot, app_state) -> None:
        """普通空态仍是「暂无校验记录」。"""
        page = HistoryPage(app_state)
        qtbot.addWidget(page)

        page._show_empty()

        assert page._empty_title.text() == "暂无校验记录"


class TestRuleOverrideDegraded:
    """覆写仓储不可用时的容差调整提示。"""

    def test_tolerance_applied_session_only(self, qapp, qtbot, app_state) -> None:
        """override_repo 为 None 时容差仍生效 (仅本次会话)。"""
        app_state._override_repo = None
        page = RulePage(app_state)
        qtbot.addWidget(page)

        page._on_tolerance_change("A-001", 0.5)

        rule = app_state.registry.get_by_id("A-001")
        assert rule is not None
        assert rule.tolerance == 0.5
