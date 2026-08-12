"""AgentFAB 浮动按钮测试。"""

from __future__ import annotations

from fsa.gui.widgets.agent_fab import AgentFAB


class TestAgentFABBadge:
    """测试 FAB 角标。"""

    def test_badge_hidden_by_default(self, qapp, qtbot) -> None:
        fab = AgentFAB()
        qtbot.addWidget(fab)
        assert fab._badge.isHidden()

    def test_set_badge_shows(self, qapp, qtbot) -> None:
        fab = AgentFAB()
        qtbot.addWidget(fab)
        fab.set_badge(True)
        assert not fab._badge.isHidden()

    def test_set_badge_false_hides(self, qapp, qtbot) -> None:
        fab = AgentFAB()
        qtbot.addWidget(fab)
        fab.set_badge(True)
        fab.set_badge(False)
        assert fab._badge.isHidden()
