"""AI 抽屉壳层测试: 忙碌条/取消信号/阶段提示/免责底栏/上下文 chip/会话按钮 elide。

独立实例化 AgentDrawer (chat_repo=None), 不依赖 MainWindow 与 designer 并行改动。
"""

from __future__ import annotations

from PySide6.QtWidgets import QLabel

from fsa.gui.widgets.agent_drawer import AgentDrawer


def _make_drawer(qapp, qtbot) -> AgentDrawer:
    drawer = AgentDrawer(chat_repo=None)
    qtbot.addWidget(drawer)
    return drawer


class TestBusyBar:
    """忙碌条: 显隐 / 动画定时器 / 停止按钮触发 cancelRequested。"""

    def test_set_busy_starts_timer_and_shows_bar(self, qapp, qtbot) -> None:
        drawer = _make_drawer(qapp, qtbot)
        drawer.set_busy(True)
        assert not drawer._busy_bar.isHidden()
        assert drawer._busy_timer.isActive()
        assert drawer._busy_timer.interval() == 400

    def test_set_busy_false_stops_timer_and_hides_bar(self, qapp, qtbot) -> None:
        drawer = _make_drawer(qapp, qtbot)
        drawer.set_busy(True)
        drawer.set_busy(False)
        assert drawer._busy_bar.isHidden()
        assert not drawer._busy_timer.isActive()

    def test_stop_button_emits_cancel_requested(self, qapp, qtbot) -> None:
        drawer = _make_drawer(qapp, qtbot)
        fired: list[int] = []
        drawer.cancelRequested.connect(lambda: fired.append(1))
        drawer.set_busy(True)
        drawer._busy_stop_btn.click()
        assert fired == [1]

    def test_animation_cycles_dots(self, qapp, qtbot) -> None:
        drawer = _make_drawer(qapp, qtbot)
        drawer.set_busy(True)
        first = drawer._busy_label.text()
        assert first.endswith("·")
        drawer._on_busy_tick()
        second = drawer._busy_label.text()
        assert second.endswith("··")
        drawer._on_busy_tick()
        assert drawer._busy_label.text().endswith("···")
        # 回到 1 个点 (循环)
        drawer._on_busy_tick()
        assert drawer._busy_label.text().endswith("·")


class TestStageHint:
    """阶段提示: 文案更新 / 空串复位 / set_busy(False) 复位。"""

    def test_set_stage_hint_updates_text(self, qapp, qtbot) -> None:
        drawer = _make_drawer(qapp, qtbot)
        drawer.set_busy(True)
        drawer.set_stage_hint("裁判正在出具结论…")
        assert "裁判正在出具结论" in drawer._busy_label.text()

    def test_set_stage_hint_empty_resets_to_default(self, qapp, qtbot) -> None:
        drawer = _make_drawer(qapp, qtbot)
        drawer.set_busy(True)
        drawer.set_stage_hint("裁判正在出具结论…")
        drawer.set_stage_hint("")
        assert drawer._busy_label.text().startswith("AI 正在分析")

    def test_set_busy_false_resets_text(self, qapp, qtbot) -> None:
        drawer = _make_drawer(qapp, qtbot)
        drawer.set_busy(True)
        drawer.set_stage_hint("裁判正在出具结论…")
        drawer.set_busy(False)
        assert drawer._busy_label.text() == "AI 正在分析"

    def test_set_stage_hint_ignored_when_not_busy(self, qapp, qtbot) -> None:
        drawer = _make_drawer(qapp, qtbot)
        drawer.set_stage_hint("裁判正在出具结论…")
        # 忙碌条不可见时忽略 (保持默认文案)
        assert drawer._busy_label.text() == "AI 正在分析"


class TestDisclaimer:
    """免责底栏: 存在且含"仅供参考"。"""

    def test_disclaimer_label_exists_and_contains(self, qapp, qtbot) -> None:
        drawer = _make_drawer(qapp, qtbot)
        label = drawer.findChild(QLabel, "AgentDisclaimerLabel")
        assert label is not None
        assert "仅供参考" in label.text()
        assert "审计意见" in label.text()


class TestContextChip:
    """上下文栏: 超长规则名 elide 截断, 短名完整显示。"""

    def test_set_context_elides_long_rule_name(self, qapp, qtbot) -> None:
        drawer = _make_drawer(qapp, qtbot)
        long_name = "超长规则名称" * 30
        drawer.set_context("BS-BAL-001", long_name)
        text = drawer._context_label.text()
        assert "…" in text
        assert "BS-BAL-001" in text

    def test_set_context_keeps_short_rule_name(self, qapp, qtbot) -> None:
        drawer = _make_drawer(qapp, qtbot)
        drawer.set_context("BS-BAL-001", "测试规则")
        text = drawer._context_label.text()
        assert "…" not in text
        assert "测试规则" in text

    def test_clear_context_resets(self, qapp, qtbot) -> None:
        drawer = _make_drawer(qapp, qtbot)
        drawer.set_context("BS-BAL-001", "测试规则")
        assert not drawer._context_bar.isHidden()
        drawer._clear_context()
        assert drawer._context_bar.isHidden()
        assert drawer._context_label.text() == ""


class TestSessionButton:
    """会话按钮: 最大宽度 140 + elide。"""

    def test_session_btn_maximum_width_140(self, qapp, qtbot) -> None:
        drawer = _make_drawer(qapp, qtbot)
        drawer._update_session_btn("新对话")
        assert drawer._session_btn.maximumWidth() == 140

    def test_session_btn_elides_long_title(self, qapp, qtbot) -> None:
        drawer = _make_drawer(qapp, qtbot)
        drawer._update_session_btn("超长会话标题" * 20)
        assert "…" in drawer._session_btn.text()


class TestInputScrollbar:
    """聊天输入框滚动条: 空态/单行不出现, 自动增高到上限后才出现。

    回归守卫: QSS padding 会压缩 QPlainTextEdit 视口, 空文本也出现滚动条;
    修复改用文档边距实现内边距, 空态/单行输入框无滚动条。
    """

    def test_empty_input_has_no_vertical_scrollbar(self, qapp, qtbot) -> None:
        drawer = _make_drawer(qapp, qtbot)
        drawer.show()
        qapp.processEvents()
        assert drawer._input.height() == 36
        assert not drawer._input.verticalScrollBar().isVisible()

    def test_single_line_input_has_no_vertical_scrollbar(self, qapp, qtbot) -> None:
        drawer = _make_drawer(qapp, qtbot)
        drawer.show()
        drawer._input.setPlainText("请分析差异")
        qapp.processEvents()
        assert drawer._input.height() == 36
        assert not drawer._input.verticalScrollBar().isVisible()

    def test_multiline_grows_without_scrollbar_until_cap(self, qapp, qtbot) -> None:
        """多行输入自动增高, 未到 120px 上限前不出现滚动条; 超限后可滚动。"""
        drawer = _make_drawer(qapp, qtbot)
        drawer.show()
        drawer._input.setPlainText("\n".join("测试" for _ in range(5)))
        qapp.processEvents()
        assert drawer._input.height() > 36
        assert not drawer._input.verticalScrollBar().isVisible()
        drawer._input.setPlainText("\n".join("测试" for _ in range(14)))
        qapp.processEvents()
        assert drawer._input.height() == 120
        assert drawer._input.verticalScrollBar().isVisible()


class TestMessagesContainerBackground:
    """消息区容器背景: 关闭 QScrollArea 强制的自绘, 透出抽屉主题背景。

    回归守卫: QScrollArea.setWidget 会强制容器 autoFillBackground=True,
    未设 QSS 背景的裸容器会用浅色调色板自绘, 导致深色主题下问答区白底。
    """

    def test_container_autofill_disabled_after_rebuild(self, qapp, qtbot) -> None:
        drawer = _make_drawer(qapp, qtbot)
        container = drawer._scroll.widget()
        assert container is not None
        assert container.autoFillBackground() is False

    def test_container_autofill_stays_disabled_after_session_switch(self, qapp, qtbot) -> None:
        """切换会话重建消息区后, 容器仍需透出主题背景 (修复不因重建失效)。"""
        drawer = _make_drawer(qapp, qtbot)
        drawer._rebuild_messages(
            [{"role": "user", "content": "请分析差异", "created_at": "2026-08-16 10:00:00"}]
        )
        container = drawer._scroll.widget()
        assert container is not None
        assert container.autoFillBackground() is False
