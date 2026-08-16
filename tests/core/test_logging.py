"""日志轮转配置的默认目录计算测试。"""

from __future__ import annotations

from pathlib import Path

from fsa.core import logging as logging_config


class TestDefaultLogDir:
    def test_windows_uses_localappdata(self, monkeypatch) -> None:
        monkeypatch.setattr(logging_config.sys, "platform", "win32")
        monkeypatch.setenv("LOCALAPPDATA", "C:\\Users\\auditor\\AppData\\Local")
        assert logging_config.default_log_dir() == Path("C:\\Users\\auditor\\AppData\\Local/FSA/logs")

    def test_linux_uses_home_dot_fsa(self, monkeypatch) -> None:
        """非 Windows 平台回落 ~/.fsa/logs (mock Path.home, 不依赖平台私有行为)。"""
        monkeypatch.setattr(logging_config.sys, "platform", "linux")
        monkeypatch.setattr(logging_config.Path, "home", classmethod(lambda cls: Path("/home/auditor")))
        assert logging_config.default_log_dir() == Path("/home/auditor/.fsa/logs")
