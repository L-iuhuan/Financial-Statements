"""SettingsPage 设置页测试。"""

from __future__ import annotations

from PySide6.QtCore import QSettings

from fsa.gui.pages.settings_page import SettingsPage


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
