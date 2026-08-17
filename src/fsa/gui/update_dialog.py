"""更新对话框: 版本说明 + 一键下载安装。

点击顶栏更新角标弹出 (模态); 展示新版本号与完整更新说明。
「立即更新」下载到固定临时目录 (~/.fsa/updates/fsa_update_<版本>.exe,
不再弹 QFileDialog), 下载全程后台线程 + 信号桥, 不冻结 GUI;
SHA256 校验由 Updater.download 完成, 通过后确认静默安装并退出应用。
取消/关闭对话框不改变顶栏角标状态 (角标保留, 随时可再次打开)。
"""

from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import QObject, QSettings, Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import InfoBar, InfoBarPosition

from fsa.core.edition import get_edition_config
from fsa.updater.updater import UpdateError, UpdateInfo, Updater

# 更新包固定保存目录 (用户主目录, 不依赖安装位置)
_UPDATES_DIR = Path.home() / ".fsa" / "updates"


class _DownloadBridge(QObject):
    """下载后台线程 -> 对话框信号桥 (线程约定: threading.Thread + Signal)。"""

    progress = Signal(int, int)  # (已下载字节数, 总字节数; 总字节 -1 表示未知)
    finished = Signal(str)  # installer_path
    failed = Signal(str)


class UpdateDialog(QDialog):
    """发现新版本对话框: 更新说明 + 立即更新/取消。"""

    def __init__(self, info: UpdateInfo, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("UpdateDialog")
        self.setWindowTitle("发现新版本")
        self.setModal(True)
        self.setMinimumSize(480, 400)
        self._info = info
        # 下载后台任务状态 (防重复点击; 桥对象防 GC)
        self._bridge: _DownloadBridge | None = None
        self._downloading = False
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        title = QLabel(f"发现新版本 v{self._info.latest_version}")
        title.setObjectName("UpdateDialogTitle")
        layout.addWidget(title)

        current = QLabel(f"当前版本: {self._info.current_version}")
        current.setObjectName("MetaLabel")
        layout.addWidget(current)

        notes = QTextBrowser()
        notes.setObjectName("UpdateNotes")
        notes.setOpenExternalLinks(False)
        notes.setPlainText(self._info.release_notes or "（暂无更新说明）")
        notes.setMinimumHeight(160)
        layout.addWidget(notes, stretch=1)

        self._progress = QProgressBar()
        self._progress.setObjectName("UpdateProgress")
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.hide()
        layout.addWidget(self._progress)

        self._status = QLabel("")
        self._status.setObjectName("MetaLabel")
        self._status.setWordWrap(True)
        self._status.hide()
        layout.addWidget(self._status)

        buttons = QHBoxLayout()
        buttons.addStretch()
        self._update_btn = QPushButton("立即更新")
        self._update_btn.setObjectName("BtnPrimary")
        self._update_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_btn.clicked.connect(self._start_download)
        buttons.addWidget(self._update_btn)
        self._cancel_btn = QPushButton("取消")
        self._cancel_btn.setObjectName("BtnSecondary")
        self._cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(self._cancel_btn)
        layout.addLayout(buttons)

    # ── 下载 ──

    def _manifest_url(self) -> str:
        """更新清单地址: QSettings 优先, 缺省走版本通道默认地址。"""
        url = str(QSettings("FSA", "FinancialAudit").value("update_manifest_url", "")).strip()
        return url or get_edition_config().default_update_url

    def _default_installer_path(self) -> str:
        """更新包固定临时目录: ~/.fsa/updates/fsa_update_<版本>.exe。"""
        _UPDATES_DIR.mkdir(parents=True, exist_ok=True)
        return str(_UPDATES_DIR / f"fsa_update_{self._info.latest_version}.exe")

    def _start_download(self) -> None:
        """立即更新: 后台下载到固定目录 (不弹 QFileDialog), 带进度。"""
        if self._downloading:
            return
        url = self._info.download_url
        if not url:
            self._show_failure("没有可用的下载地址")
            return

        self._downloading = True
        self._update_btn.setEnabled(False)
        self._cancel_btn.setEnabled(False)
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.show()
        self._status.setText("正在下载更新...")
        self._status.show()

        dest = self._default_installer_path()
        bridge = _DownloadBridge(self)
        bridge.progress.connect(self._on_progress)
        bridge.finished.connect(self._on_download_finished)
        bridge.failed.connect(self._on_download_failed)
        self._bridge = bridge

        def run() -> None:
            try:
                Updater(
                    manifest_url=self._manifest_url(),
                    current_version="",
                    timeout=120.0,
                ).download(url, dest, progress_cb=bridge.progress.emit)
            except UpdateError as e:
                bridge.failed.emit(str(e))
            else:
                bridge.finished.emit(dest)

        threading.Thread(target=run, daemon=True).start()

    def _on_progress(self, downloaded: int, total: int) -> None:
        """下载进度 (GUI 线程): 有总字节数时显示百分比, 否则忙碌指示。"""
        if total > 0:
            percent = min(100, downloaded * 100 // total)
            self._progress.setRange(0, 100)
            self._progress.setValue(percent)
            self._status.setText(f"正在下载更新... {percent}%")
        else:
            self._progress.setRange(0, 0)  # 未知总大小: 忙碌指示条
            self._status.setText("正在下载更新...")

    def _on_download_finished(self, installer_path: str) -> None:
        """下载完成且 SHA256 校验通过 (GUI 线程): 确认后静默安装。"""
        self._downloading = False
        self._progress.setRange(0, 100)
        self._progress.setValue(100)
        self._status.setText("下载完成，完整性校验通过。")

        reply = QMessageBox.question(
            self,
            "安装更新",
            "更新包已下载并通过完整性校验。\n点击「确定」将关闭软件并开始静默安装。",
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Ok,
        )
        if reply != QMessageBox.StandardButton.Ok:
            # 取消安装: 关闭对话框, 顶栏角标保留 (可再次打开)
            self.reject()
            return
        try:
            Updater(
                manifest_url=self._manifest_url(),
                current_version="",
                timeout=120.0,
            ).install(installer_path)
        except UpdateError as e:
            self._show_failure(str(e))
            self._status.setText(f"安装失败: {e}")
            return
        # 安装器已启动 (内置 3 秒延迟), 立即退出应用释放文件占用
        QApplication.quit()

    def _on_download_failed(self, message: str) -> None:
        """下载失败 (GUI 线程): 中文 InfoBar, 按钮恢复可重试。"""
        self._downloading = False
        self._update_btn.setEnabled(True)
        self._cancel_btn.setEnabled(True)
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._status.setText(f"下载失败: {message}")
        self._show_failure(message)

    def _show_failure(self, message: str) -> None:
        """中文失败提示 (下载失败/校验失败/清单不可达)。"""
        InfoBar.error(
            "更新失败",
            message,
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=6000,
            parent=self.window(),
        )
