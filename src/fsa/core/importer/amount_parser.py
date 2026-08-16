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

# 行尾"元"后缀 (如 "1,000.50元")
_TRAILING_YUAN_RE = re.compile(r"元$")

# 金额单位 -> 换算为元的乘数 (长单位优先匹配, 避免"万元"被拆成"元")
_AMOUNT_UNITS: dict[str, float] = {
    "百万元": 1_000_000.0,
    "亿元": 100_000_000.0,
    "万元": 10_000.0,
    "千元": 1_000.0,
    "元": 1.0,
}
_UNIT_RE = re.compile(r"(百万元|亿元|万元|千元|元)")


def detect_amount_unit(text: object) -> str | None:
    """从表头/标题/单元格文本中识别金额单位。

    支持: 元 / 千元 / 万元 / 百万元 / 亿元。
    未识别到明确单位时返回 None。
    """
    if text is None:
        return None
    value = str(text)
    # 避免把"单元"、"人民币元"以外的普通"元"字误判? 仅识别数量级词或独立"元"
    match = _UNIT_RE.search(value)
    if match is None:
        return None
    token = match.group(1)
    if token == "元" and not re.search(r"(金额单位|单位[:：]|人民币元|[(（]元[)）])", value):
        return None
    return token


def to_yuan(amount: float, unit: str | None) -> float:
    """将金额按单位换算为元; 未知单位按元处理 (保守不放大差异)。"""
    if unit is None:
        return amount
    return amount * _AMOUNT_UNITS.get(unit, 1.0)


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
    # P3: 去除行尾"元"后缀
    text = _TRAILING_YUAN_RE.sub("", text).strip()
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
