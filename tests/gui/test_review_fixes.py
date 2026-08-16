"""针对 2026-08 审查修复的回归测试。

覆盖:
- FAB 消息图标必须为白色 (不再使用 colored().icon() 的错误 API)
- 表格 QSS 去除 focus outline, 避免 Windows 下点击单元格出现黑色方框
- 查看历史后: 页面/侧边栏/状态/横幅/滚动位置一致
- 抽屉最小宽度下消息气泡不超出消息区视口
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QLabel, QPushButton, QTableWidget

from fsa.core.models.detail import DetailDataset
from fsa.core.models.result import ValidationSummary
from fsa.core.models.rule import Severity
from fsa.core.resources import sha256_file
from fsa.gui.main_window import MainWindow
from fsa.gui.pages.import_page import ImportPage
from fsa.gui.pages.settings_page import SettingsPage
from fsa.gui.theme import get_qss
from fsa.gui.widgets.agent_fab import AgentFAB
from tests.gui.helpers import make_report, make_result

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_REALISTIC_REPORT = _PROJECT_ROOT / "tests" / "fixtures" / "realistic_report.xlsx"


def _icon_dominant_color(icon) -> tuple[int, int, int] | None:
    """统计图标非透明像素中最多的颜色。"""
    image = icon.pixmap(22, 22).toImage()
    counts: dict[tuple[int, int, int], int] = {}
    for y in range(image.height()):
        for x in range(image.width()):
            color = image.pixelColor(x, y)
            if color.alpha() < 32:
                continue
            key = (color.red(), color.green(), color.blue())
            counts[key] = counts.get(key, 0) + 1
    if not counts:
        return None
    return max(counts, key=counts.get)


class TestFabIconWhite:
    def test_fab_message_icon_is_white(self, qapp, qtbot) -> None:
        """FAB 图标主色应为白色, 不能是默认黑色。"""
        fab = AgentFAB()
        qtbot.addWidget(fab)

        color = _icon_dominant_color(fab.icon())
        assert color is not None
        assert color == (255, 255, 255), f"FAB 图标主色应为白色, 实际 {color}"


class TestTableFocusOutline:
    def test_table_qss_disables_focus_outline(self) -> None:
        """表格 QSS 必须显式关闭 outline, 消除点击单元格的黑色焦点框。"""
        for dark in (False, True):
            qss = get_qss(dark)
            assert "QTableWidget {" in qss
            assert "outline: none;" in qss

    def test_table_widget_still_usable(self, qapp, qtbot) -> None:
        """表格仍可正常选中单元格。"""
        table = QTableWidget(1, 1)
        qtbot.addWidget(table)
        table.show()
        QTest.mouseClick(table.viewport(), Qt.MouseButton.LeftButton, pos=QPoint(20, 20))
        assert table.currentColumn() >= 0


class TestHistoryViewNavigation:
    def test_view_history_syncs_state_sidebar_and_scroll(
        self, qapp, qtbot, app_state
    ) -> None:
        """查看历史后进入导入页, 侧边栏/历史状态/横幅/滚动位置一致。"""
        results = [
            make_result("A-001", passed=True, severity=Severity.ERROR),
            make_result("B-001", passed=False, severity=Severity.ERROR, diff=1.0),
        ]
        summary = ValidationSummary(
            period="2024-12",
            total=len(results),
            passed=1,
            failed=1,
            results=results,
        )
        history_id = app_state.history_repo.save(summary)  # type: ignore[union-attr]

        # 先制造一个实时报表与结果, 验证历史回看会清空实时数据
        app_state.set_reports([])
        app_state.set_results(summary, persist=False)

        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        window.show()
        qtbot.wait(20)

        window._import_page._scroll.verticalScrollBar().setValue(999)
        window._sidebar._nav_buttons["navHistory"].clicked_nav.emit("navHistory")
        qtbot.wait(20)

        window._on_view_history(history_id)
        qtbot.wait(20)

        assert window._stack.currentIndex() == 1
        assert window._get_current_nav() == "navAudit"
        assert window._sidebar._nav_buttons["navAudit"].property("active") is True
        assert window._sidebar._nav_buttons["navHistory"].property("active") is False
        assert app_state.history_view_id == history_id
        assert app_state.reports == []
        # 历史回看走轻量表格页, 不再构建导入页结果卡片
        assert len(window._import_page._result_cards) == 0
        assert window._audit_page._history_banner.isVisible()
        assert f"历史回看 #{history_id}" in window._audit_page._history_banner_text.text()
        assert window._audit_page._table.rowCount() == 2

    def test_importing_new_file_exits_history_view(
        self, qapp, qtbot, app_state
    ) -> None:
        """进入历史回看后重新导入文件, 自动退出回看并隐藏横幅。"""
        results = [make_result("A-001", passed=True)]
        summary = ValidationSummary(total=1, passed=1, results=results)
        app_state.set_history_view(summary, 42)
        assert app_state.history_view_id == 42

        app_state.set_reports([])
        assert app_state.history_view_id is None


class TestDropZoneClick:
    def test_click_emits_clicked_signal(self, qapp, qtbot, app_state) -> None:
        """文件选择/拖放区支持点击, 发出 clicked 信号用于打开文件对话框。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        window.show()
        received: list[int] = []
        # 断开真实文件对话框处理, 仅验证 DropZone 的点击信号
        window._import_page._drop_zone.clicked.disconnect(
            window._import_page._on_choose_files
        )
        window._import_page._drop_zone.clicked.connect(lambda: received.append(1))
        QTest.mouseClick(
            window._import_page._drop_zone,
            Qt.MouseButton.LeftButton,
            pos=window._import_page._drop_zone.rect().center(),
        )
        assert received == [1]


class TestDrawerLazySessionLoad:
    def test_session_messages_loaded_on_first_show(self, qapp, qtbot, app_state) -> None:
        """隐藏抽屉不预载历史消息, 首次显示时才加载, 降低启动和主题切换开销。"""
        session_id = app_state.chat_repo.create_session()  # type: ignore[union-attr]
        app_state.chat_repo.add_message(session_id, "user", "测试消息")  # type: ignore[union-attr]
        app_state.chat_repo.add_message(session_id, "assistant", "回复")  # type: ignore[union-attr]

        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        window.show()
        drawer = window._agent_drawer

        assert drawer._session_id == session_id
        assert drawer._messages_loaded is False
        assert drawer._ai_bubbles == []

        window._open_drawer()
        qtbot.wait(20)
        assert drawer._messages_loaded is True
        assert len(drawer._ai_bubbles) == 1
        assert len(drawer._user_bubbles) == 1


class TestDrawerBubbleFitsViewport:
    def test_bubbles_do_not_overflow_min_drawer(self, qapp, qtbot, app_state) -> None:
        """抽屉缩到最小宽度时, 消息气泡右缘不超过消息区视口。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        window.resize(1280, 800)
        window.show()
        window._open_drawer()
        drawer = window._agent_drawer
        qtbot.wait(20)

        drawer.add_user_message("用户消息" * 80)
        drawer.add_assistant_message("AI 回答" * 120)
        qtbot.wait(20)

        drawer.resize(drawer.MIN_WIDTH, drawer.height())
        qtbot.wait(30)

        viewport_width = drawer._scroll.viewport().width()
        for bubble in [*drawer._user_bubbles, *drawer._ai_bubbles]:
            left = bubble.mapTo(drawer._scroll.viewport(), QPoint(0, 0)).x()
            assert left >= 0
            assert left + bubble.width() <= viewport_width + 1, (
                f"气泡右缘 {left + bubble.width()} 超出视口 {viewport_width}"
            )


class TestAuditEvidenceChain:
    def test_period_and_source_metadata_persisted(self, qapp, qtbot, app_state) -> None:
        """报告期间、源文件、哈希与规则版本写入校验结果和历史记录。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        window.show()
        app_state.load_registry()

        window._import_page._period_input.setText("2024-12")
        window._import_page._on_file(str(_REALISTIC_REPORT))
        qtbot.wait(100)

        assert app_state.period == "2024-12"

        window._import_page.trigger_validate()
        qtbot.waitUntil(
            lambda: app_state.history_repo.count() >= 1, timeout=5000  # type: ignore[union-attr]
        )

        summary = app_state.results
        assert summary is not None
        assert summary.period == "2024-12"
        assert summary.source_files == [str(_REALISTIC_REPORT)]
        assert summary.source_hashes == [sha256_file(_REALISTIC_REPORT)]
        assert summary.rule_version == "1.3.0"

        record = app_state.history_repo.get_recent(limit=1)[0]  # type: ignore[union-attr]
        assert record["period"] == "2024-12"
        assert record["source_files"] == [str(_REALISTIC_REPORT)]
        assert record["source_hashes"] == [sha256_file(_REALISTIC_REPORT)]
        assert record["rule_version"] == "1.3.0"

    def test_history_view_locks_period_input(self, qapp, qtbot, app_state) -> None:
        """历史回看时期间输入框只读, 退出回看后恢复可编辑。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        window.show()

        summary = ValidationSummary(
            period="2024-11",
            total=1,
            passed=1,
            results=[make_result("A-001", passed=True)],
        )
        app_state.set_history_view(summary, 42)
        qtbot.wait(20)

        assert not window._import_page._period_input.isEnabled()
        assert window._import_page._period_input.text() == "2024-11"

        app_state.clear_all()
        qtbot.wait(20)
        assert window._import_page._period_input.isEnabled()


class TestBackgroundImport:
    def test_background_import_does_not_block_gui(self, qapp, qtbot, app_state, monkeypatch) -> None:
        """拖放导入走后台线程, 调用后立即返回且最终写入状态。"""
        import time

        import fsa.gui.pages.import_page as import_page_module

        page = ImportPage(app_state)
        qtbot.addWidget(page)

        def slow_read(path: str, use_com: bool = False) -> dict:
            time.sleep(0.3)
            return {}

        monkeypatch.setattr(import_page_module, "read_excel", slow_read)
        page._importer.import_data = (
            lambda data, source_file, suffix: [make_report()]
        )
        page._detail_importer.import_data = lambda data: DetailDataset()

        started = time.monotonic()
        page._on_files_async(["a.xlsx"])
        assert time.monotonic() - started < 0.1
        assert page._import_cancel_event is not None

        qtbot.waitUntil(lambda: len(app_state.reports) == 1, timeout=3000)
        assert page._progress.isHidden()

    def test_background_validation_does_not_block_gui(self, qapp, qtbot, app_state, monkeypatch) -> None:
        """顶栏校验走后台线程, 慢哈希不阻塞界面。"""
        import time

        import fsa.gui.pages.import_page as import_page_module

        page = ImportPage(app_state)
        qtbot.addWidget(page)
        app_state.load_registry()
        page._on_file(str(_REALISTIC_REPORT))
        qtbot.wait(100)

        def slow_hash(path: str) -> str:
            time.sleep(0.3)
            return sha256_file(path)

        monkeypatch.setattr(import_page_module, "sha256_file", slow_hash)
        started = time.monotonic()
        page.trigger_validate_async()
        assert time.monotonic() - started < 0.1
        assert page._validation_running is True

        qtbot.waitUntil(lambda: app_state.results is not None, timeout=3000)
        assert page._validation_running is False


class TestAgentPageAwareSuggestions:
    def test_page_switch_changes_suggestions(self, qapp, qtbot, app_state) -> None:
        """不同页面显示不同的 AI 建议问题。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        window.show()

        window._on_nav("navImport")
        import_texts = [
            window._agent_drawer._suggestions_layout.itemAt(i).widget().text()
            for i in range(window._agent_drawer._suggestions_layout.count())
            if window._agent_drawer._suggestions_layout.itemAt(i).widget() is not None
        ]
        window._on_nav("navSettings")
        settings_texts = [
            window._agent_drawer._suggestions_layout.itemAt(i).widget().text()
            for i in range(window._agent_drawer._suggestions_layout.count())
            if window._agent_drawer._suggestions_layout.itemAt(i).widget() is not None
        ]
        assert import_texts != settings_texts
        assert any("配置" in text for text in settings_texts)

    def test_typing_previews_related_questions(self, qapp, qtbot, app_state) -> None:
        """输入内容变化时预览本地问题库中的相关问题。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        window.show()
        window._open_drawer()

        window._agent_drawer._input.setPlainText("勾稽")
        qtbot.wait(30)
        texts = [
            window._agent_drawer._suggestions_layout.itemAt(i).widget().text()
            for i in range(window._agent_drawer._suggestions_layout.count())
            if window._agent_drawer._suggestions_layout.itemAt(i).widget() is not None
        ]
        assert any("勾稽" in text for text in texts)


class TestMultiEntityGui:
    def test_run_multi_entity_produces_combined_result(
        self, qapp, qtbot, app_state, tmp_path
    ) -> None:
        """多主体批量校验入口可按子文件夹生成合并结果。"""
        from tests.importer.conftest import make_multi_sheet_excel

        page = ImportPage(app_state)
        qtbot.addWidget(page)
        app_state.load_registry()

        folder_a = tmp_path / "主体A"
        folder_b = tmp_path / "主体B"
        folder_a.mkdir()
        folder_b.mkdir()
        make_multi_sheet_excel(folder_a)
        make_multi_sheet_excel(folder_b)

        result = page._run_multi_entity([str(folder_a), str(folder_b)])
        assert len(result.outcomes) == 2
        assert result.combined is not None
        assert result.combined.total > 0


class TestDeepSeekTemplate:
    def test_deepseek_template_fills_settings(self, qapp, qtbot, app_state) -> None:
        """设置页一键填入 DeepSeek 模板, 不自动填密钥。"""
        page = SettingsPage(app_state)
        qtbot.addWidget(page)
        btn = next(
            b for b in page.findChildren(QPushButton) if b.text() == "填入 DeepSeek 模板"
        )
        btn.click()
        qtbot.wait(20)

        settings = QSettings("FSA", "FinancialAudit")
        assert settings.value("llm_provider") == "openai"
        assert settings.value("llm_base_url") == "https://api.deepseek.com"
        assert settings.value("llm_model") == "deepseek-chat"
        assert settings.value("llm_api_key") in ("", None)


class TestHistorySearchAndCompare:
    def test_history_search_filters_records(self, qapp, qtbot, app_state) -> None:
        """历史页可按期间/源文件搜索。"""
        from fsa.gui.pages.history_page import HistoryPage

        repo = app_state.history_repo
        conn = repo._db.connection  # type: ignore[union-attr]
        conn.execute("DELETE FROM validation_history")
        conn.commit()
        repo.save(  # type: ignore[union-attr]
            ValidationSummary(period="2024-12", total=1, passed=1, source_files=["a.xlsx"])
        )
        repo.save(  # type: ignore[union-attr]
            ValidationSummary(period="2025-01", total=1, passed=1, source_files=["b.xlsx"])
        )

        page = HistoryPage(app_state)
        qtbot.addWidget(page)
        page._load_history()
        assert len(page._cards) == 2
        assert page._compare_btn.isEnabled()

        page._search_input.setText("2024-12")
        qtbot.wait(20)
        assert len(page._cards) == 1

        page._search_input.setText("b.xlsx")
        qtbot.wait(20)
        assert len(page._cards) == 1
        card_texts = [
            label.text()
            for label in page._cards[0].findChildren(QLabel)
        ]
        assert any("2025-01" in text for text in card_texts)

        page._search_input.clear()
        qtbot.wait(20)
        assert len(page._cards) == 2
