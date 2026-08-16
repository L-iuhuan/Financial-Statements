"""资源路径解析: 同时支持开发模式与 PyInstaller 冻结模式。"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path


def resource_path(relative: str) -> Path:
    """解析资源文件路径。

    解析顺序:
    1. 冻结模式: PyInstaller bundle 目录 (sys._MEIPASS) 或 exe 所在目录
    2. 开发模式: 项目根目录 (本文件上溯 3 级)
    3. 兜底: 当前工作目录 (允许用户将资源放在 exe 旁边)

    Args:
        relative: 相对路径, 如 "cas_gouji_rule_library.json"

    Returns:
        第一个存在的候选路径; 都不存在时返回首个候选 (便于上层报"文件不存在")
    """
    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        bundle = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        candidates.append(bundle / relative)
        candidates.append(Path(sys.executable).parent / relative)
    else:
        candidates.append(Path(__file__).resolve().parents[3] / relative)
    candidates.append(Path.cwd() / relative)

    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def sha256_file(path: str | Path) -> str:
    """流式计算文件 SHA256 十六进制摘要 (审计证据链用)。

    文件不存在或读取失败时返回空字符串, 不中断主流程。
    """
    try:
        digest = hashlib.sha256()
        with open(path, "rb") as f:
            while True:
                chunk = f.read(8192)
                if not chunk:
                    break
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return ""
