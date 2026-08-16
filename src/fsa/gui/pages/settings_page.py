"""系统设置页面: 外观/校验参数/数据存储/关于/软件更新。

匹配 Demo v4 设计: 多分区设置面板。
支持 QSettings 持久化: theme_mode, industry, history_retention_days,
update_manifest_url。
"""

from __future__ import annotations

import threading

from loguru import logger
from PySide6.QtCore import QObject, QSettings, Qt, Signal
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import InfoBar, InfoBarPosition, SwitchButton

from fsa.gui.app_state import AppState
from fsa.gui.pages.settings_sections import (
    build_about_section,
    build_appearance_section,
    build_llm_section,
    build_storage_section,
    build_update_section,
    build_validation_section,
)
from fsa.gui.theme import bind_theme_listener
from fsa.gui.widgets.dropdown_combo import DropdownCombo


class _UpdateBridge(QObject):
    """更新检查/下载后台线程 -> GUI 线程的信号桥 (B5-1: 网络 IO 全部后台化)。"""

    check_finished = Signal(object)  # UpdateInfo
    check_failed = Signal(str)
    download_finished = Signal(str)  # save_path
    download_failed = Signal(str)
    download_progress = Signal(int, int)  # (已下载字节数, 总字节数; -1 表示未知)


class SettingsPage(QWidget):
    """系统设置页面。"""

    theme_changed = Signal(bool)

    # 由 settings_sections 的 build_* 分区构建器动态挂接的控件引用
    _light_btn: QPushButton
    _dark_btn: QPushButton
    _auto_btn: QPushButton
    _industry_combo: DropdownCombo
    _days_input: QLineEdit
    _update_url_input: QLineEdit
    _update_check_btn: QPushButton
    _update_download_btn: QPushButton
    _update_status_label: QLabel
    _update_download_url: str
    _llm_provider_combo: DropdownCombo
    _llm_base_url_input: QLineEdit
    _llm_model_input: QLineEdit
    _llm_api_key_input: QLineEdit
    _llm_remote_switch: SwitchButton

    def __init__(self, state: AppState) -> None:
        super().__init__()
        self.setObjectName("SettingsPage")
        self._state = state
        self._settings = QSettings("FSA", "FinancialAudit")
        # 更新检查/下载后台任务状态 (防重复点击; 桥对象防 GC)
        self._update_bridge: _UpdateBridge | None = None
        self._update_checking = False
        self._update_downloading = False
        self._setup_ui()
        self._load_settings()
        # 注册主题监听器: 顶栏/Ctrl+D 切换后, 即使页面已打开也立即刷新按钮高亮
        bind_theme_listener(self, self._on_external_theme_changed)

    def _on_external_theme_changed(self) -> None:
        """页面已打开时, 外部主题切换立即同步按钮高亮。"""
        self._update_theme_buttons(str(self._settings.value("theme_mode", "light")))

    def showEvent(self, event: QShowEvent) -> None:
        """页面显示时重读主题模式刷新按钮高亮 (B3-4: 顶栏/Ctrl+D 切换后同步)。"""
        super().showEvent(event)
        self._update_theme_buttons(str(self._settings.value("theme_mode", "light")))

    def _setup_ui(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        content.setObjectName("PageContent")
        layout = QVBoxLayout(content)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

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
        mode = str(self._settings.value("theme_mode", "light"))
        self._update_theme_buttons(mode)

        industry = str(self._settings.value("industry", "general"))
        index = self._industry_combo.findData(industry)
        self._industry_combo.setCurrentIndex(index if index >= 0 else 0)

        days = str(self._settings.value("history_retention_days", "90"))
        self._days_input.setText(days)

    def _set_theme(self, mode: str) -> None:
        self._settings.setValue("theme_mode", mode)
        self._settings.sync()
        self._update_theme_buttons(mode)
        dark = self._detect_system_dark() if mode == "auto" else mode == "dark"

        # 主题应用统一由 MainWindow 负责 (监听 theme_changed),
        # 本页不直接 apply_theme/setStyleSheet, 避免双入口重复执行
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

    def _save_industry(self) -> None:
        industry = str(self._industry_combo.currentData())
        self._settings.setValue("industry", industry)
        self._settings.sync()
        self._notify_saved()

    def _save_days(self) -> None:
        text = self._days_input.text().strip()
        self._settings.setValue("history_retention_days", text)
        self._notify_saved()

    def _notify_saved(self) -> None:
        """在页面右上角弹出浮动提示, 2 秒后自动消失, 不占布局。"""
        InfoBar.success(
            "已保存",
            "设置已自动保存",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP_RIGHT,
            duration=2000,
            parent=self,
        )

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

    def _export_problem_package(self) -> None:
        """导出问题包 (日志 + 数据库 + 诊断信息), 供支持排查。"""
        from datetime import datetime

        from fsa.services.problem_package import create_problem_package

        default_name = f"fsa_problem_{datetime.now():%Y%m%d_%H%M}.zip"
        path, _ = QFileDialog.getSaveFileName(self, "导出问题包", default_name, "ZIP 文件 (*.zip)")
        if not path:
            return
        try:
            result = create_problem_package(path)
        except OSError:
            logger.exception("导出问题包失败")
            InfoBar.error(
                "导出失败",
                "无法写入所选文件，请检查路径后重试。",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=4000,
                parent=self,
            )
            return
        InfoBar.success(
            "导出完成",
            f"问题包已生成 ({result.file_count} 个文件):\n{result.path}\n{result.note}",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=6000,
            parent=self,
        )

    def _reset_to_defaults(self) -> None:
        """恢复所有设置为默认值并立即生效。"""
        from PySide6.QtWidgets import QMessageBox

        reply = QMessageBox.question(
            self,
            "确认恢复",
            "确定将所有设置恢复为默认值吗？此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        from fsa.core.edition import get_edition_config

        defaults = {
            "theme_mode": "auto",
            "industry": "general",
            "history_retention_days": "90",
            "update_manifest_url": get_edition_config().default_update_url,
        }
        for key, value in defaults.items():
            self._settings.setValue(key, value)
        self._settings.sync()
        self._load_settings()
        self._update_url_input.setText(defaults["update_manifest_url"])
        self._set_theme("auto")  # 应用主题

        # 清除规则页逐条容差覆写并重载注册表 (回放默认容差)
        if self._state.override_repo is not None:
            self._state.override_repo.clear()
            self._state.load_registry()

        from qfluentwidgets import InfoBar, InfoBarPosition

        InfoBar.success(
            "已恢复默认",
            "外观与校验参数已恢复默认，规则页逐条覆写已清除（AI 助手与更新配置保留）",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2500,
            parent=self,
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
        """后台检查是否有新版本可用 (网络 IO 移出 GUI 线程, B5-1)。"""
        if self._update_checking:
            return
        url = self._update_url_input.text().strip()
        if not url:
            self._update_status_label.setText("请先输入更新清单地址")
            return

        self._update_checking = True
        self._update_check_btn.setEnabled(False)
        self._update_check_btn.setText("检查中...")
        self._update_status_label.setText("正在检查更新...")

        bridge = _UpdateBridge(self)
        bridge.check_finished.connect(self._on_update_check_finished)
        bridge.check_failed.connect(self._on_update_check_failed)
        self._update_bridge = bridge

        def run() -> None:
            from fsa.core.version import APP_VERSION
            from fsa.updater.updater import UpdateError, Updater

            try:
                info = Updater(
                    manifest_url=url,
                    current_version=APP_VERSION,
                    timeout=10.0,
                ).check_for_update()
            except UpdateError as e:
                bridge.check_failed.emit(str(e))
            else:
                bridge.check_finished.emit(info)

        threading.Thread(target=run, daemon=True).start()

    def _on_update_check_finished(self, info: object) -> None:
        """后台更新检查完成 (GUI 线程)。"""
        from fsa.updater.updater import UpdateInfo

        self._finish_update_check()
        if not isinstance(info, UpdateInfo):
            self._update_status_label.setText("检查更新失败: 结果无效")
            self._update_download_btn.setVisible(False)
            return
        if info.has_update:
            self._update_status_label.setText(f"发现新版本 {info.latest_version}，可下载更新")
            self._update_download_url = info.download_url
            self._update_download_btn.setVisible(True)
        else:
            self._update_status_label.setText("已是最新版本")
            self._update_download_btn.setVisible(False)

    def _on_update_check_failed(self, message: str) -> None:
        """后台更新检查失败 (GUI 线程)。"""
        self._finish_update_check()
        self._update_status_label.setText(f"检查更新失败: {message}")
        self._update_download_btn.setVisible(False)

    def _finish_update_check(self) -> None:
        """恢复检查按钮与任务状态。"""
        self._update_checking = False
        self._update_check_btn.setEnabled(True)
        self._update_check_btn.setText("检查更新")

    def _download_update(self) -> None:
        """后台下载更新包到用户选择的路径 (带百分比进度, B5-1)。"""
        if self._update_downloading:
            # 下载中再次点击忽略 (按钮已禁用, 双保险)
            return
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

        download_url = self._update_download_url
        manifest_url = self._update_url_input.text().strip()
        self._update_downloading = True
        self._update_download_btn.setEnabled(False)
        self._update_status_label.setText("正在下载更新...")

        bridge = _UpdateBridge(self)
        bridge.download_finished.connect(self._on_update_download_finished)
        bridge.download_failed.connect(self._on_update_download_failed)
        bridge.download_progress.connect(self._on_update_download_progress)
        self._update_bridge = bridge

        def run() -> None:
            from fsa.updater.updater import UpdateError, Updater

            try:
                Updater(
                    manifest_url=manifest_url,
                    current_version="",
                    timeout=120.0,
                ).download(download_url, save_path, progress_cb=bridge.download_progress.emit)
            except UpdateError as e:
                bridge.download_failed.emit(str(e))
            else:
                bridge.download_finished.emit(save_path)

        threading.Thread(target=run, daemon=True).start()

    def _on_update_download_progress(self, downloaded: int, total: int) -> None:
        """下载进度 (GUI 线程): 有总字节数时显示百分比。"""
        downloaded_mb = downloaded / 1048576
        if total > 0:
            percent = min(100, downloaded * 100 // total)
            self._update_status_label.setText(
                f"正在下载更新... {percent}% ({downloaded_mb:.1f} MB / {total / 1048576:.1f} MB)"
            )
        else:
            self._update_status_label.setText(f"正在下载更新... 已下载 {downloaded_mb:.1f} MB")

    def _on_update_download_finished(self, save_path: str) -> None:
        """后台下载完成 (GUI 线程): 询问是否静默安装。"""
        from fsa.updater.updater import Updater

        self._update_downloading = False
        self._update_download_btn.setEnabled(True)
        self._update_status_label.setText(f"下载完成: {save_path}")
        updater = Updater(
            manifest_url=self._update_url_input.text().strip(),
            current_version="",
            timeout=120.0,
        )
        self._offer_install(updater, save_path)

    def _on_update_download_failed(self, message: str) -> None:
        """后台下载失败 (GUI 线程)。"""
        self._update_downloading = False
        self._update_download_btn.setEnabled(True)
        self._update_status_label.setText(f"下载失败: {message}")

    def _offer_install(self, updater: object, installer_path: str) -> None:
        """下载完成后询问是否立即静默安装并重启 (一键更新闭环)。"""
        from PySide6.QtWidgets import QApplication, QMessageBox

        from fsa.updater.updater import UpdateError

        install = getattr(updater, "install", None)
        if install is None:
            InfoBar.info(
                "下载完成",
                f"请手动运行安装包完成安装:\n{installer_path}",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self,
            )
            return
        reply = QMessageBox.question(
            self,
            "安装更新",
            "更新包已下载并通过完整性校验。\n是否立即安装？应用将自动关闭并完成静默安装，随后自动重启。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            install(installer_path)
        except UpdateError as e:
            InfoBar.error(
                "安装失败",
                str(e),
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self,
            )
            return
        # 安装器已启动 (内置 3 秒延迟), 立即退出应用释放文件占用
        QApplication.quit()
