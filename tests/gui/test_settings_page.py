"""SettingsPage 设置页测试。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QLabel

from fsa.gui.pages.settings_page import SettingsPage
from fsa.gui.pages.settings_sections import _rule_library_label


class TestResetToDefaultsConfirm:
    """测试恢复默认设置的二次确认 (C5-4)。"""

    def test_reset_cancelled_keeps_settings(self, qapp, qtbot, app_state) -> None:
        """确认框选"否"时不重置任何设置。"""
        from PySide6.QtWidgets import QMessageBox

        settings = QSettings("FSA", "FinancialAudit")
        settings.setValue("history_retention_days", "180")
        page = SettingsPage(app_state)
        qtbot.addWidget(page)

        with patch.object(
            QMessageBox,
            "question",
            lambda *args, **kwargs: QMessageBox.StandardButton.No,
        ):
            page._reset_to_defaults()

        assert settings.value("history_retention_days") == "180"

    def test_reset_confirmed_restores_defaults(self, qapp, qtbot, app_state) -> None:
        """确认框选"是"时恢复默认值。"""
        from PySide6.QtWidgets import QMessageBox

        settings = QSettings("FSA", "FinancialAudit")
        settings.setValue("history_retention_days", "180")
        settings.setValue("industry", "retail")
        page = SettingsPage(app_state)
        qtbot.addWidget(page)

        with patch.object(
            QMessageBox,
            "question",
            lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
        ):
            page._reset_to_defaults()

        assert settings.value("history_retention_days") == "90"
        assert settings.value("industry") == "general"

    def test_reset_clears_tolerance_overrides(self, qapp, qtbot, app_state) -> None:
        """恢复默认时清除规则页逐条容差覆写并重放注册表默认值 (B3-2)。"""
        import pytest
        from PySide6.QtWidgets import QMessageBox

        repo = app_state.override_repo
        if repo is None:
            pytest.skip("测试环境持久化不可用")
        repo.set("A-001", 5.0)
        app_state.registry.set_tolerance("A-001", 5.0)
        override = repo.get_all()["A-001"]
        assert override.tolerance == 5.0

        page = SettingsPage(app_state)
        qtbot.addWidget(page)
        with patch.object(
            QMessageBox,
            "question",
            lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
        ):
            page._reset_to_defaults()

        assert repo.get_all() == {}
        # 注册表已重载, 逐条覆写不再残留
        assert all(
            rule.tolerance != 5.0 for rule in app_state.registry.get_all()
        )


class TestSettingsPersistence:
    """测试 QSettings 持久化。"""

    def test_theme_mode_saved(self, qapp, qtbot, app_state) -> None:
        page = SettingsPage(app_state)
        qtbot.addWidget(page)
        page._set_theme("dark")

        settings = QSettings("FSA", "FinancialAudit")
        assert settings.value("theme_mode") == "dark"

    def test_industry_saved(self, qapp, qtbot, app_state) -> None:
        """选择行业后写入 QSettings 键 industry (P1-7/8)。"""
        page = SettingsPage(app_state)
        qtbot.addWidget(page)
        index = page._industry_combo.findData("retail")
        page._industry_combo.setCurrentIndex(index)
        page._save_industry()

        settings = QSettings("FSA", "FinancialAudit")
        assert settings.value("industry") == "retail"

    def test_dead_settings_removed(self, qapp, qtbot, app_state) -> None:
        """死设置「默认容差/毛利率波动阈值」控件已删除 (P1-6)。"""
        page = SettingsPage(app_state)
        qtbot.addWidget(page)
        assert not hasattr(page, "_tolerance_input")
        assert not hasattr(page, "_threshold_input")

    def test_days_saved(self, qapp, qtbot, app_state) -> None:
        page = SettingsPage(app_state)
        qtbot.addWidget(page)
        page._days_input.setText("180")
        page._save_days()

        settings = QSettings("FSA", "FinancialAudit")
        assert settings.value("history_retention_days") == "180"

    def test_load_settings_applies_to_ui(self, qapp, qtbot, app_state) -> None:
        settings = QSettings("FSA", "FinancialAudit")
        settings.setValue("theme_mode", "auto")
        settings.setValue("industry", "retail")
        settings.setValue("history_retention_days", "60")

        page = SettingsPage(app_state)
        qtbot.addWidget(page)

        assert page.get_theme_mode() == "auto"
        assert page._industry_combo.currentData() == "retail"
        assert page._days_input.text() == "60"

    def test_is_dark_theme_light(self, qapp, qtbot, app_state) -> None:
        page = SettingsPage(app_state)
        qtbot.addWidget(page)
        page._set_theme("light")
        assert page.is_dark_theme() is False

    def test_is_dark_theme_dark(self, qapp, qtbot, app_state) -> None:
        page = SettingsPage(app_state)
        qtbot.addWidget(page)
        page._set_theme("dark")
        assert page.is_dark_theme() is True

    def test_theme_buttons_follow_external_theme_change(self, qapp, qtbot, app_state) -> None:
        """页面已打开时, 外部主题切换(顶栏/Ctrl+D)立即同步按钮高亮。"""
        from fsa.gui.theme import notify_theme_listeners

        settings = QSettings("FSA", "FinancialAudit")
        settings.setValue("theme_mode", "light")
        page = SettingsPage(app_state)
        qtbot.addWidget(page)

        assert page._light_btn.property("active") is True
        assert page._dark_btn.property("active") is False

        settings.setValue("theme_mode", "dark")
        notify_theme_listeners()

        assert page._light_btn.property("active") is False
        assert page._dark_btn.property("active") is True

    def test_save_update_url_calls_sync(self, qapp, qtbot, app_state) -> None:
        """保存更新清单地址时调用 settings.sync() (B-11)。"""
        page = SettingsPage(app_state)
        qtbot.addWidget(page)
        with patch.object(page._settings, "sync") as mock_sync:
            page._update_url_input.setText("http://192.168.1.5/version.json")
            page._save_update_url()
        assert page._settings.value("update_manifest_url") == "http://192.168.1.5/version.json"
        mock_sync.assert_called_once()


class TestAboutSection:
    """关于分区: 版本摘要与规则库版本串动态读取。"""

    def test_version_summary_shows_version_and_channel(self, qapp, qtbot, app_state) -> None:
        """关于区顶部显示「版本 0.4.1 · 通用版/内部版」摘要行。"""
        from fsa.core.edition import get_edition_config
        from fsa.core.version import APP_VERSION

        page = SettingsPage(app_state)
        qtbot.addWidget(page)

        summary = page.findChild(QLabel, "AboutVersionSummary")
        assert summary is not None
        expected = f"版本 {APP_VERSION} · {get_edition_config().display_name}"
        assert summary.text() == expected

    def test_rule_library_label_shows_registry_count(self, qapp, app_state) -> None:
        """有 registry 时显示条数, 条数与注册表一致。"""
        label = _rule_library_label(app_state)
        assert "CAS" in label
        assert f"{app_state.registry.count()} 条规则" in label

    def test_rule_library_label_no_registry_omits_count(self, qapp) -> None:
        """无 registry 时降级, 不显示条数。"""
        state = SimpleNamespace(registry=None)
        label = _rule_library_label(state)  # type: ignore[arg-type]
        assert "条规则" not in label
        assert label  # 非空, 仍有可读文案


class TestLlmQuickTemplates:
    """DeepSeek / 智谱 GLM 快速模板按钮。"""

    def _click_button(self, qtbot, page: SettingsPage, text: str) -> None:
        from PySide6.QtWidgets import QPushButton

        buttons = page.findChildren(QPushButton, "TextBtn")
        target = next(btn for btn in buttons if btn.text() == text)
        qtbot.mouseClick(target, Qt.MouseButton.LeftButton)

    def test_deepseek_template_fills_openai_compat_fields(self, qapp, qtbot, app_state) -> None:
        page = SettingsPage(app_state)
        qtbot.addWidget(page)
        self._click_button(qtbot, page, "填入 DeepSeek 模板")

        assert page._llm_provider_combo.currentData() == "openai"
        assert page._llm_base_url_input.text() == "https://api.deepseek.com"
        assert page._llm_model_input.text() == "deepseek-chat"

    def test_glm_template_fills_openai_compat_fields(self, qapp, qtbot, app_state) -> None:
        page = SettingsPage(app_state)
        qtbot.addWidget(page)
        self._click_button(qtbot, page, "填入智谱 GLM 模板")

        assert page._llm_provider_combo.currentData() == "openai"
        assert page._llm_base_url_input.text() == ("https://open.bigmodel.cn/api/paas/v4")
        assert page._llm_model_input.text() == "glm-4-plus"
