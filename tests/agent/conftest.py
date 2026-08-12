"""Agent 测试共享 fixtures (轻量 AppState, 不依赖 GUI)。"""

from __future__ import annotations

import pytest

from fsa.gui.app_state import AppState


@pytest.fixture
def app_state() -> AppState:
    """创建轻量 AppState (真实 SQLite, 但测试间不共享数据断言)。"""
    return AppState()
