"""LLM 输入消毒 (P1): 清洗进入提示词的不可信数据。

报表数据 (科目名/sheet 名/文件名等)、用户消息、工具调用结果都是不可信输入,
统一经 sanitize_llm_input 清洗后再拼入提示词, 降低提示词注入与
控制字符干扰风险。纯标准库, 无外部依赖。
"""

from __future__ import annotations

# 截断后追加的标记
_TRUNCATE_SUFFIX = "…(截断)"


def sanitize_llm_input(value: str, max_len: int = 200) -> str:
    """清洗将进入 LLM 提示词的输入文本。

    处理顺序:
    1. 非 str 输入先 str() 转换
    2. 去除首尾空白 (strip)
    3. 去除控制字符 (\\x00-\\x1f, 保留 \\n 与 \\t)
    4. 连续空白折叠为单个空格
    5. 超过 max_len 时截断并追加 "…(截断)"

    Args:
        value: 待清洗的输入 (可为任意类型, 自动转 str)
        max_len: 最大保留长度, 超长截断

    Returns:
        清洗后的安全文本
    """
    text = str(value)
    text = text.strip()
    text = "".join(ch for ch in text if ch == "\n" or ch == "\t" or ord(ch) >= 0x20)
    text = " ".join(text.split())
    if len(text) > max_len:
        text = text[:max_len] + _TRUNCATE_SUFFIX
    return text
