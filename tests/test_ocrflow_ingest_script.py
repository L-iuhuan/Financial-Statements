"""OCRFlow 知识库导入脚本的路径转换辅助函数测试 (无需 OCRFlow)。"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "ingest_knowledge_ocrflow.py"


@pytest.fixture(scope="module")
def module():
    spec = importlib.util.spec_from_file_location("ingest_knowledge_ocrflow", _SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestPathTranslation:
    def test_windows_path_to_local_on_linux(self, module, monkeypatch) -> None:
        monkeypatch.setattr(module.sys, "platform", "linux")
        local = module._to_local_path(Path("C:\\Software\\OCRFlow\\OCRFlow.exe"))
        assert str(local).replace("\\", "/") == "/mnt/c/Software/OCRFlow/OCRFlow.exe"

    def test_local_path_unchanged(self, module, monkeypatch) -> None:
        monkeypatch.setattr(module.sys, "platform", "win32")
        assert module._to_local_path(Path("D:\\资料\\a.pdf")) == Path("D:\\资料\\a.pdf")

    def test_to_windows_path(self, module) -> None:
        if sys.platform.startswith("linux"):
            result = module._to_windows_path(Path("/mnt/d/资料/a.pdf"))
            assert result.startswith("D:\\")
            assert "资料" in result
            assert result.endswith("资料\\a.pdf")
