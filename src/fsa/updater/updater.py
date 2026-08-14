"""内网自动更新模块。

通过 HTTP 获取版本清单 JSON，比较版本号，下载更新包。
使用 Python 标准库 urllib.request，不依赖 requests 库。
"""

from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass

from loguru import logger


class UpdateError(Exception):
    """更新过程异常，错误信息为中文，面向财务用户。"""


@dataclass(frozen=True)
class UpdateInfo:
    """更新信息数据类。

    Attributes:
        current_version: 当前软件版本
        latest_version: 最新可用版本
        has_update: 是否有可用更新
        download_url: 更新包下载地址
        release_notes: 更新说明
    """

    current_version: str
    latest_version: str
    has_update: bool
    download_url: str
    release_notes: str


def compare_versions(current: str, latest: str) -> int:
    """比较两个版本号，类似 semver 但不严格要求三段。

    版本号按 '.' 分割，逐段数值比较。忽略前导 'v' 或 'V'。
    段数不同时，短版本用 0 补齐。

    Args:
        current: 当前版本号，如 "0.1.0"
        latest: 最新版本号，如 "v0.2.0"

    Returns:
        -1: current < latest
         0: current == latest
         1: current > latest
    """
    def _parse(version: str) -> list[int]:
        cleaned = version.lstrip("vV")
        parts = cleaned.split(".")
        return [int(p) for p in parts]

    cur_parts = _parse(current)
    lat_parts = _parse(latest)

    max_len = max(len(cur_parts), len(lat_parts))
    cur_parts += [0] * (max_len - len(cur_parts))
    lat_parts += [0] * (max_len - len(lat_parts))

    for cv, lv in zip(cur_parts, lat_parts, strict=True):
        if cv < lv:
            return -1
        if cv > lv:
            return 1
    return 0


class Updater:
    """内网更新检查器。

    从内网 HTTP 服务器获取版本清单 JSON，比较版本并下载更新包。

    Attributes:
        manifest_url: 版本清单 JSON 的 URL
        current_version: 当前软件版本号
        timeout: HTTP 请求超时时间（秒）
    """

    _CHUNK_SIZE: int = 8192

    def __init__(
        self,
        manifest_url: str,
        current_version: str,
        timeout: float = 10.0,
    ) -> None:
        self._manifest_url = manifest_url
        self._current_version = current_version
        self._timeout = timeout

    def check_for_update(self) -> UpdateInfo:
        """获取版本清单并比较版本号。

        Returns:
            UpdateInfo 包含是否有更新、最新版本号、下载地址等信息。

        Raises:
            UpdateError: 网络错误、清单解析失败、缺少必需字段时抛出。
        """
        try:
            response = urllib.request.urlopen(
                self._manifest_url, timeout=self._timeout
            )
        except urllib.error.URLError as e:
            raise UpdateError(f"更新清单下载失败: 网络连接错误 ({e.reason})") from e
        except TimeoutError as e:
            raise UpdateError("更新清单下载失败: 连接超时，请检查网络") from e
        except OSError as e:
            raise UpdateError(f"更新清单下载失败: 网络错误 ({e})") from e

        try:
            with response:
                raw = response.read()
        except OSError as e:
            raise UpdateError(f"更新清单读取失败: ({e})") from e

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise UpdateError(f"更新清单解析失败: JSON 格式错误 ({e})") from e

        if not isinstance(data, dict):
            raise UpdateError("更新清单格式错误: 应为 JSON 对象")

        try:
            latest_version = data["version"]
        except KeyError:
            raise UpdateError("更新清单缺少必需字段: version") from None

        try:
            download_url = data["download_url"]
        except KeyError:
            raise UpdateError("更新清单缺少必需字段: download_url") from None

        release_notes = data.get("release_notes", "")

        latest_version_str = str(latest_version)
        cmp = compare_versions(self._current_version, latest_version_str)
        has_update = cmp < 0

        return UpdateInfo(
            current_version=self._current_version,
            latest_version=latest_version_str,
            has_update=has_update,
            download_url=str(download_url),
            release_notes=str(release_notes),
        )

    def download(
        self,
        url: str,
        dest_path: str,
        progress_cb: Callable[[int, int], None] | None = None,
    ) -> str:
        """从指定 URL 流式下载文件到本地路径。

        下载前从更新清单读取期望的 sha256；清单提供该字段时，下载完成后
        比对文件哈希，不匹配则删除文件并抛出 UpdateError。

        Args:
            url: 下载地址
            dest_path: 目标文件路径
            progress_cb: 进度回调，参数为 (已下载字节数, 总字节数)

        Returns:
            目标文件路径

        Raises:
            UpdateError: 网络错误、写入失败或哈希校验失败时抛出。
        """
        expected_sha256 = self._fetch_expected_sha256()
        try:
            response = urllib.request.urlopen(url, timeout=self._timeout)
        except urllib.error.URLError as e:
            raise UpdateError(f"下载失败: 网络连接错误 ({e.reason})") from e
        except TimeoutError as e:
            raise UpdateError("下载失败: 连接超时，请检查网络") from e
        except OSError as e:
            raise UpdateError(f"下载失败: 磁盘或网络错误 ({e})") from e

        try:
            with response:
                downloaded = 0
                total = self._read_content_length(response)
                with open(dest_path, "wb") as f:
                    while True:
                        chunk = response.read(self._CHUNK_SIZE)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_cb is not None:
                            progress_cb(downloaded, total)
        except OSError as e:
            raise UpdateError(f"下载失败: 磁盘写入错误 ({e})") from e

        if expected_sha256 is not None:
            self._verify_sha256(dest_path, expected_sha256)

        return dest_path

    def _fetch_expected_sha256(self) -> str | None:
        """从更新清单读取期望的 sha256 哈希值。

        清单获取失败、格式错误或缺少 sha256 字段时返回 None，并记录警告后
        跳过校验（保持向后兼容，不阻塞下载）。

        Returns:
            期望的 sha256 十六进制小写值；无法获取时返回 None
        """
        try:
            response = urllib.request.urlopen(self._manifest_url, timeout=self._timeout)
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            logger.warning(f"获取更新清单失败，跳过安装包完整性校验: {e}")
            return None
        try:
            with response:
                data = json.loads(response.read())
        except (OSError, ValueError) as e:
            logger.warning(f"更新清单解析失败，跳过安装包完整性校验: {e}")
            return None
        if not isinstance(data, dict):
            logger.warning("更新清单格式错误，跳过安装包完整性校验")
            return None
        expected = data.get("sha256")
        if not expected:
            logger.warning("更新清单未提供 sha256 字段，跳过安装包完整性校验")
            return None
        return str(expected).strip().lower()

    def _read_content_length(self, response: object) -> int:
        """从响应头读取 Content-Length，无该头或值非法时返回 -1。

        Args:
            response: urlopen 返回的响应对象

        Returns:
            Content-Length 数值；缺失或非法时返回 -1
        """
        headers = getattr(response, "headers", None)
        getter = getattr(headers, "get", None)
        if getter is None:
            return -1
        content_length = getter("Content-Length")
        if not isinstance(content_length, str):
            return -1
        try:
            return int(content_length)
        except ValueError:
            return -1

    def _verify_sha256(self, file_path: str, expected_sha256: str) -> None:
        """计算文件 SHA256 并与期望值比对，不匹配则删除文件并抛出 UpdateError。

        Args:
            file_path: 已下载的安装包路径
            expected_sha256: 期望的 SHA256 十六进制小写值

        Raises:
            UpdateError: 哈希不匹配或无法读取文件时抛出
        """
        try:
            actual = compute_sha256(file_path)
        except OSError as e:
            raise UpdateError(f"安装包校验失败: 无法读取下载文件 ({e})") from e
        if actual == expected_sha256:
            return
        try:
            os.remove(file_path)
        except OSError:
            logger.warning(f"删除校验失败的安装包失败: {file_path}")
        raise UpdateError("安装包校验失败，文件可能被篡改或损坏，请重试")


def compute_sha256(file_path: str) -> str:
    """流式计算文件 SHA256 十六进制小写摘要。

    Args:
        file_path: 文件路径

    Returns:
        SHA256 十六进制小写摘要

    Raises:
        OSError: 无法读取文件时抛出
    """
    digest = hashlib.sha256()
    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()
