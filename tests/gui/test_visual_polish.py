"""视觉审查补篇 V1-V5 修复回归测试 (审查报告-2026-08-16)。

- V1: AI 抽屉左侧 1px 分隔线 (border_strong 令牌, 明暗主题)
- V2: 建议气泡行距放宽 (垂直 8px)
- V3: 导入页拖放区图标引导 + 审计页空状态「去导入」按钮
- V5: 历史页人性化时间格式 + 规则页搜索匹配计数
(V4 导入失败文案精简的用例在 tests/importer/test_import_page_batch.py)
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

from qfluentwidgets import IconWidget, InfoBarPosition

from fsa.gui.main_window import MainWindow
from fsa.gui.pages.audit_page import AuditPage
from fsa.gui.pages.history_page import HistoryPage, _format_history_time
from fsa.gui.pages.rule_page import RulePage
from fsa.gui.pages.settings_page import SettingsPage
from fsa.gui.theme import get_qss
from fsa.gui.widgets.agent_drawer import AgentDrawer
from fsa.gui.widgets.drop_zone import DropZone
from tests.gui.helpers import make_result, make_summary


class TestDrawerSeparator:
    """V1: 抽屉与主内容区的层次边界。"""

    def test_light_qss_drawer_border_left_uses_border_strong(self) -> None:
        """浅色主题: AgentDrawer 左侧 1px 分隔线用 border_strong 令牌色。"""
        qss = get_qss(dark=False)
        assert "QFrame#AgentDrawer" in qss
        assert "border-left: 1px solid #d1d5db;" in qss

    def test_dark_qss_drawer_border_left_uses_border_strong(self) -> None:
        """深色主题: AgentDrawer 左侧 1px 分隔线随主题切换。"""
        qss = get_qss(dark=True)
        assert "border-left: 1px solid #3f3f46;" in qss


class TestSuggestionSpacing:
    """V2: 建议气泡行距。"""

    def test_suggestions_layout_vertical_spacing_relaxed(self, qapp, qtbot) -> None:
        """建议气泡网格垂直间距放宽到 8px (4px 基准)。"""
        drawer = AgentDrawer(chat_repo=None)
        qtbot.addWidget(drawer)
        assert drawer._suggestions_layout.verticalSpacing() == 8


class TestDropZoneGuidance:
    """V3: 导入页拖放区空状态引导。"""

    def test_drop_zone_has_icon_and_text_hierarchy(self, qapp, qtbot) -> None:
        """拖放区含大图标 + 主/次两层文案。"""
        zone = DropZone()
        qtbot.addWidget(zone)
        icon = zone.findChild(IconWidget, "DropZoneIcon")
        assert icon is not None
        assert icon.width() >= 36

    def test_drop_zone_keeps_main_and_sub_text(self, qapp, qtbot) -> None:
        """主文案与格式说明次文案均在。"""
        from PySide6.QtWidgets import QLabel

        zone = DropZone()
        qtbot.addWidget(zone)
        texts = {label.objectName(): label.text() for label in zone.findChildren(QLabel)}
        assert "点击选择文件" in texts["DropZoneText"]
        assert ".xlsx" in texts["DropZoneHint"]
        assert ".pdf" in texts["DropZoneHint"]


class TestAuditPageEmptyState:
    """V3: 审计页空状态「去导入」按钮。"""

    def test_empty_state_shows_go_import_button(self, qapp, qtbot, app_state) -> None:
        """无校验结果时显示「去导入」按钮。"""
        page = AuditPage(app_state)
        qtbot.addWidget(page)
        assert not page._go_import_btn.isHidden()
        assert page._go_import_btn.text() == "去导入"

    def test_go_import_button_hidden_after_results(self, qapp, qtbot, app_state) -> None:
        """有校验结果后按钮隐藏。"""
        page = AuditPage(app_state)
        qtbot.addWidget(page)
        app_state.set_results(make_summary([make_result()]))
        assert not page._go_import_btn.isVisible()

    def test_go_import_button_emits_signal(self, qapp, qtbot, app_state) -> None:
        """点击按钮发出 go_import_requested 信号。"""
        page = AuditPage(app_state)
        qtbot.addWidget(page)
        emitted: list[bool] = []
        page.go_import_requested.connect(lambda: emitted.append(True))
        page._go_import_btn.click()
        assert emitted == [True]

    def test_main_window_navigates_to_import_page(self, qapp, qtbot, app_state) -> None:
        """主窗口接线: 信号触发后切换到数据导入页。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        window._on_nav("navAudit")
        window._audit_page.go_import_requested.emit()
        assert window._get_current_nav() == "navImport"


class TestHistoryTimeFormat:
    """V5: 历史页时间人性化显示。"""

    def test_today_shows_relative_time(self) -> None:
        """当天记录显示「今天 HH:mm」。"""
        now = datetime(2026, 8, 16, 15, 30)
        assert _format_history_time("2026-08-16 09:05:00", now) == "今天 09:05"

    def test_same_year_shows_month_day(self) -> None:
        """当年非当天显示「MM-dd HH:mm」。"""
        now = datetime(2026, 8, 16, 15, 30)
        assert _format_history_time("2026-03-02 08:00:00", now) == "03-02 08:00"

    def test_earlier_year_shows_full_date(self) -> None:
        """更早年份显示完整日期。"""
        now = datetime(2026, 8, 16, 15, 30)
        assert _format_history_time("2025-12-31 23:59:00", now) == "2025-12-31"

    def test_unparseable_returns_raw(self) -> None:
        """无法解析的时间原样返回 (不崩溃)。"""
        assert _format_history_time("未知时间") == "未知时间"


class TestRulePageSearchCount:
    """V5: 规则页搜索结果计数。"""

    def test_search_shows_match_count(self, qapp, qtbot, app_state) -> None:
        """搜索后统计标签前置「搜索匹配 N 条」。"""
        page = RulePage(app_state)
        qtbot.addWidget(page)
        page._on_search("测试规则")
        assert page._summary.text().startswith("搜索匹配 3 条")

    def test_no_search_hides_match_count(self, qapp, qtbot, app_state) -> None:
        """无搜索词时保持原统计文案。"""
        page = RulePage(app_state)
        qtbot.addWidget(page)
        assert "搜索匹配" not in page._summary.text()


class TestDatePickerModern:
    """导入页报告期间日期选择器 (PeriodPicker 复合控件)。"""

    def test_period_input_is_period_picker_with_calendar(
        self, qapp, qtbot, app_state,
    ) -> None:
        """期间控件为 PeriodPicker (文本框+日历箭头按钮), 对象名保持 StyledDateEdit。

        修复背景: QDateEdit 的下拉按钮/箭头依赖 QSS 子控件渲染, 在部分
        Windows 环境不可靠, 改为 QLineEdit+ArrowButton+QCalendarWidget 实现。
        """
        from fsa.gui.widgets.period_picker import PeriodPicker

        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        date_edit = window._import_page._period_input
        assert isinstance(date_edit, PeriodPicker)
        assert date_edit.objectName() == "StyledDateEdit"
        assert date_edit.date().isValid()
        # 日历按钮存在且可点 (点击后弹日历, 此处只验证控件存在)
        assert date_edit._btn is not None
        assert not date_edit._btn.isHidden()


class TestMultiEntityButtonStyle:
    """多主体批量校验按钮风格统一为次级按钮。"""

    def test_multi_entity_button_is_secondary_with_fixed_height(
        self, qapp, qtbot, app_state,
    ) -> None:
        """按钮对象名为 BtnSecondary 且高度固定 32px。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        btn = window._import_page._multi_entity_btn
        assert btn.objectName() == "BtnSecondary"
        assert btn.minimumSize().height() == 32
        assert btn.maximumSize().height() == 32


class TestSettingsInfoBar:
    """设置页保存提示改为浮动 InfoBar。"""

    def test_notify_saved_uses_top_right_infobar(
        self, qapp, qtbot, app_state,
    ) -> None:
        """_notify_saved 调用 InfoBar.success 并定位在右上角。"""
        page = SettingsPage(app_state)
        qtbot.addWidget(page)
        with patch("fsa.gui.pages.settings_page.InfoBar.success") as mock_success:
            page._notify_saved()
        mock_success.assert_called_once()
        kwargs = mock_success.call_args.kwargs
        assert kwargs.get("position") == InfoBarPosition.TOP_RIGHT


class TestHistoryDeleteButtonStyle:
    """历史页删除全部按钮使用 DangerBtn 描边样式。"""

    def test_delete_all_button_is_danger(self, qapp, qtbot, app_state) -> None:
        """删除全部按钮对象名为 DangerBtn。"""
        page = HistoryPage(app_state)
        qtbot.addWidget(page)
        assert page._delete_all_btn.objectName() == "DangerBtn"


class TestFilterTabActiveQss:
    """FilterTab 选中态使用品牌色令牌。"""

    def test_light_filter_tab_active_uses_brand_50(self) -> None:
        """浅色主题选中态背景为 brand-50。"""
        qss = get_qss(dark=False)
        assert 'QPushButton#FilterTab[active="true"]' in qss
        assert "background-color: #eef2ff;" in qss

    def test_dark_filter_tab_active_uses_brand_50(self) -> None:
        """深色主题选中态背景为暗色 brand-50。"""
        qss = get_qss(dark=True)
        assert 'QPushButton#FilterTab[active="true"]' in qss
        assert "background-color: #1e1b4b;" in qss
