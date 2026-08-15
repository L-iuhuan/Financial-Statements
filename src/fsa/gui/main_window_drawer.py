"""主窗口 AI 抽屉/浮动按钮管理 (mixin)。

从 main_window 拆分的抽屉显隐/定位/淡入淡出动画与 FAB 定位逻辑 (纯移动, 不改行为)。
由 MainWindow 继承 (需与 MainWindowAgentMixin/MainWindowDebateMixin 组合使用)。

依赖宿主 MainWindow 提供的属性 (均在 __init__/_setup_ui 中初始化):
_agent_drawer / _agent_fab / _overlay; 及 QMainWindow 的 centralWidget()。
"""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QEvent, QObject, QPropertyAnimation, Qt
from PySide6.QtGui import QGuiApplication, QKeyEvent, QResizeEvent
from PySide6.QtWidgets import QFrame, QGraphicsOpacityEffect, QWidget

from fsa.gui.widgets.agent_drawer import AgentDrawer
from fsa.gui.widgets.agent_fab import AgentFAB

# 抽屉动画参数 (时长/缓动统一常量)
_DRAWER_ANIM_MS = 250

# 进行中的抽屉动画 (防止被 GC 提前回收)
_active_drawer_anims: list[QPropertyAnimation] = []


class MainWindowDrawerMixin(QFrame):
    """AI 抽屉与 FAB 的显隐/定位/动画管理 (继承 QFrame 以便访问 QWidget 方法)。"""

    _agent_drawer: AgentDrawer
    _agent_fab: AgentFAB
    _overlay: QFrame

    def _get_current_nav(self) -> str:
        """由宿主 MainWindow 实现: 返回当前导航页 ID。"""
        raise NotImplementedError

    def centralWidget(self) -> QWidget:
        """由宿主 QMainWindow 提供: 中央部件。"""
        raise NotImplementedError

    def _toggle_drawer(self) -> None:
        if self._agent_drawer.isVisible():
            self._close_drawer()
        else:
            self._open_drawer()

    def _open_drawer(self) -> None:
        self._overlay.show()
        self._overlay.raise_()
        self._agent_drawer.show()
        self._agent_drawer.raise_()
        self._position_drawer()
        self._fade_drawer(fade_in=True)
        self._agent_fab.set_badge(False)
        # 抽屉打开时隐藏 FAB, 避免遮盖抽屉底部的建议气泡/输入区
        self._agent_fab.hide()

    def _close_drawer(self) -> None:
        self._fade_drawer(fade_in=False)
        self._overlay.hide()
        # 抽屉关闭后恢复 FAB (仅在当前页是工作区时)
        current_nav = self._get_current_nav()
        if current_nav in ("navImport", "navAudit"):
            self._agent_fab.show()
            self._position_fab()

    def _fade_drawer(self, fade_in: bool) -> None:
        """抽屉淡入/淡出动画 (250ms OutCubic)。offscreen 环境直接显隐。"""
        drawer = self._agent_drawer
        # 测试/offscreen 环境不做动画, 直接显隐
        if QGuiApplication.platformName() == "offscreen":
            if not fade_in:
                drawer.hide()
            return
        effect = QGraphicsOpacityEffect(drawer)
        drawer.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity", drawer)
        anim.setDuration(_DRAWER_ANIM_MS)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.setStartValue(0.0 if fade_in else 1.0)
        anim.setEndValue(1.0 if fade_in else 0.0)

        def _cleanup() -> None:
            drawer.setGraphicsEffect(None)  # type: ignore[arg-type]  # Qt 运行时空值即移除特效
            if not fade_in:
                drawer.hide()
            if anim in _active_drawer_anims:
                _active_drawer_anims.remove(anim)

        anim.finished.connect(_cleanup)
        _active_drawer_anims.append(anim)
        anim.start()

    def _position_drawer(self) -> None:
        """定位 AI 抽屉和遮罩层到右侧。"""
        drawer = self._agent_drawer
        rect = self.centralWidget().geometry()
        # 窗口变窄时收窄抽屉, 避免超出容器右侧;
        # 极端窄窗口下临时放宽最小宽度, 否则 setGeometry 会被 minimumWidth 钳制回原宽
        available = max(1, rect.width())
        if available < drawer.minimumWidth():
            drawer.setMinimumWidth(available)
        drawer_width = min(drawer.width(), available)
        x = rect.right() - drawer_width
        drawer.setGeometry(x, rect.top(), drawer_width, rect.height())
        if drawer.minimumWidth() < drawer.MIN_WIDTH and available >= drawer.MIN_WIDTH:
            drawer.setMinimumWidth(drawer.MIN_WIDTH)
        self._overlay.setGeometry(
            rect.left(), rect.top(), max(0, rect.width() - drawer_width), rect.height()
        )

    def _position_fab(self) -> None:
        """定位 AI 浮动按钮到右下角 (demo: bottom 24px, right 24px)。"""
        rect = self.centralWidget().geometry()
        fab_size = self._agent_fab.width()
        margin = 24
        self._agent_fab.move(
            rect.right() - fab_size - margin,
            rect.bottom() - fab_size - margin,
        )
        self._agent_fab.raise_()

    # ── 窗口事件 (抽屉/FAB 相关) ──

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._position_fab()
        if self._agent_drawer.isVisible():
            self._position_drawer()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape and self._agent_drawer.isVisible():
            self._close_drawer()
            return
        super().keyPressEvent(event)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.MouseButtonPress and obj == self._overlay:
            self._close_drawer()
            return True
        return super().eventFilter(obj, event)
