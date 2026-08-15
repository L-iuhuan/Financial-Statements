"""版本号一致性测试: APP_VERSION / pyproject.toml / installer.iss 必须同步。"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

from fsa.core.version import APP_VERSION

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_PYPROJECT = _PROJECT_ROOT / "pyproject.toml"
_INSTALLER = _PROJECT_ROOT / "installer.iss"


def test_app_version_is_current_release() -> None:
    """当前发布版本应为 0.4.1 (v0.4.0 后的补丁版本)。"""
    assert APP_VERSION == "0.4.1"


def test_pyproject_version_matches_app_version() -> None:
    """pyproject 打包元数据版本与运行时 APP_VERSION 一致。"""
    data = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))
    assert data["project"]["version"] == APP_VERSION


def test_installer_version_matches_app_version() -> None:
    """Inno Setup 安装包版本与运行时 APP_VERSION 一致。"""
    text = _INSTALLER.read_text(encoding="utf-8")
    match = re.search(r'#define MyAppVersion "([^"]+)"', text)
    assert match is not None, "installer.iss 缺少 MyAppVersion"
    assert match.group(1) == APP_VERSION
