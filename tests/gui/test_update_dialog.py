"""更新对话框测试: 立即更新下载路径 + 取消路径 + 启动检查角标显示。

覆盖:
- 对话框内容 (新版本号/更新说明/按钮)
- 立即更新: mock Updater 下载到固定临时目录 (~/.fsa/updates), 不弹 QFileDialog,
  完成后调用 install
- 下载失败: 中文状态 + 按钮恢复可重试
- 取消路径: 关闭对话框且顶栏角标仍在
- app.py 启动更新检查发现新版: 显示角标并缓存 UpdateInfo
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QFileDialog, QLabel, QMessageBox, QTextBrowser

from fsa.gui.main_window import MainWindow
from fsa.gui.update_dialog import UpdateDialog
from fsa.updater.updater import UpdateError, UpdateInfo


def _make_info(
    latest_version: str = "0.5.0",
    download_url: str = "http://intranet/fsa_0.5.0.exe",
    release_notes: str = "修复若干问题\n新增校验功能",
) -> UpdateInfo:
    """构造发现新版本的 UpdateInfo。"""
    return UpdateInfo(
        current_version="0.4.0",
        latest_version=latest_version,
        has_update=True,
        download_url=download_url,
        release_notes=release_notes,
    )


class _FakeDownloadUpdater:
    """模拟带进度回调的下载, 并把 install 调用记录到类属性。"""

    install_calls: list[str] = []

    def __init__(self, manifest_url: str, current_version: str, timeout: float = 10.0) -> None:
        pass

    def download(self, url: str, dest_path: str, progress_cb: object = None) -> str:
        if callable(progress_cb):
            progress_cb(50, 100)
            progress_cb(100, 100)
        Path(dest_path).write_bytes(b"installer")
        return dest_path

    def install(self, installer_path: str) -> None:
        _FakeDownloadUpdater.install_calls.append(installer_path)


class _FakeFailingDownloadUpdater:
    """模拟下载失败的 Updater。"""

    def __init__(self, manifest_url: str, current_version: str, timeout: float = 10.0) -> None:
        pass

    def download(self, url: str, dest_path: str, progress_cb: object = None) -> str:
        raise UpdateError("下载失败: 网络连接错误")


class _FakeHasUpdateUpdater:
    """模拟启动检查发现新版本的 Updater。"""

    def __init__(self, manifest_url: str, current_version: str, timeout: float = 5.0) -> None:
        pass

    def check_for_update(self) -> UpdateInfo:
        return _make_info()


class TestUpdateDialogContent:
    """对话框内容: 新版本号 / 更新说明 / 按钮。"""

    def test_dialog_shows_version_notes_and_buttons(self, qapp, qtbot) -> None:
        """显示新版本号、完整更新说明与「立即更新」「取消」按钮。"""
        info = _make_info(release_notes="第一行说明\n第二行说明")
        dialog = UpdateDialog(info)
        qtbot.addWidget(dialog)

        title = dialog.findChild(QLabel, "UpdateDialogTitle")
        assert title is not None and "0.5.0" in title.text()

        notes = dialog.findChild(QTextBrowser, "UpdateNotes")
        assert notes is not None
        plain = notes.toPlainText()
        assert "第一行说明" in plain
        assert "第二行说明" in plain

        assert dialog._update_btn.text() == "立即更新"
        assert dialog._cancel_btn.text() == "取消"

    def test_cancel_button_rejects_dialog(self, qapp, qtbot) -> None:
        """点击「取消」关闭对话框 (角标状态不受影响)。"""
        from PySide6.QtWidgets import QDialog

        dialog = UpdateDialog(_make_info())
        qtbot.addWidget(dialog)
        dialog._cancel_btn.click()
        assert dialog.result() == QDialog.DialogCode.Rejected


class TestUpdateDialogImmediateUpdate:
    """立即更新: 固定临时目录 + install 调用 + 失败恢复。"""

    def test_immediate_update_downloads_to_fixed_dir_and_installs(
        self, qapp, qtbot, monkeypatch, tmp_path
    ) -> None:
        """立即更新: 下载到 ~/.fsa/updates/fsa_update_<版本>.exe 并调用 install (不弹 QFileDialog)。"""
        # 对话框模块级导入 Updater, 直接替换其命名空间引用
        monkeypatch.setattr("fsa.gui.update_dialog.Updater", _FakeDownloadUpdater)
        _FakeDownloadUpdater.install_calls.clear()
        # 固定临时目录重定向到 tmp_path 以便断言; 同时确保不弹文件对话框
        monkeypatch.setattr("fsa.gui.update_dialog._UPDATES_DIR", tmp_path)
        monkeypatch.setattr(
            QFileDialog,
            "getSaveFileName",
            staticmethod(lambda *a, **k: (_ for _ in ()).throw(AssertionError("不应弹出文件对话框"))),
        )
        monkeypatch.setattr(
            QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
        )

        dialog = UpdateDialog(_make_info())
        qtbot.addWidget(dialog)
        dialog._update_btn.click()
        qtbot.waitUntil(lambda: not dialog._downloading, timeout=5000)

        expected = str(tmp_path / "fsa_update_0.5.0.exe")
        assert _FakeDownloadUpdater.install_calls == [expected]
        assert Path(expected).exists()

    def test_download_failure_shows_status_and_reenables(
        self, qapp, qtbot, monkeypatch, tmp_path
    ) -> None:
        """下载失败: 中文状态文案 + 「立即更新」按钮恢复可重试。"""
        monkeypatch.setattr("fsa.gui.update_dialog.Updater", _FakeFailingDownloadUpdater)
        monkeypatch.setattr("fsa.gui.update_dialog._UPDATES_DIR", tmp_path)

        dialog = UpdateDialog(_make_info())
        qtbot.addWidget(dialog)
        dialog._update_btn.click()
        qtbot.waitUntil(lambda: not dialog._downloading, timeout=5000)

        assert "下载失败" in dialog._status.text()
        assert dialog._update_btn.isEnabled()
        assert dialog._cancel_btn.isEnabled()


class TestUpdateBadgeWiring:
    """顶栏角标 -> 更新对话框接线 + 取消后角标仍在。"""

    def test_badge_click_opens_dialog_and_cancel_keeps_badge(
        self, qapp, qtbot, app_state, monkeypatch
    ) -> None:
        """点击角标弹出更新对话框; 取消后对话框关闭且角标仍在。"""
        from PySide6.QtWidgets import QDialog

        from fsa.gui import update_dialog as dialog_module

        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        window.show()
        window._pending_update_info = _make_info()
        window.show_update_badge("0.5.0")
        assert window._topbar._update_badge_btn.isVisible()

        opened: list[UpdateDialog] = []
        # mock exec: 不阻塞测试, 直接模拟用户点「取消」关闭
        monkeypatch.setattr(
            dialog_module.UpdateDialog,
            "exec",
            lambda self: opened.append(self) or QDialog.DialogCode.Rejected,
        )
        window._topbar.update_badge_clicked.emit()

        assert len(opened) == 1
        # 取消后角标保留, 可再次点击
        assert window._topbar._update_badge_btn.isVisible()

    def test_open_dialog_without_pending_info_is_noop(self, qapp, qtbot, app_state, monkeypatch) -> None:
        """无缓存更新信息时点击角标不弹对话框。"""
        from fsa.gui import update_dialog as dialog_module

        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        window.show()
        opened: list[UpdateDialog] = []
        monkeypatch.setattr(
            dialog_module.UpdateDialog,
            "exec",
            lambda self: opened.append(self) or 0,
        )
        window._topbar.update_badge_clicked.emit()
        assert opened == []


class TestStartupUpdateCheck:
    """app.py 启动更新检查发现新版时角标显示并缓存 UpdateInfo。"""

    def test_startup_check_has_update_shows_badge(
        self, qapp, qtbot, app_state, monkeypatch
    ) -> None:
        """启动检查发现新版: 顶栏角标显示 + window 缓存完整 UpdateInfo。"""
        from fsa.gui.app import _schedule_startup_update_check

        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        window.show()
        # app.py 模块级导入 Updater, 直接替换其命名空间引用
        monkeypatch.setattr("fsa.gui.app.Updater", _FakeHasUpdateUpdater)

        settings = QSettings("FSA", "FinancialAudit")
        settings.setValue("update_manifest_url", "http://intranet/version.json")
        _schedule_startup_update_check(window, settings)

        qtbot.waitUntil(lambda: window._topbar._update_badge_btn.isVisible(), timeout=8000)
        info = window._pending_update_info
        assert info is not None
        assert info.latest_version == "0.5.0"
        assert info.download_url == "http://intranet/fsa_0.5.0.exe"
        assert "0.5.0" in window._topbar._update_badge_btn.toolTip()
