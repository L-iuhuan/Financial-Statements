"""SettingsPage 设置页测试。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from PySide6.QtCore import QSettings

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
            QMessageBox, "question",
            lambda *args, **kwargs: QMessageBox.StandardButton.No,
        ):
            page._reset_to_defaults()

        assert settings.value("history_retention_days") == "180"

    def test_reset_confirmed_restores_defaults(self, qapp, qtbot, app_state) -> None:
        """确认框选"是"时恢复默认值。"""
        from PySide6.QtWidgets import QMessageBox

        settings = QSettings("FSA", "FinancialAudit")
        settings.setValue("history_retention_days", "180")
        page = SettingsPage(app_state)
        qtbot.addWidget(page)

        with patch.object(
            QMessageBox, "question",
            lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
        ):
            page._reset_to_defaults()

        assert settings.value("history_retention_days") == "90"
        assert settings.value("default_tolerance") == "0.01"


class TestSettingsPersistence:
    """测试 QSettings 持久化。"""

    def test_theme_mode_saved(self, qapp, qtbot, app_state) -> None:
        page = SettingsPage(app_state)
        qtbot.addWidget(page)
        page._set_theme("dark")

        settings = QSettings("FSA", "FinancialAudit")
        assert settings.value("theme_mode") == "dark"

    def test_tolerance_saved(self, qapp, qtbot, app_state) -> None:
        page = SettingsPage(app_state)
        qtbot.addWidget(page)
        page._tolerance_input.setText("5.00")
        page._save_tolerance()

        settings = QSettings("FSA", "FinancialAudit")
        assert settings.value("default_tolerance") == "5.00"
        assert app_state.default_tolerance == 5.0

    def test_threshold_saved(self, qapp, qtbot, app_state) -> None:
        page = SettingsPage(app_state)
        qtbot.addWidget(page)
        page._threshold_input.setText("50")
        page._save_threshold()

        settings = QSettings("FSA", "FinancialAudit")
        assert settings.value("gross_margin_threshold") == "50"

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
        settings.setValue("default_tolerance", "1.50")
        settings.setValue("gross_margin_threshold", "25")
        settings.setValue("history_retention_days", "60")

        page = SettingsPage(app_state)
        qtbot.addWidget(page)

        assert page.get_theme_mode() == "auto"
        assert page._tolerance_input.text() == "1.50"
        assert page._threshold_input.text() == "25"
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

    def test_save_update_url_calls_sync(self, qapp, qtbot, app_state) -> None:
        """保存更新清单地址时调用 settings.sync() (B-11)。"""
        page = SettingsPage(app_state)
        qtbot.addWidget(page)
        with patch.object(page._settings, "sync") as mock_sync:
            page._update_url_input.setText("http://192.168.1.5/version.json")
            page._save_update_url()
        assert (
            page._settings.value("update_manifest_url")
            == "http://192.168.1.5/version.json"
        )
        mock_sync.assert_called_once()


class TestAboutSection:
    """关于分区: 规则库版本串动态读取。"""

    def test_rule_library_label_shows_registry_count(self, qapp, app_state) -> None:
        """有 registry 时显示条数, 条数与注册表一致。"""
        label = _rule_library_label(app_state)
        assert "CAS" in label
        assert f"{app_state.registry.count()} 条规则" in label

    def test_rule_library_label_no_registry_omits_count(self, qapp) -> None:
        """无 registry 时降级, 不显示条数。"""
        state = SimpleNamespace(registry=None)
        label = _rule_library_label(state)
        assert "条规则" not in label
        assert label  # 非空, 仍有可读文案
