"""导入页 (ImportPage) 交互测试: IP-01, IP-03, IP-10, IP-11, IP-13, IP-14, IP-15。"""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton

from fsa.core.models.rule import Severity
from fsa.gui.main_window import MainWindow
from fsa.gui.widgets.report_card import ReportCard
from fsa.gui.widgets.result_card import ResultCard
from tests.gui.helpers import make_result, make_summary

_TEST_ROOT = Path(__file__).resolve().parent
_PROJECT_ROOT = _TEST_ROOT.parent.parent
_MOUTAI_FILE = _PROJECT_ROOT / "tests" / "fixtures" / "real_reports" / "贵州茅台_2023年报_三大报表.xlsx"
pytestmark = pytest.mark.skipif(
    not _MOUTAI_FILE.exists(),
    reason="真实年报 fixture 缺失（合规红线：已移出 git，需手动放置）",
)



class TestImportRealFile:
    """测试真实文件导入 (IP-01, IP-03, IP-14)。"""

    def test_import_moutai_creates_three_report_cards(self, qapp, qtbot, app_state) -> None:
        """导入茅台文件后出现 3 张 ReportCard (IP-01)。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        window._import_page._on_file(str(_MOUTAI_FILE))
        qtbot.wait(100)

        cards = window._import_page.findChildren(ReportCard)
        assert len(cards) == 3, f"期望 3 张报表卡片，实际 {len(cards)} 张"

    def test_after_import_drop_zone_hidden(self, qapp, qtbot, app_state) -> None:
        """导入成功后拖放区隐藏 (IP-03)。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        window._import_page._on_file(str(_MOUTAI_FILE))
        qtbot.wait(100)
        assert not window._import_page._drop_zone.isVisible()

    def test_after_import_validate_enabled(self, qapp, qtbot, app_state) -> None:
        """导入成功后校验按钮启用 (IP-03)。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        window._import_page._on_file(str(_MOUTAI_FILE))
        qtbot.wait(100)
        assert window._topbar._validate_btn.isEnabled() is True

    def test_empty_state_hidden_initially(self, qapp, qtbot, app_state) -> None:
        """首页只保留文件选择/拖放区, 旧的空状态虚线框默认隐藏 (IP-14)。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        # 确保在导入页
        window._sidebar._nav_buttons["navImport"].clicked_nav.emit("navImport")
        qtbot.wait(50)
        assert window._import_page._empty_state.isHidden()
        assert not window._import_page._drop_zone.isHidden()

    def test_empty_state_hidden_after_import(self, qapp, qtbot, app_state) -> None:
        """导入后空状态隐藏 (IP-14)。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        window._import_page._on_file(str(_MOUTAI_FILE))
        qtbot.wait(100)
        assert window._import_page._empty_state.isHidden()


class TestResultCardInteractions:
    """测试结果卡片交互 (IP-10, IP-11, IP-13)。"""

    def test_clicking_result_card_toggles_detail(self, qapp, qtbot, app_state) -> None:
        """点击 ResultCard 切换详情可见性 (IP-10)。"""
        result = make_result(
            rule_id="X-001", passed=True, category="A-表内平衡",
            diff=0.0, severity=Severity.ERROR,
        )
        card = ResultCard(result)
        qtbot.addWidget(card)
        initial_expanded = card._expanded

        # 点击卡片主体区域 (非按钮)
        QTest.mouseClick(card, Qt.MouseButton.LeftButton, pos=card.rect().center())
        assert card._expanded != initial_expanded

        # 再点击一次恢复
        QTest.mouseClick(card, Qt.MouseButton.LeftButton, pos=card.rect().center())
        assert card._expanded == initial_expanded

    def test_failed_card_default_expanded(self, qapp, qtbot) -> None:
        """不通过卡片默认展开 (IP-11)。"""
        result = make_result(
            rule_id="X-001", passed=False, diff=5.0,
            severity=Severity.ERROR, category="A-表内平衡",
        )
        card = ResultCard(result)
        qtbot.addWidget(card)
        assert card._expanded is True

    def test_passed_card_default_collapsed(self, qapp, qtbot) -> None:
        """通过卡片默认收起 (IP-11)。"""
        result = make_result(
            rule_id="X-001", passed=True, diff=0.0,
            severity=Severity.ERROR, category="A-表内平衡",
        )
        card = ResultCard(result)
        qtbot.addWidget(card)
        assert card._expanded is False

    def test_diagnose_button_emits_signal(self, qapp, qtbot, app_state) -> None:
        """点击 AI 诊断按钮发出 diagnose_requested 信号 (IP-13)。"""
        # 使用 MainWindow 测试完整信号链路
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        app_state.load_registry()

        results = [
            make_result(
                "A-001", passed=False, diff=5.0,
                severity=Severity.ERROR, category="A-表内平衡",
            ),
        ]
        app_state.set_results(make_summary(results), persist=False)

        # 找到 ResultCard 中的 AI 诊断按钮
        cards = window._import_page.findChildren(ResultCard)
        assert len(cards) == 1
        diagnose_btn = cards[0].findChild(QPushButton, "DiagnoseBtn")
        assert diagnose_btn is not None

        QTest.mouseClick(diagnose_btn, Qt.MouseButton.LeftButton)
        # 验证抽屉已打开
        assert not window._agent_drawer.isHidden()


class TestHistoryFilterRegression:
    """测试历史查看后筛选无弹窗闪现 (IP-15 回归)。"""

    def test_filter_after_view_history_no_popup_flash(self, qapp, qtbot, app_state) -> None:
        """查看历史后点击筛选按钮不产生新顶级窗口 (IP-15)。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        app_state.load_registry()

        # 先导入并校验以产生历史记录
        window._import_page._on_file(str(_MOUTAI_FILE))
        qtbot.wait(100)
        window._topbar.validate_clicked.emit()
        qtbot.wait(100)

        # 获取历史记录 ID
        repo = app_state.history_repo
        assert repo is not None
        records = repo.get_recent(limit=1)
        assert len(records) == 1
        history_id = records[0]["id"]

        # 查看历史 (模拟 _on_view_history)
        window._on_view_history(history_id)
        qtbot.wait(100)

        # 记录当前顶级窗口数量
        app = QApplication.instance()
        assert isinstance(app, QApplication)
        initial_top_levels = set(app.topLevelWidgets())

        # 点击各个筛选按钮
        for key in ["all", "error", "warning", "pass"]:
            btn = window._import_page._filter_buttons.get(key)
            if btn is not None and btn.isVisible():
                QTest.mouseClick(btn, qapp.mouseButton())
                qtbot.wait(50)

        # 验证没有新的顶级窗口出现
        current_top_levels = set(app.topLevelWidgets())
        new_widgets = current_top_levels - initial_top_levels
        assert len(new_widgets) == 0, (
            f"历史查看后点击筛选按钮产生了新顶级窗口: {new_widgets}"
        )
