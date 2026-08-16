"""应用日志文件轮转配置。

loguru 默认只写 stderr; 发布版额外写入用户目录日志文件:
- 默认位置: %LOCALAPPDATA%/FSA/logs (Windows) 或 ~/.fsa/logs
- 5 MB 轮转, 保留 30 天, 归档 zip 压缩
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from loguru import logger

_configured_path: str | None = None


def default_log_dir() -> Path:
    """默认日志目录 (用户可写目录, 不依赖安装位置)。"""
    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base:
            return Path(base) / "FSA" / "logs"
    return Path.home() / ".fsa" / "logs"


def configure_file_logging(log_dir: Path | str | None = None) -> Path:
    """配置文件日志轮转 (幂等, 多次调用返回同一目录)。"""
    global _configured_path
    if _configured_path is not None:
        return Path(_configured_path)
    base = Path(log_dir) if log_dir is not None else default_log_dir()
    base.mkdir(parents=True, exist_ok=True)
    logger.add(
        base / "fsa_{time:YYYY-MM-DD}.log",
        rotation="5 MB",
        retention="30 days",
        compression="zip",
        enqueue=True,
        encoding="utf-8",
        level="DEBUG",
        format=("{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}"),
        backtrace=False,
        diagnose=True,
    )
    _configured_path = str(base)
    logger.info(f"日志文件已启用: {base}")
    return base
