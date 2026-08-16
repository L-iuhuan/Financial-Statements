"""C P2-3 hover 阴影测试: enterEvent/leaveEvent 挂/卸 QGraphicsDropShadowEffect。"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QPointF
from PySide6.QtGui import QEnterEvent
from PySide6.QtWidgets import QGraphicsDropShadowEffect

from fsa.gui.theme import apply_theme, get_shadow_color
from fsa.gui.widgets.result_card import ResultCard
from fsa.gui.widgets.summary_card import SummaryCard
from tests.gui.helpers import make_result


def _enter(widget: object) -> None:
    """模拟鼠标进入 (offscreen 下直接派发事件)。"""
    widget.enterEvent(QEnterEvent(QPointF(1, 1), QPointF(1, 1), QPointF(1, 1)))  # type: ignore[attr-defined]


def _leave(widget: object) -> None:
    """模拟鼠标离开。"""
    widget.leaveEvent(QEvent(QEvent.Type.Leave))  # type: ignore[attr-defined]


class TestResultCardHoverShadow:
    """结果卡片 hover 阴影。"""

    def test_enter_attaches_shadow(self, qapp, qtbot) -> None:
        """鼠标进入时挂阴影效果。"""
        card = ResultCard(make_result())
        qtbot.addWidget(card)
        assert card.graphicsEffect() is None

        _enter(card)

        effect = card.graphicsEffect()
        assert isinstance(effect, QGraphicsDropShadowEffect)
        assert effect.offset().y() == 2
        assert effect.color() == get_shadow_color(hover=True)

    def test_leave_detaches_shadow(self, qapp, qtbot) -> None:
        """鼠标离开时卸载阴影。"""
        card = ResultCard(make_result())
        qtbot.addWidget(card)
        _enter(card)

        _leave(card)

        assert card.graphicsEffect() is None

    def test_theme_switch_refreshes_shadow_color(self, qapp, qtbot) -> None:
        """主题切换时已挂载的阴影刷新颜色 (深浅主题透明度不同)。"""
        apply_theme(dark=False)
        card = ResultCard(make_result())
        qtbot.addWidget(card)
        _enter(card)

        apply_theme(dark=True)
        card._refresh_shadow_color()

        effect = card.graphicsEffect()
        assert isinstance(effect, QGraphicsDropShadowEffect)
        assert effect.color() == get_shadow_color(hover=True)
        apply_theme(dark=False)


class TestSummaryCardHoverShadow:
    """汇总卡片 hover 阴影。"""

    def test_enter_leave_shadow(self, qapp, qtbot) -> None:
        """进入挂阴影, 离开卸载。"""
        card = SummaryCard("success")
        qtbot.addWidget(card)

        _enter(card)
        assert isinstance(card.graphicsEffect(), QGraphicsDropShadowEffect)

        _leave(card)
        assert card.graphicsEffect() is None

    def test_theme_listener_refreshes_shadow(self, qapp, qtbot) -> None:
        """主题监听回调刷新已挂载阴影颜色。"""
        apply_theme(dark=True)
        card = SummaryCard("info")
        qtbot.addWidget(card)
        _enter(card)

        apply_theme(dark=False)
        card._on_theme_changed()

        effect = card.graphicsEffect()
        assert isinstance(effect, QGraphicsDropShadowEffect)
        assert effect.color() == get_shadow_color(hover=True)
