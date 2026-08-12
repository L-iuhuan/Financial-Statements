"""AI 抽屉 (AgentDrawer) 功能测试: AD-01, AD-03, AD-06, AD-07, AD-08, AD-11。"""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QPushButton

from fsa.gui.main_window import MainWindow


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
        """拖拽宽度不下于 280 (AD-06)。"""
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
        from PySide6.QtWidgets import QVBoxLayout
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
        """设置上下文后上下文栏显示规则文本 (AD-11)。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        drawer = window._agent_drawer

        drawer.set_context("BS-BAL-001", "资产负债表平衡校验")
        assert not drawer._context_bar.isHidden()
        assert "BS-BAL-001" in drawer._context_label.text()
        assert "资产负债表平衡校验" in drawer._context_label.text()

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
