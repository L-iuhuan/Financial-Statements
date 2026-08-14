"""系统设置页面: 外观/校验参数/数据存储/关于/软件更新。

匹配 Demo v4 设计: 多分区设置面板。
支持 QSettings 持久化: theme_mode, default_tolerance, gross_margin_threshold,
history_retention_days, update_manifest_url。
"""

from __future__ import annotations

from loguru import logger
from PySide6.QtCore import QSettings, Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from fsa.gui.app_state import AppState
from fsa.gui.pages.settings_sections import (
    build_about_section,
    build_appearance_section,
    build_llm_section,
    build_storage_section,
    build_update_section,
    build_validation_section,
)
from fsa.gui.theme import apply_theme, get_qss


class SettingsPage(QWidget):
    """系统设置页面。"""

    theme_changed = Signal(bool)  # type: ignore[name-defined]

    def __init__(self, state: AppState) -> None:
        super().__init__()
        self.setObjectName("SettingsPage")
        self._state = state
        self._settings = QSettings("FSA", "FinancialAudit")
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        content.setObjectName("PageContent")
        layout = QVBoxLayout(content)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # 自动保存提示条 (默认隐藏, 保存时短暂显示)
        self._save_hint = QLabel("已自动保存")
        self._save_hint.setObjectName("SaveHintLabel")
        self._save_hint.setVisible(False)
        layout.addWidget(self._save_hint)
        self._save_hint_timer = None

        layout.addWidget(build_appearance_section(self, self._settings, self._state))
        layout.addWidget(build_validation_section(self, self._settings, self._state))
        layout.addWidget(build_storage_section(self, self._settings, self._state))
        layout.addWidget(build_llm_section(self, self._settings, self._state))
        layout.addWidget(build_update_section(self, self._settings, self._state))
        layout.addWidget(build_about_section(self, self._settings, self._state))

        # 恢复默认按钮
        reset_row = QVBoxLayout()
        reset_btn = QPushButton("恢复默认设置")
        reset_btn.setObjectName("BtnSecondary")
        reset_btn.setFixedHeight(36)
        reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        reset_btn.clicked.connect(self._reset_to_defaults)
        reset_row.addWidget(reset_btn)
        layout.addLayout(reset_row)

        layout.addStretch()

        scroll.setWidget(content)
        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.addWidget(scroll)

    # ── 加载与保存 ──

    def _load_settings(self) -> None:
        """从 QSettings 加载并应用到 UI。"""
        import contextlib

        mode = str(self._settings.value("theme_mode", "light"))
        self._update_theme_buttons(mode)

        tol = str(self._settings.value("default_tolerance", "0.01"))
        self._tolerance_input.setText(tol)
        with contextlib.suppress(ValueError):
            self._state.set_default_tolerance(float(tol))

        thr = str(self._settings.value("gross_margin_threshold", "30"))
        self._threshold_input.setText(thr)

        days = str(self._settings.value("history_retention_days", "90"))
        self._days_input.setText(days)

    def _set_theme(self, mode: str) -> None:
        self._settings.setValue("theme_mode", mode)
        self._settings.sync()
        self._update_theme_buttons(mode)
        dark = self._detect_system_dark() if mode == "auto" else mode == "dark"

        def _apply() -> None:
            apply_theme(dark=dark)
            from PySide6.QtWidgets import QApplication
            app = QApplication.instance()
            if isinstance(app, QApplication):
                app.setStyleSheet(get_qss(dark))

        # 截屏遮罩淡出过渡, 避免瞬间反色闪烁
        from fsa.gui.theme import run_theme_transition
        run_theme_transition(self.window(), _apply)
        self.theme_changed.emit(dark)

    def _update_theme_buttons(self, mode: str) -> None:
        for btn, target in [
            (self._light_btn, "light"),
            (self._dark_btn, "dark"),
            (self._auto_btn, "auto"),
        ]:
            active = mode == target
            btn.setProperty("active", active)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _detect_system_dark(self) -> bool:
        """检测系统是否为暗色模式。"""
        try:
            from PySide6.QtGui import QGuiApplication
            style_hints = QGuiApplication.styleHints()
            if hasattr(style_hints, "colorScheme"):
                from PySide6.QtCore import Qt
                return style_hints.colorScheme() == Qt.ColorScheme.Dark
        except (RuntimeError, AttributeError) as e:
            # 防御性兜底: QGuiApplication 未就绪或缺 colorScheme 时无法判定,
            # 一律按亮色处理, 不影响启动 (仅记录调试日志)
            logger.debug(f"系统暗色模式检测失败, 按亮色处理: {e}")
        return False

    def _save_tolerance(self) -> None:
        text = self._tolerance_input.text().strip()
        try:
            value = float(text)
            self._settings.setValue("default_tolerance", text)
            self._state.set_default_tolerance(value)
            self._notify_saved()
        except ValueError:
            pass

    def _save_threshold(self) -> None:
        text = self._threshold_input.text().strip()
        self._settings.setValue("gross_margin_threshold", text)
        self._notify_saved()

    def _save_days(self) -> None:
        text = self._days_input.text().strip()
        self._settings.setValue("history_retention_days", text)
        self._notify_saved()

    def _notify_saved(self) -> None:
        """显示"已自动保存"提示条, 2 秒后自动隐藏。"""
        from PySide6.QtCore import QTimer
        self._save_hint.setVisible(True)
        if self._save_hint_timer is not None:
            self._save_hint_timer.stop()
        self._save_hint_timer = QTimer(self)
        self._save_hint_timer.setSingleShot(True)
        self._save_hint_timer.timeout.connect(
            lambda: self._save_hint.setVisible(False)
        )
        self._save_hint_timer.start(2000)

    def _save_llm_provider(self) -> None:
        """保存 LLM provider 类型。"""
        provider = self._llm_provider_combo.currentData()
        self._settings.setValue("llm_provider", provider or "")
        self._settings.sync()
        self._notify_saved()

    def _save_llm_config(self) -> None:
        """保存 LLM 连接配置 (base_url/model/api_key)。"""
        self._settings.setValue("llm_base_url", self._llm_base_url_input.text().strip())
        self._settings.setValue("llm_model", self._llm_model_input.text().strip())
        self._settings.setValue("llm_api_key", self._llm_api_key_input.text().strip())
        self._settings.sync()
        self._notify_saved()

    def _reset_to_defaults(self) -> None:
        """恢复所有设置为默认值并立即生效。"""
        from PySide6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self, "确认恢复",
            "确定将所有设置恢复为默认值吗？此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        defaults = {
            "theme_mode": "auto",
            "default_tolerance": "0.01",
            "gross_margin_threshold": "30",
            "history_retention_days": "90",
            "update_manifest_url": "",
        }
        for key, value in defaults.items():
            self._settings.setValue(key, value)
        self._settings.sync()
        self._load_settings()
        self._update_url_input.setText(defaults["update_manifest_url"])
        self._set_theme("auto")  # 应用主题
        from qfluentwidgets import InfoBar, InfoBarPosition
        InfoBar.success(
            "已恢复默认", "所有设置已重置为默认值",
            orient=Qt.Orientation.Horizontal, isClosable=True,
            position=InfoBarPosition.TOP, duration=2500, parent=self,
        )

    def get_theme_mode(self) -> str:
        """返回当前设置的主题模式。"""
        return str(self._settings.value("theme_mode", "light"))

    def is_dark_theme(self) -> bool:
        """返回当前是否为暗色主题。"""
        mode = self.get_theme_mode()
        if mode == "auto":
            return self._detect_system_dark()
        return mode == "dark"

    # ── 软件更新 ──

    def _save_update_url(self) -> None:
        """保存更新清单 URL 到 QSettings。"""
        url = self._update_url_input.text().strip()
        self._settings.setValue("update_manifest_url", url)
        self._settings.sync()
        self._notify_saved()

    def _check_for_update(self) -> None:
        """检查是否有新版本可用。"""
        from fsa.core.version import APP_VERSION
        from fsa.updater.updater import UpdateError, Updater

        url = self._update_url_input.text().strip()
        if not url:
            self._update_status_label.setText("请先输入更新清单地址")
            return

        self._update_check_btn.setEnabled(False)
        self._update_check_btn.setText("检查中...")
        self._update_status_label.setText("正在检查更新...")

        try:
            updater = Updater(
                manifest_url=url,
                current_version=APP_VERSION,
                timeout=10.0,
            )
            info = updater.check_for_update()

            if info.has_update:
                self._update_status_label.setText(
                    f"发现新版本 {info.latest_version}，可下载更新"
                )
                self._update_download_url = info.download_url
                self._update_download_btn.setVisible(True)
            else:
                self._update_status_label.setText("已是最新版本")
                self._update_download_btn.setVisible(False)
        except UpdateError as e:
            self._update_status_label.setText(f"检查更新失败: {e}")
            self._update_download_btn.setVisible(False)
        finally:
            self._update_check_btn.setEnabled(True)
            self._update_check_btn.setText("检查更新")

    def _download_update(self) -> None:
        """下载更新包到用户选择的路径。"""
        from fsa.updater.updater import UpdateError, Updater

        if not self._update_download_url:
            self._update_status_label.setText("没有可用的下载地址")
            return

        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存更新包",
            "fsa_update.exe",
            "可执行文件 (*.exe)",
        )
        if not save_path:
            return

        self._update_download_btn.setEnabled(False)
        self._update_status_label.setText("正在下载更新...")

        try:
            updater = Updater(
                manifest_url=self._update_url_input.text().strip(),
                current_version="",
                timeout=120.0,
            )
            updater.download(self._update_download_url, save_path)
            self._update_status_label.setText(f"下载完成: {save_path}")
        except UpdateError as e:
            self._update_status_label.setText(f"下载失败: {e}")
        finally:
            self._update_download_btn.setEnabled(True)
