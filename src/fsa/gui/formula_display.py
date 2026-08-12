"""公式中文化: 将引擎使用的英文变量公式转换为中文显示。

仅用于 UI 显示层, 不影响引擎求值 (引擎仍用英文变量)。
示例: "asset_total == liability_total + equity_total"
   -> "资产总计 == 负债合计 + 所有者权益合计"
"""

from __future__ import annotations

import re

from fsa.core.importer.name_mapper import get_name

# 变量名 token 匹配 (字母/下划线/数字)
_TOKEN_RE = re.compile(r"[a-zA-Z_][a-zA-Z0-9_]*")

# 公式函数名 -> 中文 (简单eval支持的函数)
_FUNCTION_NAMES = {
    "abs": "绝对值",
    "min": "最小值",
    "max": "最大值",
    "round": "四舍五入",
    "sum": "求和",
}

# 逻辑运算符 -> 中文
_OPERATORS = {
    "and": "且",
    "or": "或",
    "not": "非",
}


def formula_to_chinese(formula: str) -> str:
    """将英文变量公式转换为中文显示。

    Args:
        formula: 英文公式, 如 "asset_total == liability_total + equity_total"

    Returns:
        中文公式, 如 "资产总计 == 负债合计 + 所有者权益合计"
    """
    def _replace(match: re.Match) -> str:
        token = match.group(0)
        return _translate_token(token)

    return _TOKEN_RE.sub(_replace, formula)


def _translate_token(token: str) -> str:
    """翻译单个 token (变量/函数/运算符)。"""
    # 函数名
    if token in _FUNCTION_NAMES:
        return _FUNCTION_NAMES[token]
    # 逻辑运算符
    if token in _OPERATORS:
        return _OPERATORS[token]
    # cf_notes_ 前缀 (附注/补充资料变量)
    if token.startswith("cf_notes_"):
        base = token[len("cf_notes_"):]
        base_cn = get_name(base) or base
        return f"{base_cn}(补充资料)"
    # _ending / _beginning 后缀 (双金额列)
    for suffix, suffix_cn in (("_ending", "(期末)"), ("_beginning", "(期初)")):
        if token.endswith(suffix):
            base = token[: -len(suffix)]
            base_cn = get_name(base) or base
            return f"{base_cn}{suffix_cn}"
    # 普通变量
    return get_name(token) or token
