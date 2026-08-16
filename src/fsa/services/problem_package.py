"""问题包导出: 收集日志/数据库/版本信息, 打包 zip 供支持排查。

- 日志目录: 应用日志轮转目录 (默认见 core.logging)
- 数据库: SQLite data.db (不含密码; 导出前建议用户知悉数据敏感性)
- diagnosis.txt: 版本/平台/Python 环境信息
"""

from __future__ import annotations

import platform
import sys
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from fsa.core.version import APP_VERSION

_DEFAULT_DB_PATH = Path.home() / ".fsa" / "data.db"


@dataclass(frozen=True)
class ProblemPackageResult:
    """问题包导出结果。"""

    path: Path
    file_count: int
    note: str


def create_problem_package(
    output_path: Path | str,
    *,
    log_dir: Path | str | None = None,
    db_path: Path | str | None = None,
) -> ProblemPackageResult:
    """收集日志/数据库/诊断信息并写入 zip。

    Args:
        output_path: 目标 zip 路径
        log_dir: 日志目录; None 时自动探测默认目录
        db_path: 数据库路径; None 时探测默认位置

    Returns:
        ProblemPackageResult

    Raises:
        OSError: 无法写入目标文件
    """
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    base = Path(log_dir) if log_dir is not None else _default_log_dir()
    db = Path(db_path) if db_path is not None else _DEFAULT_DB_PATH

    file_count = 0
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(base.glob("*.log")):
            if path.is_file():
                zf.write(path, arcname=f"logs/{path.name}")
                file_count += 1
        if db.is_file():
            zf.write(db, arcname="database/data.db")
            file_count += 1
        diagnosis = _build_diagnosis_text(db)
        zf.writestr("diagnosis.txt", diagnosis)
        file_count += 1
    note = "问题包不含 API 密钥；数据库可能包含财务文件路径与历史结果，请勿外发。"
    return ProblemPackageResult(path=target, file_count=file_count, note=note)


def _default_log_dir() -> Path:
    from fsa.core.logging import default_log_dir

    return default_log_dir()


def _build_diagnosis_text(db: Path) -> str:
    lines = [
        "财务报表勾稽校验系统 问题诊断包",
        f"生成时间: {datetime.now():%Y-%m-%d %H:%M:%S}",
        f"应用版本: {APP_VERSION}",
        f"平台: {platform.platform()}",
        f"Python: {sys.version.split()[0]}",
        f"数据库: {db} (存在={db.is_file()})",
        "",
        "说明: 请将本 zip 提交给系统管理员; 如需保护敏感信息, 可先删除 database/data.db。",
    ]
    return "\n".join(lines) + "\n"
