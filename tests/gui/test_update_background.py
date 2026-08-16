"""B5-1 设置页更新检查/下载后台化测试 (mock Updater, 真实后台线程 + 信号)。"""

from __future__ import annotations

from pathlib import Path

from fsa.gui.pages.settings_page import SettingsPage
from fsa.updater.updater import UpdateError, UpdateInfo


class _FakeUpdaterHasUpdate:
    """模拟发现新版本的 Updater。"""

    def __init__(self, manifest_url: str, current_version: str, timeout: float = 10.0) -> None:
        self._manifest_url = manifest_url

    def check_for_update(self) -> UpdateInfo:
        return UpdateInfo(
            current_version="0.4.0",
            latest_version="0.5.0",
            has_update=True,
            download_url="http://intranet/fsa_0.5.0.exe",
            release_notes="",
        )


class _FakeUpdaterLatest:
    """模拟已是最新的 Updater。"""

    def __init__(self, manifest_url: str, current_version: str, timeout: float = 10.0) -> None:
        pass

    def check_for_update(self) -> UpdateInfo:
        return UpdateInfo(
            current_version="0.5.0",
            latest_version="0.5.0",
            has_update=False,
            download_url="",
            release_notes="",
        )


class _FakeUpdaterFailing:
    """模拟检查失败的 Updater。"""

    def __init__(self, manifest_url: str, current_version: str, timeout: float = 10.0) -> None:
        pass

    def check_for_update(self) -> UpdateInfo:
        raise UpdateError("网络连接错误")


class _FakeDownloadUpdater:
    """模拟带进度回调的下载。"""

    def __init__(self, manifest_url: str, current_version: str, timeout: float = 10.0) -> None:
        pass

    def download(self, url: str, dest_path: str, progress_cb: object = None) -> str:
        if callable(progress_cb):
            progress_cb(50, 100)
            progress_cb(100, 100)
        Path(dest_path).write_bytes(b"installer")
        return dest_path


class TestCheckForUpdateBackground:
    """检查更新在后台线程执行, 结果经信号回主线程。"""

    def test_check_has_update(self, qapp, qtbot, app_state, monkeypatch) -> None:
        """发现新版本: 状态文案 + 下载按钮可见。"""
        monkeypatch.setattr("fsa.updater.updater.Updater", _FakeUpdaterHasUpdate)
        page = SettingsPage(app_state)
        qtbot.addWidget(page)
        page._update_url_input.setText("http://intranet/version.json")

        page._check_for_update()
        qtbot.waitUntil(lambda: not page._update_checking, timeout=5000)

        assert "发现新版本 0.5.0" in page._update_status_label.text()
        assert not page._update_download_btn.isHidden()
        assert page._update_download_url == "http://intranet/fsa_0.5.0.exe"
        assert page._update_check_btn.isEnabled()

    def test_check_already_latest(self, qapp, qtbot, app_state, monkeypatch) -> None:
        """已是最新: 状态文案 + 下载按钮隐藏。"""
        monkeypatch.setattr("fsa.updater.updater.Updater", _FakeUpdaterLatest)
        page = SettingsPage(app_state)
        qtbot.addWidget(page)
        page._update_url_input.setText("http://intranet/version.json")

        page._check_for_update()
        qtbot.waitUntil(lambda: not page._update_checking, timeout=5000)

        assert "已是最新版本" in page._update_status_label.text()

    def test_check_failure(self, qapp, qtbot, app_state, monkeypatch) -> None:
        """检查失败: 中文错误文案, 按钮恢复可用。"""
        monkeypatch.setattr("fsa.updater.updater.Updater", _FakeUpdaterFailing)
        page = SettingsPage(app_state)
        qtbot.addWidget(page)
        page._update_url_input.setText("http://intranet/version.json")

        page._check_for_update()
        qtbot.waitUntil(lambda: not page._update_checking, timeout=5000)

        assert "检查更新失败" in page._update_status_label.text()
        assert page._update_check_btn.isEnabled()

    def test_check_reentry_ignored(self, qapp, qtbot, app_state, monkeypatch) -> None:
        """检查进行中重复点击被忽略。"""
        monkeypatch.setattr("fsa.updater.updater.Updater", _FakeUpdaterHasUpdate)
        page = SettingsPage(app_state)
        qtbot.addWidget(page)
        page._update_url_input.setText("http://intranet/version.json")
        page._update_checking = True

        page._check_for_update()

        assert page._update_status_label.text() != "正在检查更新..."


class TestDownloadUpdateBackground:
    """下载更新在后台线程执行, 带百分比进度。"""

    def _prepare(self, qtbot, app_state, monkeypatch, tmp_path) -> SettingsPage:
        monkeypatch.setattr("fsa.updater.updater.Updater", _FakeDownloadUpdater)
        from PySide6.QtWidgets import QFileDialog, QMessageBox

        save_path = str(tmp_path / "fsa_update.exe")
        monkeypatch.setattr(
            QFileDialog, "getSaveFileName",
            staticmethod(lambda *args, **kwargs: (save_path, "*.exe")),
        )
        monkeypatch.setattr(
            QMessageBox, "question",
            staticmethod(lambda *args, **kwargs: QMessageBox.StandardButton.No),
        )
        page = SettingsPage(app_state)
        qtbot.addWidget(page)
        page._update_url_input.setText("http://intranet/version.json")
        page._update_download_url = "http://intranet/fsa_0.5.0.exe"
        return page

    def test_download_success_with_progress(self, qapp, qtbot, app_state, monkeypatch, tmp_path) -> None:
        """下载完成: 状态显示完成路径, 按钮恢复。"""
        page = self._prepare(qtbot, app_state, monkeypatch, tmp_path)

        page._download_update()
        qtbot.waitUntil(lambda: not page._update_downloading, timeout=5000)

        assert "下载完成" in page._update_status_label.text()
        assert page._update_download_btn.isEnabled()

    def test_download_reentry_ignored(self, qapp, qtbot, app_state, monkeypatch, tmp_path) -> None:
        """下载中再次点击被忽略 (不弹文件对话框)。"""
        from PySide6.QtWidgets import QFileDialog

        page = self._prepare(qtbot, app_state, monkeypatch, tmp_path)
        page._update_downloading = True
        monkeypatch.setattr(
            QFileDialog, "getSaveFileName",
            staticmethod(lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("不应弹框"))),
        )
        page._update_status_label.setText("正在下载更新... 50%")

        page._download_update()

        assert page._update_status_label.text() == "正在下载更新... 50%"

    def test_download_progress_format(self, qapp, qtbot, app_state) -> None:
        """进度回调按百分比/已下载两种格式展示。"""
        page = SettingsPage(app_state)
        qtbot.addWidget(page)

        page._on_update_download_progress(524288, 1048576)
        assert "50%" in page._update_status_label.text()

        page._on_update_download_progress(524288, -1)
        assert "已下载 0.5 MB" in page._update_status_label.text()
