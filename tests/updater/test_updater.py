"""Updater 模块单元测试: compare_versions, check_for_update, download, UpdateError。

所有 HTTP 调用通过 mock urllib.request.urlopen 进行，不发起真实网络请求。
"""

from __future__ import annotations

import hashlib
import io
import json
import urllib.error
from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest
from loguru import logger

from fsa.updater.updater import (
    UpdateError,
    UpdateInfo,
    Updater,
    compare_versions,
)


@contextmanager
def _capture_loguru(level: str = "WARNING") -> Iterator[io.StringIO]:
    """捕获 loguru 日志到 StringIO，用于断言警告日志。

    loguru 默认 stderr handler 在导入时即绑定底层 fd，capsys/caplog 捕获不到，
    因此挂载临时 StringIO sink。
    """
    sink = io.StringIO()
    handler_id = logger.add(sink, level=level, format="{message}", colorize=False)
    try:
        yield sink
    finally:
        logger.remove(handler_id)


def _make_http_response(
    read_side_effect: list[bytes],
    headers: dict | None = None,
) -> MagicMock:
    """构造模拟的 HTTP 响应对象。

    Args:
        read_side_effect: response.read 的逐次返回值序列（最后一次通常为 b""）
        headers: 可选响应头字典（含 Content-Length 等）

    Returns:
        模拟的响应对象
    """
    mock = MagicMock()
    mock.__enter__ = MagicMock(return_value=mock)
    mock.__exit__ = MagicMock(return_value=False)
    mock.read.side_effect = read_side_effect
    if headers is not None:
        mock.headers = headers
    return mock


def _make_manifest_response(sha256: str | None = None) -> MagicMock:
    """构造模拟的更新清单响应对象。

    Args:
        sha256: 期望的 sha256 字段值；为 None 时不写入该字段

    Returns:
        模拟的清单响应对象
    """
    manifest: dict = {
        "version": "0.2.0",
        "download_url": "http://example.com/fsa.exe",
    }
    if sha256 is not None:
        manifest["sha256"] = sha256
    return _make_http_response([json.dumps(manifest).encode("utf-8")])


class TestCompareVersions:
    """compare_versions 函数测试。"""

    def test_equal_versions_returns_zero(self) -> None:
        """相等版本返回 0。"""
        assert compare_versions("0.1.0", "0.1.0") == 0

    def test_current_less_than_latest_returns_negative(self) -> None:
        """当前版本小于最新版本返回 -1。"""
        assert compare_versions("0.1.0", "0.2.0") == -1

    def test_current_greater_than_latest_returns_positive(self) -> None:
        """当前版本大于最新版本返回 1。"""
        assert compare_versions("0.2.0", "0.1.0") == 1

    def test_leading_v_prefix_ignored(self) -> None:
        """忽略前导 'v' 前缀。"""
        assert compare_versions("v0.1.0", "0.1.0") == 0
        assert compare_versions("0.1.0", "v0.1.0") == 0
        assert compare_versions("v0.1.0", "v0.2.0") == -1
        assert compare_versions("v0.2.0", "v0.1.0") == 1

    def test_different_segment_counts_compare_correctly(self) -> None:
        """不同段数比较: 短版本补齐0。"""
        assert compare_versions("0.1", "0.1.0") == 0
        assert compare_versions("0.1.0", "0.1") == 0
        assert compare_versions("0.2", "0.1.1") == 1
        assert compare_versions("0.1.0.1", "0.1.0") == 1

    def test_major_version_difference(self) -> None:
        """主版本号差异。"""
        assert compare_versions("1.0.0", "0.9.9") == 1
        assert compare_versions("0.9.9", "1.0.0") == -1

    def test_minor_version_difference(self) -> None:
        """次版本号差异。"""
        assert compare_versions("0.1.9", "0.2.0") == -1
        assert compare_versions("0.2.0", "0.1.9") == 1

    def test_patch_version_difference(self) -> None:
        """修订版本号差异。"""
        assert compare_versions("0.1.0", "0.1.1") == -1
        assert compare_versions("0.1.1", "0.1.0") == 1

    def test_two_digit_versions(self) -> None:
        """两位数版本号。"""
        assert compare_versions("10.0.0", "9.0.0") == 1
        assert compare_versions("0.10.0", "0.9.0") == 1
        assert compare_versions("0.0.10", "0.0.9") == 1

    def test_zero_versions(self) -> None:
        """全零版本。"""
        assert compare_versions("0.0.0", "0.0.0") == 0
        assert compare_versions("0.0.0", "0.0.1") == -1

    def test_single_segment(self) -> None:
        """单段版本号。"""
        assert compare_versions("1", "1.0.0") == 0
        assert compare_versions("1", "2") == -1
        assert compare_versions("2", "1") == 1


class TestUpdateInfo:
    """UpdateInfo 数据类测试。"""

    def test_has_update_true_when_versions_differ(self) -> None:
        """版本不同时 has_update=True。"""
        info = UpdateInfo(
            current_version="0.1.0",
            latest_version="0.2.0",
            has_update=True,
            download_url="http://example.com/update.exe",
            release_notes="新版本发布",
        )
        assert info.has_update is True
        assert info.current_version == "0.1.0"
        assert info.latest_version == "0.2.0"

    def test_has_update_false_when_versions_equal(self) -> None:
        """版本相同时 has_update=False。"""
        info = UpdateInfo(
            current_version="0.1.0",
            latest_version="0.1.0",
            has_update=False,
            download_url="",
            release_notes="",
        )
        assert info.has_update is False

    def test_frozen_immutable(self) -> None:
        """frozen=True: 不可变。"""
        info = UpdateInfo(
            current_version="0.1.0",
            latest_version="0.2.0",
            has_update=True,
            download_url="http://example.com/update.exe",
            release_notes="",
        )
        with pytest.raises(AttributeError):
            info.has_update = False  # type: ignore[misc]


class TestUpdateError:
    """UpdateError 测试。"""

    def test_update_error_is_exception(self) -> None:
        """UpdateError 是 Exception 的子类。"""
        assert issubclass(UpdateError, Exception)

    def test_update_error_message_in_chinese(self) -> None:
        """UpdateError 信息为中文。"""
        with pytest.raises(UpdateError, match="更新清单"):
            raise UpdateError("更新清单下载失败: 连接超时")

    def test_update_error_str(self) -> None:
        """UpdateError 的字符串表示。"""
        err = UpdateError("网络错误")
        assert str(err) == "网络错误"


class TestUpdaterCheckForUpdate:
    """Updater.check_for_update 测试。"""

    def test_has_update_true_when_latest_is_newer(self) -> None:
        """最新版本更新时返回 has_update=True。"""
        manifest = json.dumps({
            "version": "0.2.0",
            "download_url": "http://example.com/fsa_0.2.0.exe",
            "release_notes": "修复了若干问题",
        }).encode("utf-8")

        mock_response = MagicMock()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_response.read.return_value = manifest

        with patch("urllib.request.urlopen", return_value=mock_response):
            updater = Updater(
                manifest_url="http://localhost/version.json",
                current_version="0.1.0",
            )
            info = updater.check_for_update()

        assert info.has_update is True
        assert info.latest_version == "0.2.0"
        assert info.current_version == "0.1.0"
        assert info.download_url == "http://example.com/fsa_0.2.0.exe"
        assert info.release_notes == "修复了若干问题"

    def test_has_update_false_when_same_version(self) -> None:
        """相同版本时返回 has_update=False。"""
        manifest = json.dumps({
            "version": "0.1.0",
            "download_url": "http://example.com/fsa_0.1.0.exe",
            "release_notes": "",
        }).encode("utf-8")

        mock_response = MagicMock()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_response.read.return_value = manifest

        with patch("urllib.request.urlopen", return_value=mock_response):
            updater = Updater(
                manifest_url="http://localhost/version.json",
                current_version="0.1.0",
            )
            info = updater.check_for_update()

        assert info.has_update is False

    def test_has_update_false_when_current_is_newer(self) -> None:
        """当前版本更新时返回 has_update=False。"""
        manifest = json.dumps({
            "version": "0.0.9",
            "download_url": "",
            "release_notes": "",
        }).encode("utf-8")

        mock_response = MagicMock()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_response.read.return_value = manifest

        with patch("urllib.request.urlopen", return_value=mock_response):
            updater = Updater(
                manifest_url="http://localhost/version.json",
                current_version="0.1.0",
            )
            info = updater.check_for_update()

        assert info.has_update is False

    def test_urlerror_raises_update_error(self) -> None:
        """URLError 转换为 UpdateError。"""
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("连接被拒绝")):
            updater = Updater(
                manifest_url="http://localhost/version.json",
                current_version="0.1.0",
            )
            with pytest.raises(UpdateError, match="更新清单"):
                updater.check_for_update()

    def test_timeout_error_raises_update_error(self) -> None:
        """TimeoutError 转换为 UpdateError。"""
        with patch("urllib.request.urlopen", side_effect=TimeoutError("连接超时")):
            updater = Updater(
                manifest_url="http://localhost/version.json",
                current_version="0.1.0",
            )
            with pytest.raises(UpdateError, match="超时"):
                updater.check_for_update()

    def test_oserror_raises_update_error(self) -> None:
        """OSError 转换为 UpdateError。"""
        with patch("urllib.request.urlopen", side_effect=OSError("网络不可达")):
            updater = Updater(
                manifest_url="http://localhost/version.json",
                current_version="0.1.0",
            )
            with pytest.raises(UpdateError, match="网络"):
                updater.check_for_update()

    def test_invalid_json_raises_update_error(self) -> None:
        """无效 JSON 转换为 UpdateError。"""
        mock_response = MagicMock()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_response.read.return_value = b"not json"

        with patch("urllib.request.urlopen", return_value=mock_response):
            updater = Updater(
                manifest_url="http://localhost/version.json",
                current_version="0.1.0",
            )
            with pytest.raises(UpdateError, match="解析"):
                updater.check_for_update()

    def test_missing_version_key_raises_update_error(self) -> None:
        """缺少 version 字段时抛出 UpdateError。"""
        manifest = json.dumps({
            "download_url": "http://example.com/fsa.exe",
            "release_notes": "",
        }).encode("utf-8")

        mock_response = MagicMock()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_response.read.return_value = manifest

        with patch("urllib.request.urlopen", return_value=mock_response):
            updater = Updater(
                manifest_url="http://localhost/version.json",
                current_version="0.1.0",
            )
            with pytest.raises(UpdateError, match="清单"):
                updater.check_for_update()

    def test_missing_download_url_key_raises_update_error(self) -> None:
        """缺少 download_url 字段时抛出 UpdateError。"""
        manifest = json.dumps({
            "version": "0.2.0",
            "release_notes": "",
        }).encode("utf-8")

        mock_response = MagicMock()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_response.read.return_value = manifest

        with patch("urllib.request.urlopen", return_value=mock_response):
            updater = Updater(
                manifest_url="http://localhost/version.json",
                current_version="0.1.0",
            )
            with pytest.raises(UpdateError, match="清单"):
                updater.check_for_update()

    def test_manifest_url_called_with_timeout(self) -> None:
        """确认 urlopen 使用正确的 URL 和超时。"""
        manifest = json.dumps({
            "version": "0.2.0",
            "download_url": "http://example.com/fsa.exe",
            "release_notes": "",
        }).encode("utf-8")

        mock_response = MagicMock()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_response.read.return_value = manifest

        with patch("urllib.request.urlopen", return_value=mock_response) as mock_urlopen:
            updater = Updater(
                manifest_url="http://intranet/fsa/version.json",
                current_version="0.1.0",
                timeout=5.0,
            )
            updater.check_for_update()

        mock_urlopen.assert_called_once()
        args, kwargs = mock_urlopen.call_args
        assert "http://intranet/fsa/version.json" in str(args[0])
        assert kwargs.get("timeout") == 5.0

    def test_manifest_with_v_prefix_handled(self) -> None:
        """清单版本带 v 前缀时正确处理。"""
        manifest = json.dumps({
            "version": "v0.2.0",
            "download_url": "http://example.com/fsa.exe",
            "release_notes": "",
        }).encode("utf-8")

        mock_response = MagicMock()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_response.read.return_value = manifest

        with patch("urllib.request.urlopen", return_value=mock_response):
            updater = Updater(
                manifest_url="http://localhost/version.json",
                current_version="0.1.0",
            )
            info = updater.check_for_update()

        assert info.has_update is True
        assert info.latest_version == "v0.2.0"


class TestUpdaterDownload:
    """Updater.download 测试。"""

    def test_download_writes_correct_bytes(self, tmp_path) -> None:
        """download 将响应内容写入文件。"""
        content = b"fake binary content"
        dest = tmp_path / "update.exe"
        with patch(
            "urllib.request.urlopen",
            side_effect=[
                _make_manifest_response(),
                _make_http_response([content, b""]),
            ],
        ):
            updater = Updater(
                manifest_url="http://localhost/version.json",
                current_version="0.1.0",
            )
            result = updater.download("http://example.com/fsa.exe", str(dest))

        assert result == str(dest)
        assert dest.read_bytes() == content

    def test_download_chunked_content(self, tmp_path) -> None:
        """分块下载: 多个 chunk 正确拼接。"""
        chunks = [b"chunk1", b"chunk2", b"chunk3", b""]
        dest = tmp_path / "update.exe"
        with patch(
            "urllib.request.urlopen",
            side_effect=[
                _make_manifest_response(),
                _make_http_response(chunks),
            ],
        ):
            updater = Updater(
                manifest_url="http://localhost/version.json",
                current_version="0.1.0",
            )
            updater.download("http://example.com/fsa.exe", str(dest))

        assert dest.read_bytes() == b"chunk1chunk2chunk3"

    def test_download_progress_callback_invoked(self, tmp_path) -> None:
        """progress_cb 被正确调用。"""
        chunks = [b"a" * 100, b"b" * 200, b""]
        progress_records: list[tuple[int, int]] = []

        def progress_cb(downloaded: int, total: int) -> None:
            progress_records.append((downloaded, total))

        dest = tmp_path / "update.exe"
        with patch(
            "urllib.request.urlopen",
            side_effect=[
                _make_manifest_response(),
                _make_http_response(chunks),
            ],
        ):
            updater = Updater(
                manifest_url="http://localhost/version.json",
                current_version="0.1.0",
            )
            updater.download("http://example.com/fsa.exe", str(dest), progress_cb=progress_cb)

        assert len(progress_records) >= 2
        assert progress_records[0][0] == 100
        assert progress_records[-1][0] == 300
        assert progress_records[-1][1] == -1

    def test_download_without_progress_callback(self, tmp_path) -> None:
        """无 progress_cb 时下载正常完成。"""
        content = b"test content"
        dest = tmp_path / "update.exe"
        with patch(
            "urllib.request.urlopen",
            side_effect=[
                _make_manifest_response(),
                _make_http_response([content, b""]),
            ],
        ):
            updater = Updater(
                manifest_url="http://localhost/version.json",
                current_version="0.1.0",
            )
            updater.download("http://example.com/fsa.exe", str(dest))

        assert dest.read_bytes() == content

    def test_download_urlerror_raises_update_error(self, tmp_path) -> None:
        """下载时 URLError 转换为 UpdateError。"""
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("连接失败")):
            updater = Updater(
                manifest_url="http://localhost/version.json",
                current_version="0.1.0",
            )
            dest = tmp_path / "update.exe"
            with pytest.raises(UpdateError, match="下载"):
                updater.download("http://example.com/fsa.exe", str(dest))

    def test_download_timeout_error_raises_update_error(self, tmp_path) -> None:
        """下载时 TimeoutError 转换为 UpdateError。"""
        with patch("urllib.request.urlopen", side_effect=TimeoutError("超时")):
            updater = Updater(
                manifest_url="http://localhost/version.json",
                current_version="0.1.0",
            )
            dest = tmp_path / "update.exe"
            with pytest.raises(UpdateError, match="超时"):
                updater.download("http://example.com/fsa.exe", str(dest))

    def test_download_oserror_raises_update_error(self, tmp_path) -> None:
        """下载时 OSError 转换为 UpdateError。"""
        with patch("urllib.request.urlopen", side_effect=OSError("磁盘满")):
            updater = Updater(
                manifest_url="http://localhost/version.json",
                current_version="0.1.0",
            )
            dest = tmp_path / "update.exe"
            with pytest.raises(UpdateError, match="磁盘"):
                updater.download("http://example.com/fsa.exe", str(dest))


class TestUpdaterDownloadSha256:
    """download 的 SHA256 完整性校验测试。"""

    def test_download_sha256_match_succeeds(self, tmp_path) -> None:
        """清单 sha256 与文件哈希一致时下载成功。"""
        content = b"fake binary content"
        expected = hashlib.sha256(content).hexdigest()
        dest = tmp_path / "update.exe"

        with patch(
            "urllib.request.urlopen",
            side_effect=[
                _make_manifest_response(sha256=expected),
                _make_http_response([content, b""]),
            ],
        ):
            updater = Updater(
                manifest_url="http://localhost/version.json",
                current_version="0.1.0",
            )
            result = updater.download("http://example.com/fsa.exe", str(dest))

        assert result == str(dest)
        assert dest.read_bytes() == content

    def test_download_sha256_uppercase_accepted(self, tmp_path) -> None:
        """清单 sha256 为大写时归一化后仍能匹配。"""
        content = b"fake binary content"
        expected = hashlib.sha256(content).hexdigest().upper()
        dest = tmp_path / "update.exe"

        with patch(
            "urllib.request.urlopen",
            side_effect=[
                _make_manifest_response(sha256=expected),
                _make_http_response([content, b""]),
            ],
        ):
            updater = Updater(
                manifest_url="http://localhost/version.json",
                current_version="0.1.0",
            )
            result = updater.download("http://example.com/fsa.exe", str(dest))

        assert result == str(dest)
        assert dest.read_bytes() == content

    def test_download_sha256_mismatch_deletes_file_and_raises(self, tmp_path) -> None:
        """清单 sha256 与文件哈希不一致时删除文件并抛出中文 UpdateError。"""
        content = b"tampered content"
        dest = tmp_path / "update.exe"

        with patch(
            "urllib.request.urlopen",
            side_effect=[
                _make_manifest_response(sha256="0" * 64),
                _make_http_response([content, b""]),
            ],
        ):
            updater = Updater(
                manifest_url="http://localhost/version.json",
                current_version="0.1.0",
            )
            with pytest.raises(UpdateError, match="校验失败"):
                updater.download("http://example.com/fsa.exe", str(dest))

        assert not dest.exists()

    def test_download_sha256_mismatch_error_message_chinese(self, tmp_path) -> None:
        """哈希不匹配的错误信息为中文且含"请重试"。"""
        content = b"tampered content"
        dest = tmp_path / "update.exe"

        with patch(
            "urllib.request.urlopen",
            side_effect=[
                _make_manifest_response(sha256="0" * 64),
                _make_http_response([content, b""]),
            ],
        ):
            updater = Updater(
                manifest_url="http://localhost/version.json",
                current_version="0.1.0",
            )
            with pytest.raises(UpdateError) as exc_info:
                updater.download("http://example.com/fsa.exe", str(dest))

        assert "安装包校验失败" in str(exc_info.value)
        assert "请重试" in str(exc_info.value)

    def test_download_without_sha256_skips_verification(self, tmp_path) -> None:
        """清单无 sha256 字段时跳过校验并记录警告（向后兼容）。"""
        content = b"fake binary content"
        dest = tmp_path / "update.exe"

        with patch(
            "urllib.request.urlopen",
            side_effect=[
                _make_manifest_response(),
                _make_http_response([content, b""]),
            ],
        ), _capture_loguru() as sink:
            updater = Updater(
                manifest_url="http://localhost/version.json",
                current_version="0.1.0",
            )
            result = updater.download("http://example.com/fsa.exe", str(dest))

        assert result == str(dest)
        assert dest.read_bytes() == content
        assert "sha256" in sink.getvalue()


class TestUpdaterDownloadProgress:
    """download 进度回调的 total 参数测试。"""

    def test_download_progress_total_from_content_length(self, tmp_path) -> None:
        """响应含 Content-Length 时进度回调传入真实总字节数。"""
        chunks = [b"a" * 100, b"b" * 200, b""]
        progress_records: list[tuple[int, int]] = []
        dest = tmp_path / "update.exe"

        with patch(
            "urllib.request.urlopen",
            side_effect=[
                _make_manifest_response(),
                _make_http_response(chunks, headers={"Content-Length": "300"}),
            ],
        ):
            updater = Updater(
                manifest_url="http://localhost/version.json",
                current_version="0.1.0",
            )
            updater.download(
                "http://example.com/fsa.exe",
                str(dest),
                progress_cb=lambda d, t: progress_records.append((d, t)),
            )

        assert progress_records[-1] == (300, 300)

    def test_download_progress_total_minus_one_without_content_length(self, tmp_path) -> None:
        """响应无 Content-Length 时进度回调传入总字节数 -1。"""
        chunks = [b"a" * 100, b""]
        progress_records: list[tuple[int, int]] = []
        dest = tmp_path / "update.exe"

        with patch(
            "urllib.request.urlopen",
            side_effect=[
                _make_manifest_response(),
                _make_http_response(chunks),
            ],
        ):
            updater = Updater(
                manifest_url="http://localhost/version.json",
                current_version="0.1.0",
            )
            updater.download(
                "http://example.com/fsa.exe",
                str(dest),
                progress_cb=lambda d, t: progress_records.append((d, t)),
            )

        assert progress_records[0][0] == 100
        assert progress_records[0][1] == -1
