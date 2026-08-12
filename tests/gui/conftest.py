"""GUI 测试共享 fixtures。"""

from __future__ import annotations

import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"

import pytest
from PySide6.QtCore import QSettings

from fsa.core.models.report import Report
from fsa.gui.app_state import AppState
from tests.gui.helpers import make_registry, make_report


@pytest.fixture
def app_state(qapp) -> AppState:
    """创建带规则注册表的 AppState。"""
    state = AppState()
    state._registry = make_registry()
    return state


@pytest.fixture
def report() -> Report:
    """创建一张测试报表。"""
    return make_report()


@pytest.fixture(autouse=True)
def clear_settings():
    """每个测试前清除 QSettings 并强制同步, 避免跨测试状态污染。"""
    settings = QSettings("FSA", "FinancialAudit")
    settings.clear()
    settings.sync()  # 强制落盘, 确保其他 QSettings 实例读到干净状态
    yield
    settings.clear()
    settings.sync()
