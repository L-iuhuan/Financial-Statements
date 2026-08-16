"""core.edition 模块测试: 通道检测与内部版域控制。"""

from __future__ import annotations

from fsa.core.edition import (
    EDITION_GENERAL,
    EDITION_INTERNAL,
    DomainCheckResult,
    check_domain_access,
    detect_edition_key,
    get_edition_config,
)


class TestDetectEdition:
    """通道检测优先级: 环境变量 > 构建覆写 > 通用版。"""

    def test_defaults_to_general(self, monkeypatch) -> None:
        monkeypatch.delenv("FSA_EDITION", raising=False)
        assert detect_edition_key() == EDITION_GENERAL
        assert get_edition_config().require_domain is False

    def test_env_internal(self, monkeypatch) -> None:
        monkeypatch.setenv("FSA_EDITION", "internal")
        config = get_edition_config()
        assert config.key == EDITION_INTERNAL
        assert config.display_name == "内部版"
        assert config.require_domain is True

    def test_invalid_env_falls_back_to_general(self, monkeypatch) -> None:
        monkeypatch.setenv("FSA_EDITION", "premium")
        assert detect_edition_key() == EDITION_GENERAL

    def test_domain_whitelist_env_parsing(self, monkeypatch) -> None:
        monkeypatch.setenv("FSA_EDITION", "internal")
        monkeypatch.setenv("FSA_DOMAIN_WHITELIST", "CORP.example.com；B.CN, C")
        assert get_edition_config().domain_whitelist == (
            "corp.example.com",
            "b.cn",
            "c",
        )


class TestBuildOverride:
    """构建期 _edition_override 模块固化通道。"""

    def _install_override(self, monkeypatch, edition: str, whitelist: tuple = (), update_url: str = "") -> None:
        import sys
        from types import ModuleType

        module = ModuleType("fsa.core._edition_override")
        module.EDITION = edition
        module.DOMAIN_WHITELIST = whitelist
        module.DEFAULT_UPDATE_URL = update_url
        monkeypatch.setitem(sys.modules, "fsa.core._edition_override", module)

    def test_override_sets_internal_edition(self, monkeypatch) -> None:
        monkeypatch.delenv("FSA_EDITION", raising=False)
        self._install_override(
            monkeypatch,
            "internal",
            whitelist=("corp.example.com",),
            update_url="\\\\server\\share\\version.json",
        )
        config = get_edition_config()
        assert config.key == EDITION_INTERNAL
        assert config.require_domain is True
        assert config.domain_whitelist == ("corp.example.com",)
        assert config.default_update_url == "\\\\server\\share\\version.json"

    def test_env_beats_override(self, monkeypatch) -> None:
        self._install_override(monkeypatch, "internal")
        monkeypatch.setenv("FSA_EDITION", "general")
        assert detect_edition_key() == EDITION_GENERAL


class TestFrozenIgnoresEnv:
    """打包版 (sys.frozen=True) 忽略环境变量: 授权闸门不得被环境变量覆盖 (B6-1)。"""

    def _install_override(self, monkeypatch, edition: str, whitelist: tuple = (), update_url: str = "") -> None:
        import sys
        from types import ModuleType

        module = ModuleType("fsa.core._edition_override")
        module.EDITION = edition
        module.DOMAIN_WHITELIST = whitelist
        module.DEFAULT_UPDATE_URL = update_url
        monkeypatch.setitem(sys.modules, "fsa.core._edition_override", module)

    def test_frozen_ignores_edition_env(self, monkeypatch) -> None:
        """打包版设置 FSA_EDITION=general 也无法绕过内部版通道。"""
        import sys

        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setenv("FSA_EDITION", "general")
        self._install_override(monkeypatch, "internal")
        assert detect_edition_key() == EDITION_INTERNAL

    def test_frozen_without_override_defaults_to_general(self, monkeypatch) -> None:
        """打包版无构建期覆写时, 即使 FSA_EDITION=internal 也回落通用版。"""
        import sys

        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setenv("FSA_EDITION", "internal")
        assert detect_edition_key() == EDITION_GENERAL

    def test_frozen_ignores_domain_whitelist_env(self, monkeypatch) -> None:
        """打包版忽略 FSA_DOMAIN_WHITELIST, 只认构建期固化白名单。"""
        import sys

        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setenv("FSA_DOMAIN_WHITELIST", "evil.example.com")
        self._install_override(monkeypatch, "internal", whitelist=("corp.example.com",))
        assert get_edition_config().domain_whitelist == ("corp.example.com",)

    def test_frozen_ignores_update_url_env(self, monkeypatch) -> None:
        """打包版忽略 FSA_UPDATE_MANIFEST_URL, 只认构建期固化更新地址。"""
        import sys

        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setenv("FSA_UPDATE_MANIFEST_URL", "http://evil.example.com/version.json")
        self._install_override(monkeypatch, "internal", update_url="\\\\server\\share\\version.json")
        assert get_edition_config().default_update_url == "\\\\server\\share\\version.json"


class TestDomainCheck:
    """内部版域控制判定。"""

    def test_allowed_with_dns_domain_and_empty_whitelist(self) -> None:
        result = check_domain_access(env={"USERDNSDOMAIN": "CORP.EXAMPLE.COM"}, whitelist=())
        assert isinstance(result, DomainCheckResult)
        assert result.allowed is True
        assert result.domain == "corp.example.com"
        assert result.source == "USERDNSDOMAIN"

    def test_allowed_when_domain_in_whitelist(self) -> None:
        result = check_domain_access(
            env={"USERDNSDOMAIN": "corp.example.com"},
            whitelist=("CORP.EXAMPLE.COM",),
        )
        assert result.allowed is True

    def test_blocked_when_domain_not_in_whitelist(self) -> None:
        result = check_domain_access(
            env={"USERDNSDOMAIN": "other.example.com"},
            whitelist=("corp.example.com",),
        )
        assert result.allowed is False
        assert "不在内部版授权白名单" in result.reason

    def test_blocked_when_not_domain_joined(self) -> None:
        result = check_domain_access(env={"USERDOMAIN": "MYPC", "COMPUTERNAME": "MYPC"}, whitelist=())
        assert result.allowed is False
        assert "USERDNSDOMAIN" in result.reason

    def test_workgroup_userdomain_only_allowed_if_whitelisted(self) -> None:
        allowed = check_domain_access(env={"USERDOMAIN": "MYPC"}, whitelist=("mypc",))
        blocked = check_domain_access(env={"USERDOMAIN": "MYPC"}, whitelist=("corp.example.com",))
        assert allowed.allowed is True
        assert allowed.source == "USERDOMAIN"
        assert blocked.allowed is False
