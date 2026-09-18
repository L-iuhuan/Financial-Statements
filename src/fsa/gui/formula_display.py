"""公式中文化 (兼容再导出): 实现已移至 core/engine/formula_display.py。

2026-09-18 移动原因: 审计底稿导出器 (core/exporter) 需要中文公式列,
core 禁止 import gui。本文件保留 re-export, gui 既有消费方无需改动。
"""

from __future__ import annotations

from fsa.core.engine.formula_display import formula_to_chinese

__all__ = ["formula_to_chinese"]
