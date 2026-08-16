"""统一金额解析工具: 兼容报表中常见的数字格式。

将单元格原始值解析为 float:
- 千分位逗号 / 空白剔除 (如 "1,000,000.50")
- 括号负数 (如 "(1,291,800.12)" -> -1291800.12)
- 占位符 ("-"、"—" 等) -> 0.0
- 科学计数法 (如 "1.5e6")
- 普通 float / int
- 行尾金额单位后缀 (如 "1,000万元"、"200（千元）"):
  parse_amount 返回去掉单位后的原始数值;
  parse_cell_amount 将原始数值按后缀单位换算为元 (后缀优先于列级单位)。

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

# 金额单位 -> 换算为元的乘数 (长单位优先匹配, 避免"万元"被拆成"元")
_AMOUNT_UNITS: dict[str, float] = {
    "百万元": 1_000_000.0,
    "亿元": 100_000_000.0,
    "万元": 10_000.0,
    "千元": 1_000.0,
    "元": 1.0,
}
_UNIT_TOKENS = tuple(_AMOUNT_UNITS)
_UNIT_RE = re.compile(r"(百万元|亿元|万元|千元|元)")
# 行尾单位后缀: "1,000万元" / "1,000（万元）" / "1,000 万元"
_SUFFIX_UNIT_RE = re.compile(r"[（(]?(百万元|亿元|万元|千元|元)[)）]?\s*$")


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


def _split_unit_suffix(text: str) -> tuple[str, str | None]:
    """从字符串末尾剥离金额单位后缀。

    Returns:
        (剩余文本, 单位); 无单位后缀时返回 (原文本, None)。
        剩余文本为空时视为无后缀 (裸 "万元" 不是金额)。
    """
    match = _SUFFIX_UNIT_RE.search(text)
    if match is None:
        return text, None
    remainder = text[: match.start()].strip()
    if not remainder:
        return text, None
    return remainder, match.group(1)


def _parse_core(text: str) -> float | None:
    """解析不含单位后缀的数字文本 (含括号负数/千分位/占位符)。"""
    negative = False
    paren_match = _PAREN_RE.match(text)
    if paren_match is not None:
        negative = True
        text = paren_match.group(1).strip()
    elif (text.startswith("(") or text.startswith("（")) and not (text.endswith(")") or text.endswith("）")):
        # 后缀剥离后残余的半个括号: "（1,000万元）" 去掉"万元）"后为"（1,000"
        negative = True
        text = text[1:].strip()

    cleaned = _STRIP_RE.sub("", text)
    if not cleaned:
        return None
    try:
        number = float(cleaned)
    except ValueError:
        return None
    if negative:
        number = -number
    if math.isnan(number) or math.isinf(number):
        # NaN/无穷大不是有效金额: 返回 None 由调用方跳过 (P1 宁可漏报)
        return None
    return number


def detect_amount_suffix_unit(value: object) -> str | None:
    """识别单元格值末尾的金额单位后缀 (如 "1,000万元" -> "万元")。

    仅当剩余部分可解析为数字时返回单位，避免把 "应付3元店" 之类误判。
    """
    if value is None or isinstance(value, bool):
        return None
    text = str(value).strip()
    if not text:
        return None
    remainder, unit = _split_unit_suffix(text)
    if unit is None or _parse_core(remainder) is None:
        return None
    return unit


def parse_cell_amount(value: object, unit: str | None = None) -> float | None:
    """解析单元格金额并换算为元 (单元格后缀单位优先于列级单位)。

    例如:
    - parse_cell_amount("1,000万元", "元") -> 10_000_000.0
    - parse_cell_amount("1,000", "万元") -> 10_000_000.0
    - 单元格 "1,000万元" 与列级 "万元" 同单位时不重复换算。

    无法解析返回 None, 与 parse_amount 的 P1 约定一致。
    """
    number = parse_amount(value)
    if number is None:
        return None
    suffix_unit = detect_amount_suffix_unit(value)
    return to_yuan(number, suffix_unit or unit)


def parse_amount(value: object) -> float | None:
    """将单元格值解析为金额 (数值部分，不含单位换算)。

    Args:
        value: 单元格原始值 (None / bool / int / float / str)

    Returns:
        金额 float; 空单元格 (None 或纯空白) 与无法解析的值返回 None;
        占位符 ("-" / "—") 返回 0.0。
        行尾金额单位后缀 ("1,000万元") 被剥离，返回原始数值 1000.0;
        需要换算为元请使用 parse_cell_amount。
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return None if (math.isnan(number) or math.isinf(number)) else number

    text = str(value).strip()
    if not text:
        return None
    # P3: 去除行尾金额单位后缀 (元/千元/万元/百万元/亿元)
    text, _suffix_unit = _split_unit_suffix(text)
    if text in _PLACEHOLDERS:
        return 0.0
    return _parse_core(text)
