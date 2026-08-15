"""AI 抽屉 (AgentDrawer) 功能测试: AD-01, AD-03, AD-06, AD-07, AD-08, AD-11。

覆盖: 开关/缩放/消息/建议/上下文/流式/思考折叠/Markdown 渲染/
黏底滚动/欢迎空态 (重构后的渲染层)。
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QLabel,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
)

from fsa.gui.main_window import MainWindow
from fsa.gui.widgets.agent_drawer import AgentDrawer
from fsa.gui.widgets.agent_messages import md_to_html


class TestDrawerOpenClose:
    """测试抽屉打开/关闭 (AD-01, AD-03)。"""

    def test_fab_click_opens_drawer_and_overlay(self, qapp, qtbot, app_state) -> None:
        """点击 FAB 打开抽屉和遮罩 (AD-01)。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        window.show()
        qtbot.wait(50)
        window._agent_fab.clicked_fab.emit()
        assert not window._agent_drawer.isHidden()
        assert not window._overlay.isHidden()

    def test_fab_click_again_closes_drawer(self, qapp, qtbot, app_state) -> None:
        """抽屉打开时再点 FAB 关闭抽屉 (AD-03)。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        window.show()
        qtbot.wait(50)
        window._agent_fab.clicked_fab.emit()
        assert not window._agent_drawer.isHidden()
        window._agent_fab.clicked_fab.emit()
        assert window._agent_drawer.isHidden()
        assert window._overlay.isHidden()

    def test_esc_key_closes_drawer(self, qapp, qtbot, app_state) -> None:
        """ESC 键关闭抽屉 (AD-05)。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        window.show()
        qtbot.wait(50)
        window._agent_fab.clicked_fab.emit()
        assert not window._agent_drawer.isHidden()

        QTest.keyClick(window, Qt.Key.Key_Escape)
        assert window._agent_drawer.isHidden()


class TestDrawerResize:
    """测试拖拽调宽 (AD-06)。"""

    def test_drag_resize_clamps_to_min(self, qapp, qtbot, app_state) -> None:
        """拖拽宽度不下于 320 (AD-06)。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        drawer = window._agent_drawer
        handle = drawer._resize_handle

        QTest.mousePress(handle, Qt.MouseButton.LeftButton, pos=QPoint(0, 0))
        QTest.mouseMove(handle, QPoint(-1000, 0))
        QTest.mouseRelease(handle, Qt.MouseButton.LeftButton, pos=QPoint(-1000, 0))

        assert drawer.width() >= drawer.MIN_WIDTH, (
            f"宽度 {drawer.width()} 应 >= {drawer.MIN_WIDTH}"
        )

    def test_drag_resize_clamps_to_max(self, qapp, qtbot, app_state) -> None:
        """拖拽宽度不超过 600 (AD-06)。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        drawer = window._agent_drawer
        handle = drawer._resize_handle

        QTest.mousePress(handle, Qt.MouseButton.LeftButton, pos=QPoint(0, 0))
        QTest.mouseMove(handle, QPoint(1000, 0))
        QTest.mouseRelease(handle, Qt.MouseButton.LeftButton, pos=QPoint(1000, 0))

        assert drawer.width() <= drawer.MAX_WIDTH, (
            f"宽度 {drawer.width()} 应 <= {drawer.MAX_WIDTH}"
        )


class TestDrawerMessages:
    """测试消息发送 (AD-07, AD-08)。"""

    def test_send_message_adds_bubble(self, qapp, qtbot, app_state) -> None:
        """发送消息添加用户气泡 (AD-07)。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        drawer = window._agent_drawer

        drawer._input.setPlainText("测试消息")
        drawer._on_send()

        container = drawer._scroll.widget()
        assert container is not None, "消息容器不应为空"
        msg_layout = container.findChild(QVBoxLayout)
        assert msg_layout is not None
        assert msg_layout.count() >= 2

    def test_suggestion_bubble_sends_question(self, qapp, qtbot, app_state) -> None:
        """点击建议气泡发送对应问题 (AD-08)。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        drawer = window._agent_drawer

        suggestion_btns = [
            w for w in drawer.findChildren(QPushButton)
            if w.objectName() == "AgentSuggestion"
        ]
        assert len(suggestion_btns) >= 1, "应有至少一个建议按钮"

        received: list[str] = []
        drawer.send_requested.connect(lambda text: received.append(text))

        QTest.mouseClick(suggestion_btns[0], Qt.MouseButton.LeftButton)
        assert len(received) == 1, "应收到一条发送请求"
        assert len(received[0]) > 0, "发送内容不应为空"


class TestDrawerContext:
    """测试上下文栏 (AD-11)。"""

    def test_set_context_shows_context_bar_with_rule_text(self, qapp, qtbot, app_state) -> None:
        """设置上下文后上下文栏显示规则文本 (AD-11)。

        规则名按抽屉宽度 elide (并行壳层行为), 故只断言前缀存活。
        """
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        drawer = window._agent_drawer

        drawer.set_context("BS-BAL-001", "资产负债表平衡校验")
        assert not drawer._context_bar.isHidden()
        assert "BS-BAL-001" in drawer._context_label.text()
        assert "资产负债表" in drawer._context_label.text()

    def test_clear_context_hides_context_bar(self, qapp, qtbot, app_state) -> None:
        """清除上下文后上下文栏隐藏 (AD-11)。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        drawer = window._agent_drawer

        drawer.set_context("BS-BAL-001", "测试规则")
        assert not drawer._context_bar.isHidden()

        drawer._clear_context()
        assert drawer._context_bar.isHidden()
        assert drawer._context_label.text() == ""


class TestMarkdownRendering:
    """md_to_html 模块级渲染断言。"""

    def test_bold(self) -> None:
        assert "<strong>加粗</strong>" in md_to_html("**加粗**")

    def test_italic_and_code(self) -> None:
        html = md_to_html("*斜体* `代码`")
        assert "<em>斜体</em>" in html
        assert ">代码</code>" in html
        assert "<code " in html

    def test_unordered_list(self) -> None:
        html = md_to_html("- 项目A\n- 项目B")
        assert "<ul" in html
        assert "项目A" in html
        assert "项目B" in html

    def test_ordered_list(self) -> None:
        html = md_to_html("1. 第一\n2. 第二")
        assert "<ol" in html
        assert "第一" in html

    def test_fenced_code_block(self) -> None:
        html = md_to_html("```python\nx = 1\nprint(x)\n```")
        assert "<pre" in html
        assert "x = 1" in html
        assert "print(x)" in html

    def test_table(self) -> None:
        html = md_to_html("|列A|列B|\n|---|---|\n|1|2|")
        assert "<table" in html
        assert ">列A</th>" in html
        assert ">列B</th>" in html
        assert ">1</td>" in html
        assert ">2</td>" in html

    def test_link_text_only(self) -> None:
        html = md_to_html("[文本](http://example.com)")
        assert "<a" not in html
        assert "文本" in html

    def test_script_escaped(self) -> None:
        html = md_to_html("<script>alert(1)</script>")
        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_heading(self) -> None:
        html = md_to_html("# 标题\n## 副标题")
        assert ">标题</h3>" in html
        assert ">副标题</h4>" in html


class TestAssistantBubble:
    """AI 气泡: QTextBrowser + Markdown 渲染。"""

    def _make_window(self, qapp, qtbot, app_state) -> MainWindow:
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        window.show()
        qtbot.wait(50)
        return window

    def test_assistant_bubble_is_text_browser_with_bold(
        self, qapp, qtbot, app_state
    ) -> None:
        """AI 气泡是 QTextBrowser, 且 Markdown 加粗真实渲染。"""
        window = self._make_window(qapp, qtbot, app_state)
        drawer = window._agent_drawer
        drawer.add_assistant_message("**加粗** 和 *斜体*")

        bubbles = [
            w for w in drawer.findChildren(QTextBrowser)
            if w.objectName() == "AgentBubbleAssistant"
        ]
        assert bubbles, "应有 AI 气泡"
        bubble = bubbles[-1]
        assert isinstance(bubble, QTextBrowser)
        assert "加粗" in bubble.toPlainText()
        # 原始 md_to_html 输出含 <strong>
        assert "<strong>加粗</strong>" in md_to_html("**加粗**")
        # 首字符为加粗格式 (Qt 会把 <strong> 序列化为 font-weight span)
        from PySide6.QtGui import QFont, QTextCursor

        cursor = bubble.textCursor()
        cursor.select(QTextCursor.SelectionType.Document)
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        cursor.movePosition(
            QTextCursor.MoveOperation.NextCharacter,
            QTextCursor.MoveMode.KeepAnchor,
        )
        assert cursor.charFormat().fontWeight() >= QFont.Weight.Bold

    def test_refresh_theme_rerenders_bubbles(self, qapp, qtbot, app_state) -> None:
        """refresh_theme 重刷已渲染 AI 气泡不崩溃且保留文本。"""
        window = self._make_window(qapp, qtbot, app_state)
        drawer = window._agent_drawer
        drawer.add_assistant_message("**加粗** 内容")
        drawer.refresh_theme()
        bubbles = [
            w for w in drawer.findChildren(QTextBrowser)
            if w.objectName() == "AgentBubbleAssistant"
        ]
        assert bubbles
        assert "加粗" in bubbles[-1].toPlainText()

    def test_bubble_max_width_caps(self, qapp, qtbot, app_state) -> None:
        """AI 气泡上限 460px, 用户气泡上限 400px (宽抽屉行长不过长)。"""
        window = self._make_window(qapp, qtbot, app_state)
        drawer = window._agent_drawer
        drawer.add_assistant_message("**加粗**")
        drawer.add_user_message("问题")

        ai = [
            w for w in drawer.findChildren(QTextBrowser)
            if w.objectName() == "AgentBubbleAssistant"
        ]
        user = [
            w for w in drawer.findChildren(QLabel)
            if w.objectName() == "AgentBubbleUser"
        ]
        assert ai and ai[-1].maximumWidth() <= 460
        assert user and user[-1].maximumWidth() <= 400


class TestStickToBottom:
    """黏底滚动状态机 + 回到底部按钮。"""

    def _make_drawer(self, qapp, qtbot) -> AgentDrawer:
        drawer = AgentDrawer(chat_repo=None)
        qtbot.addWidget(drawer)
        drawer.show()
        qtbot.wait(20)
        return drawer

    def test_stick_flips_when_scrolled_up_and_button_shows(
        self, qapp, qtbot, app_state
    ) -> None:
        """距底部较远时翻转非黏底并显示按钮; 点击后恢复黏底并隐藏按钮。"""
        drawer = self._make_drawer(qapp, qtbot)
        for i in range(25):
            drawer._add_message("assistant", "A" * 300 + str(i))
        qtbot.wait(50)

        bar = drawer._scroll.verticalScrollBar()
        assert bar.maximum() > 0, "应有可滚动内容"
        assert drawer._stick_button is not None

        # 模拟用户向上滚动 (远离底部)
        drawer._on_scroll_value_changed(0)
        assert drawer._stick_bottom is False
        assert drawer._stick_button.isVisible()

        # 点击"回到底部" -> 恢复黏底并隐藏按钮
        drawer._scroll_to_bottom_clicked()
        qtbot.wait(20)
        assert drawer._stick_bottom is True
        assert not drawer._stick_button.isVisible()

    def test_user_message_restores_stick_bottom(self, qapp, qtbot, app_state) -> None:
        """用户上滑后发新消息: 恢复黏底、隐藏按钮并滚到底 (新回复可见)。"""
        drawer = self._make_drawer(qapp, qtbot)
        for i in range(15):
            drawer._add_message("assistant", "A" * 200 + str(i))
        qtbot.wait(50)

        bar = drawer._scroll.verticalScrollBar()
        assert bar.maximum() > 0, "应有可滚动内容"

        # 用户上滑 -> 非黏底
        drawer._on_scroll_value_changed(0)
        assert drawer._stick_bottom is False

        # 新用户消息 (add_user_message 公共路径) -> 恢复黏底
        drawer.add_user_message("新问题")
        qtbot.wait(30)
        assert drawer._stick_bottom is True
        assert bar.value() == bar.maximum(), "应滚到底部"
        assert not drawer._stick_button.isVisible()


class TestSuggestionsGrid:
    """建议 chips: 2 列网格, 窄窗不截断, tooltip 兜底。"""

    def test_suggestions_use_two_column_grid(self, qapp, qtbot, app_state) -> None:
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        drawer = window._agent_drawer

        from PySide6.QtWidgets import QGridLayout

        assert isinstance(drawer._suggestions_layout, QGridLayout)
        chips = [
            w
            for w in drawer._suggestions_frame.findChildren(QPushButton)
            if w.objectName() == "AgentSuggestion"
        ]
        assert len(chips) >= 3
        assert all(chip.toolTip() for chip in chips), "chip 应有完整文本 tooltip"


class TestThinkingCollapse:
    """思考过程折叠: 流式展开, 收尾自动收起。"""

    def _make_window(self, qapp, qtbot, app_state) -> MainWindow:
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        return window

    def test_thinking_collapsed_after_finish(self, qapp, qtbot, app_state) -> None:
        """思考标题存在; 流式期间展开, finish 后收起。"""
        window = self._make_window(qapp, qtbot, app_state)
        drawer = window._agent_drawer

        handle = drawer.start_stream_message()
        drawer.append_stream_reasoning(handle, "思考片段")
        drawer.append_stream_chunk(handle, "回答")

        assert handle.reasoning_toggle is not None
        assert "思考过程" in handle.reasoning_toggle.text()
        assert handle.reasoning_label is not None
        assert "思考片段" in handle.reasoning_label.text()
        # 流式期间默认展开 (checkable 按钮处于勾选态)
        assert handle.reasoning_toggle.isChecked() is True

        drawer.finish_stream_message(handle)
        assert handle.reasoning_toggle.isChecked() is False
        assert "▸" in handle.reasoning_toggle.text()
        assert handle.reasoning_label.isHidden()


class TestWelcomeEmptyState:
    """欢迎空态: 居中引导 + 免责小字, 无伪欢迎气泡。"""

    def test_welcome_shows_title_desc_and_disclaimer(
        self, qapp, qtbot, app_state
    ) -> None:
        drawer = AgentDrawer(chat_repo=None)
        qtbot.addWidget(drawer)

        labels = drawer.findChildren(QLabel)
        titles = [
            label for label in labels if label.objectName() == "AgentWelcomeTitle"
        ]
        descs = [
            label for label in labels if label.objectName() == "AgentWelcomeDesc"
        ]
        disclaimers = [
            label
            for label in labels
            if label.objectName() == "AgentWelcomeDisclaimer"
        ]

        assert titles and "AI 诊断助手" in titles[0].text()
        assert descs and "根因分析" in descs[0].text()
        assert disclaimers and "仅供参考" in disclaimers[0].text()

        # 无伪欢迎气泡 (欢迎空态不是一条 assistant 消息)
        assert not [
            w for w in drawer.findChildren(QTextBrowser)
            if w.objectName() == "AgentBubbleAssistant"
        ]


class TestDrawerStreaming:
    """流式消息气泡: 分块追加 / 思考过程弱化区 / 收尾 (P1)。"""

    def test_stream_chunks_accumulate_into_bubble(
        self, qapp, qtbot, app_state
    ) -> None:
        """start_stream_message + append_stream_chunk + finish 累积文本。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        drawer = window._agent_drawer

        handle = drawer.start_stream_message()
        drawer.append_stream_chunk(handle, "你")
        drawer.append_stream_chunk(handle, "好")
        drawer.finish_stream_message(handle)

        assert handle.bubble.toPlainText() == "你好"
        assert isinstance(handle.bubble, QTextBrowser)
        # 气泡行 + 时间戳行
        assert handle.layout.count() >= 2

    def test_stream_reasoning_creates_thinking_label(
        self, qapp, qtbot, app_state
    ) -> None:
        """首块推理创建标题按钮 + 内容标签, 后续分块追加。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        drawer = window._agent_drawer

        handle = drawer.start_stream_message()
        drawer.append_stream_reasoning(handle, "思考片段")
        assert handle.reasoning_label is not None
        assert handle.reasoning_toggle is not None
        assert "思考过程" in handle.reasoning_toggle.text()
        assert "思考片段" in handle.reasoning_label.text()

        drawer.append_stream_reasoning(handle, "更多")
        assert "更多" in handle.reasoning_label.text()
        drawer.finish_stream_message(handle)

    def test_stream_reasoning_displayed_before_bubble(
        self, qapp, qtbot, app_state
    ) -> None:
        """思考过程区插入在正式气泡之前 (index 0)。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        drawer = window._agent_drawer

        handle = drawer.start_stream_message()
        drawer.append_stream_reasoning(handle, "思考")
        drawer.append_stream_chunk(handle, "回答")
        drawer.finish_stream_message(handle)

        # layout 第 0 项是推理区 (QVBoxLayout: 标题按钮 + 内容), 之后是气泡行
        first = handle.layout.itemAt(0)
        assert first is not None
        assert isinstance(first, QVBoxLayout)

    def test_stream_empty_finish_persists_nothing(
        self, qapp, qtbot, app_state
    ) -> None:
        """空气泡收尾不持久化 (无内容不污染会话历史)。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        drawer = window._agent_drawer

        handle = drawer.start_stream_message()
        drawer.finish_stream_message(handle)
        assert handle.bubble.toPlainText() == ""
