"""内网自动更新模块。

通过 HTTP 获取版本清单 JSON，比较版本号，下载更新包。
使用 Python 标准库 urllib.request，不依赖 requests 库。
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass


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

        Args:
            url: 下载地址
            dest_path: 目标文件路径
            progress_cb: 进度回调，参数为 (已下载字节数, 总字节数)

        Returns:
            目标文件路径

        Raises:
            UpdateError: 网络错误或写入文件失败时抛出。
        """
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
                with open(dest_path, "wb") as f:
                    while True:
                        chunk = response.read(self._CHUNK_SIZE)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_cb is not None:
                            progress_cb(downloaded, -1)
        except OSError as e:
            raise UpdateError(f"下载失败: 磁盘写入错误 ({e})") from e

        return dest_path
