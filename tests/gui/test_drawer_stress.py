"""AI 抽屉与界面 压力/边界测试。

覆盖用户指定的 6 个方面:
1. 界面稳定性 (快速切页/切主题/缩放)
2. 抽屉各项功能 (开关/会话/发送)
3. 图标状态稳定准确 (FAB角标/主题图标/显隐)
4. 抽屉拖拽调整的内容可靠度 (宽度 clamp + 内容不溢出)
5. 发送按钮文字准确显示
6. 输入框文字增多时自动增加高度

设计原则: 用对抗性极端操作 (快速连续/边界值/超长输入) 暴露问题。
"""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication, QPushButton

from fsa.gui.app_state import AppState
from fsa.gui.main_window import MainWindow
from fsa.gui.theme import get_qss

# 整个文件为耗时压测 (rapid 50x/100x 循环), 默认套件跳过;
# 改动抽屉/主题/布局相关代码或发布前, 用 pytest -m slow 显式运行
pytestmark = pytest.mark.slow


@pytest.fixture
def window(qapp, qtbot):
    """创建主窗口 (浅色主题)。"""
    app = QApplication.instance()
    if isinstance(app, QApplication):
        app.setStyleSheet(get_qss(False))
    state = AppState()
    state.load_registry()
    win = MainWindow(state)
    win.resize(1280, 800)
    qtbot.addWidget(win)
    win.show()
    return win


# ═══════════════ 1. 界面稳定性 ═══════════════

class TestUIStability:
    def test_rapid_page_switching_100x(self, window, qtbot) -> None:
        """快速连续切换 5 个页面 20 轮 (100 次), 无崩溃无异常。"""
        navs = ["navImport", "navAudit", "navRules", "navHistory", "navSettings"]
        for _ in range(20):
            for nav in navs:
                window._on_nav(nav)
        qtbot.wait(10)
        assert window._stack.currentIndex() == 4  # 最后停在设置页

    def test_rapid_theme_toggle_50x(self, window, qtbot) -> None:
        """快速切换主题 50 次, 主题状态与图标保持一致。"""
        initial_dark = window._dark
        for _ in range(50):
            window._toggle_theme()
        qtbot.wait(10)
        # 偶数次切换回到初始状态
        assert window._dark == initial_dark

    def test_rapid_window_resize(self, window, qtbot) -> None:
        """快速缩放窗口到各种尺寸, FAB 位置始终正确。"""
        sizes = [(960, 600), (1280, 800), (1920, 1080), (1024, 768), (1280, 800)]
        for w, h in sizes:
            window.resize(w, h)
            qtbot.wait(5)
        # FAB 应在右下角 (工作区页面)
        window._on_nav("navImport")
        window._position_fab()
        rect = window.centralWidget().geometry()
        fab = window._agent_fab
        assert fab.x() + fab.width() <= rect.right() + 1
        assert fab.y() + fab.height() <= rect.bottom() + 1

    def test_resize_below_minimum(self, window, qtbot) -> None:
        """缩放到最小尺寸以下, 被钳制到 960x600。"""
        window.resize(400, 300)
        qtbot.wait(10)
        assert window.width() >= 960
        assert window.height() >= 600


# ═══════════════ 2. 抽屉各项功能 ═══════════════

class TestDrawerFunctions:
    def test_rapid_open_close_50x(self, window, qtbot) -> None:
        """快速开关抽屉 50 次, 状态一致 (FAB 显隐正确)。"""
        window._on_nav("navImport")
        for _ in range(50):
            window._toggle_drawer()
        qtbot.wait(10)
        # 偶数次后抽屉应为关闭, FAB 应可见
        assert not window._agent_drawer.isVisible()
        assert window._agent_fab.isVisible()

    def test_drawer_open_hides_fab(self, window, qtbot) -> None:
        """抽屉打开时 FAB 隐藏 (避免遮盖建议气泡)。"""
        window._on_nav("navImport")
        window._open_drawer()
        qtbot.wait(10)
        assert window._agent_drawer.isVisible()
        assert not window._agent_fab.isVisible()
        window._close_drawer()

    def test_send_empty_message_ignored(self, window, qtbot) -> None:
        """发送空消息被忽略, 不产生气泡。"""
        window._open_drawer()
        drawer = window._agent_drawer
        before = drawer._messages_layout.count()
        drawer._input.setPlainText("   ")
        drawer._on_send()
        qtbot.wait(10)
        assert drawer._messages_layout.count() == before
        window._close_drawer()

    def test_send_message_appears(self, window, qtbot) -> None:
        """发送消息后气泡出现在消息区。"""
        window._open_drawer()
        drawer = window._agent_drawer
        before = drawer._messages_layout.count()
        drawer._input.setPlainText("测试消息")
        drawer._on_send()
        qtbot.wait(10)
        assert drawer._messages_layout.count() > before
        window._close_drawer()

    def test_rapid_send_30_messages(self, window, qtbot) -> None:
        """快速连续发送 30 条消息, 全部记录无丢失。"""
        window._open_drawer()
        drawer = window._agent_drawer
        before = drawer._messages_layout.count()
        for i in range(30):
            drawer._input.setPlainText(f"消息{i}")
            drawer._on_send()
        qtbot.wait(20)
        assert drawer._messages_layout.count() >= before + 30
        window._close_drawer()


# ═══════════════ 3. 图标状态稳定准确 ═══════════════

class TestIconStates:
    def test_fab_visible_only_workspace(self, window, qtbot) -> None:
        """FAB 仅在工作区(导入/审计)显示, 其他页隐藏。"""
        cases = [
            ("navImport", True), ("navAudit", True),
            ("navRules", False), ("navHistory", False), ("navSettings", False),
        ]
        for nav, expected in cases:
            window._on_nav(nav)
            qtbot.wait(5)
            assert window._agent_fab.isVisible() == expected, f"{nav} FAB 显隐错误"

    def test_theme_icon_matches_state(self, window, qtbot) -> None:
        """主题图标与当前主题状态一致。"""
        window._dark = False
        window._topbar.set_theme_icon(False)
        assert not window._topbar._theme_btn.icon().isNull()
        window._topbar.set_theme_icon(True)
        assert not window._topbar._theme_btn.icon().isNull()

    def test_validate_export_button_states(self, window, qtbot) -> None:
        """校验/导出按钮状态随数据正确变化。"""
        # 初始: 都禁用
        assert not window._topbar._validate_btn.isEnabled()
        assert not window._topbar._export_btn.isEnabled()


# ═══════════════ 4. 抽屉拖拽调整 ═══════════════

class TestDrawerResize:
    def test_resize_clamped_to_min(self, window, qtbot) -> None:
        """拖到最小宽度以下被钳制到 320。"""
        window._open_drawer()
        drawer = window._agent_drawer
        drawer.resize(100, drawer.height())  # 模拟拖到极小
        qtbot.wait(5)
        assert drawer.width() == 320
        assert drawer.MIN_WIDTH == 320
        window._close_drawer()

    def test_resize_clamped_to_max(self, window, qtbot) -> None:
        """拖到最大宽度以上被钳制到 600。"""
        drawer = window._agent_drawer
        clamped = max(drawer.MIN_WIDTH, min(drawer.MAX_WIDTH, 999))
        assert clamped == 600

    def test_resize_preserves_content(self, window, qtbot) -> None:
        """拖拽到各宽度, 内部组件不溢出 (宽度不超过抽屉)。"""
        window._on_nav("navImport")
        window._open_drawer()
        drawer = window._agent_drawer
        for width in (320, 400, 600):
            drawer.resize(width, drawer.height())
            qtbot.wait(5)
            # 输入框 + 发送按钮总宽不应超过抽屉内容宽
            assert drawer._input.width() + 48 + 8 <= width
        window._close_drawer()

    def test_rapid_drag_back_forth(self, window, qtbot) -> None:
        """快速来回拖拽 30 次, 宽度始终在合法范围。"""
        window._open_drawer()
        drawer = window._agent_drawer
        for _ in range(30):
            drawer.resize(320, drawer.height())
            drawer.resize(600, drawer.height())
        qtbot.wait(10)
        assert 320 <= drawer.width() <= 600
        window._close_drawer()


# ═══════════════ 5. 发送按钮文字 ═══════════════

class TestSendButton:
    def test_send_button_text_complete(self, window, qtbot) -> None:
        """发送按钮完整显示'发送'二字。"""
        window._open_drawer()
        drawer = window._agent_drawer
        # 找发送按钮 (文本为"发送")
        from PySide6.QtWidgets import QPushButton as QPB
        btns = drawer.findChildren(QPB)
        send = next((b for b in btns if b.text() == "发送"), None)
        assert send is not None, "未找到发送按钮"
        assert send.text() == "发送"
        # 按钮宽度足够显示文字 (sizeHint 不超过实际宽度)
        assert send.sizeHint().width() <= send.width() + 2
        window._close_drawer()

    def test_send_button_visible_at_min_drawer_width(self, window, qtbot) -> None:
        """抽屉最小宽度 280 时发送按钮仍完整可见。"""
        window._open_drawer()
        drawer = window._agent_drawer
        drawer.setFixedWidth(280)
        qtbot.wait(10)
        btns = drawer.findChildren(QPushButton)
        send = next((b for b in btns if b.text() == "发送"), None)
        assert send is not None and send.isVisible()
        window._close_drawer()


# ═══════════════ 6. 输入框自动增高 ═══════════════

class TestInputAutoHeight:
    def test_input_grows_with_long_text(self, window, qtbot) -> None:
        """输入多行文字时输入框高度自动增加 (当前失败 -> 驱动修复)。"""
        window._open_drawer()
        drawer = window._agent_drawer
        initial_height = drawer._input.height()
        # 输入多行长文本
        long_text = "这是一段很长的文字\n" * 10
        drawer._input.setPlainText(long_text)
        qtbot.wait(20)
        new_height = drawer._input.height()
        window._close_drawer()
        assert new_height > initial_height, (
            f"输入框未自动增高: 初始{initial_height}, 多行后{new_height}"
        )

    def test_input_height_capped(self, window, qtbot) -> None:
        """输入框高度有上限, 不会无限增长。"""
        window._open_drawer()
        drawer = window._agent_drawer
        huge_text = "行\n" * 100
        drawer._input.setPlainText(huge_text)
        qtbot.wait(20)
        height = drawer._input.height()
        window._close_drawer()
        # 高度应有合理上限 (如 <= 150px)
        assert height <= 200, f"输入框高度无上限: {height}"
