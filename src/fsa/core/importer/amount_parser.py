"""统一金额解析工具: 兼容报表中常见的数字格式。

将单元格原始值解析为 float:
- 千分位逗号 / 空白剔除 (如 "1,000,000.50")
- 括号负数 (如 "(1,291,800.12)" -> -1291800.12)
- 占位符 ("-"、"—" 等) -> 0.0
- 科学计数法 (如 "1.5e6")
- 普通 float / int

严格区分"真空值"与"占位符"，避免把真空值误转 0 制造虚假平衡:
- 空单元格 (None / 纯空白) -> None
- 占位符 ("-"、"—") -> 0.0

遵循 P1 宁可漏报不可误报: 无法解析的值返回 None，由调用方跳过。
"""

from __future__ import annotations

import math
import re

# 报表中的占位符(表示"无数据"而非数字): 半角/全角连字符、破折号、减号
_PLACEHOLDERS = frozenset({"-", "--", "—", "–", "－", "−"})

# 千分位逗号与各类空白(半角/全角空格、不间断空格)
_STRIP_RE = re.compile(r"[,，\s\u00a0\u3000]")

# 括号包裹表示负数: 半角 (1,000) 与全角 （1,000）
_PAREN_RE = re.compile(r"^[（(](.+)[)）]$")


def parse_amount(value: object) -> float | None:
    """将单元格值解析为金额。

    Args:
        value: 单元格原始值 (None / bool / int / float / str)

    Returns:
        金额 float; 空单元格 (None 或纯空白) 与无法解析的值返回 None;
        占位符 ("-" / "—") 返回 0.0。
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return None if math.isnan(number) else number

    text = str(value).strip()
    if not text:
        return None
    if text in _PLACEHOLDERS:
        return 0.0

    negative = False
    paren_match = _PAREN_RE.match(text)
    if paren_match is not None:
        negative = True
        text = paren_match.group(1).strip()

    cleaned = _STRIP_RE.sub("", text)
    if not cleaned:
        return None
    try:
        number = float(cleaned)
    except ValueError:
        return None
    if negative:
        number = -number
    if math.isnan(number):
        return None
    return number
