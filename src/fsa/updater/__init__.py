"""内网自动更新模块。

提供版本检查、比较和下载功能。
使用 Python 标准库 urllib.request，不依赖 requests 库。
"""

from fsa.updater.updater import UpdateError, UpdateInfo, Updater, compare_versions

__all__ = ["UpdateError", "UpdateInfo", "Updater", "compare_versions"]
