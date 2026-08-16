"""版本通道配置: internal(内部版) / general(通用版)。

构建时由 scripts/build_installer.ps1 写入 `_edition_override.py` 固化通道;
开发环境可用环境变量 FSA_EDITION 覆盖, 便于本地切换验证。
内部版与通用版功能一致, 差异仅在:
- 内部版: 启动时要求计算机已加入域, 并按白名单校验域名
- 内部版: 更新通道默认指向内部共享盘/内网清单
- 通用版: 无域检查, 更新通道默认 HTTPS 清单
"""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from dataclasses import dataclass

EDITION_INTERNAL = "internal"
EDITION_GENERAL = "general"
_KNOWN_EDITIONS = frozenset({EDITION_INTERNAL, EDITION_GENERAL})

# 内部版允许的域名白名单 (构建时可覆写为实际 AD 域名, 如 "corp.example.com")。
# 空元组 = 不限制具体域名, 但仍要求计算机已加入域。
_DEFAULT_DOMAIN_WHITELIST: tuple[str, ...] = ()

# 通用版默认 HTTPS 更新地址 (未配置时为 "", 软件内可编辑)。
_DEFAULT_GENERAL_UPDATE_URL = ""
# 内部版默认更新清单地址 (共享盘 UNC 或内网 HTTP, 未配置时为 "")。
_DEFAULT_INTERNAL_UPDATE_URL = ""


@dataclass(frozen=True)
class EditionConfig:
    """版本通道的静态配置。"""

    key: str
    display_name: str
    require_domain: bool
    domain_whitelist: tuple[str, ...]
    default_update_url: str

    @property
    def is_internal(self) -> bool:
        """是否为内部版。"""
        return self.key == EDITION_INTERNAL


def _load_override() -> str | None:
    """读取构建期写入的通道标识 (打包时固化, 源仓库不提交)。"""
    try:
        from fsa.core._edition_override import EDITION as override
    except ImportError:
        return None
    return str(override).strip().lower() if override else None


def _is_frozen() -> bool:
    """是否为 PyInstaller 打包版。

    打包版是发给最终用户的正式产物，其版本通道与授权闸门在构建期固化，
    必须忽略环境变量，防止终端用户用 FSA_EDITION 等变量绕过内部版域检查。
    """
    return bool(getattr(sys, "frozen", False))


def detect_edition_key() -> str:
    """检测当前通道: 环境变量(仅开发模式) > 构建期覆写 > 通用版。"""
    # 打包版忽略环境变量: 授权闸门不得被环境变量覆盖 (B6-1)
    if not _is_frozen():
        env_value = os.getenv("FSA_EDITION", "").strip().lower()
        if env_value in _KNOWN_EDITIONS:
            return env_value
    override = _load_override()
    if override in _KNOWN_EDITIONS:
        return override
    return EDITION_GENERAL


def get_edition_config() -> EditionConfig:
    """返回当前通道配置 (含域名白名单与默认更新地址)。"""
    key = detect_edition_key()
    if key == EDITION_INTERNAL:
        whitelist = _load_domain_whitelist()
        return EditionConfig(
            key=key,
            display_name="内部版",
            require_domain=True,
            domain_whitelist=whitelist,
            default_update_url=_load_default_update_url(_DEFAULT_INTERNAL_UPDATE_URL),
        )
    return EditionConfig(
        key=key,
        display_name="通用版",
        require_domain=False,
        domain_whitelist=(),
        default_update_url=_load_default_update_url(_DEFAULT_GENERAL_UPDATE_URL),
    )


def _load_default_update_url(fallback: str) -> str:
    """加载构建期固化/环境变量指定的默认更新清单地址。

    打包版忽略环境变量: 更新通道属授权配置, 不得被环境变量重定向 (B6-1)。
    """
    if not _is_frozen():
        env_value = os.getenv("FSA_UPDATE_MANIFEST_URL", "").strip()
        if env_value:
            return env_value
    try:
        from fsa.core._edition_override import DEFAULT_UPDATE_URL as override
    except ImportError:
        return fallback
    if not isinstance(override, str) or not override.strip():
        return fallback
    return override.strip()


def _load_domain_whitelist() -> tuple[str, ...]:
    """加载内部版域名白名单 (环境变量(仅开发模式) > 构建期覆写 > 默认空)。

    环境变量 FSA_DOMAIN_WHITELIST 支持逗号分隔, 供开发/部署调试临时调整;
    构建期 `_edition_override.py` 中的 DOMAIN_WHITELIST 固化正式白名单。
    打包版忽略环境变量: 域白名单是授权闸门, 不得被环境变量放宽 (B6-1)。
    """
    if not _is_frozen():
        env_value = os.getenv("FSA_DOMAIN_WHITELIST", "").strip()
        if env_value:
            return tuple(
                part.strip().lower() for part in env_value.replace("；", ",").replace(";", ",").split(",") if part.strip()
            )
    try:
        from fsa.core._edition_override import DOMAIN_WHITELIST as override
    except ImportError:
        return _DEFAULT_DOMAIN_WHITELIST
    if not isinstance(override, tuple | list):
        return _DEFAULT_DOMAIN_WHITELIST
    return tuple(str(item).strip().lower() for item in override if str(item).strip())


@dataclass(frozen=True)
class DomainCheckResult:
    """域检查结果。"""

    allowed: bool
    domain: str = ""
    reason: str = ""
    source: str = ""

    @property
    def ok(self) -> bool:
        """是否允许继续启动。"""
        return self.allowed


def check_domain_access(
    env: Mapping[str, str] | None = None,
    whitelist: tuple[str, ...] | None = None,
) -> DomainCheckResult:
    """校验计算机是否满足内部版域控制要求。

    判定顺序:
    1. USERDNSDOMAIN 存在 -> 已加入 AD 域
    2. 回退 USERDOMAIN; 仅在白名单显式包含该名时接受 (工作组机器
       USERDOMAIN 常等于计算机名, 不能单独作为域证据)
    3. 白名单非空时, 域名必须命中白名单 (大小写不敏感)

    Args:
        env: 环境变量映射, 测试注入用; None 时读取 os.environ
        whitelist: 域名白名单; None 时读取当前通道配置

    Returns:
        DomainCheckResult
    """
    environ: Mapping[str, str] = os.environ if env is None else env
    if whitelist is None:
        whitelist = get_edition_config().domain_whitelist
    normalized_whitelist = tuple(item.strip().lower() for item in whitelist)

    dns_domain = str(environ.get("USERDNSDOMAIN", "")).strip().lower()
    user_domain = str(environ.get("USERDOMAIN", "")).strip().lower()

    if dns_domain:
        domain = dns_domain
        source = "USERDNSDOMAIN"
    elif user_domain and normalized_whitelist and user_domain in normalized_whitelist:
        # 未加入域时 USERDOMAIN 常等于计算机名; 只有白名单显式接受才放行
        domain = user_domain
        source = "USERDOMAIN"
    else:
        return DomainCheckResult(
            allowed=False,
            domain=user_domain or dns_domain,
            reason=("未检测到域环境 (USERDNSDOMAIN 为空)。内部版仅允许在加入企业域并完成授权的计算机上运行。"),
            source="USERDNSDOMAIN",
        )

    if normalized_whitelist and domain not in normalized_whitelist:
        return DomainCheckResult(
            allowed=False,
            domain=domain,
            reason=(f"当前计算机域「{domain}」不在内部版授权白名单中，请联系管理员。"),
            source=source,
        )

    return DomainCheckResult(
        allowed=True,
        domain=domain,
        reason="域检查通过",
        source=source,
    )
