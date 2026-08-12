"""智能规则化回退应答: 无 LLM 时也能真正回答用户问题。

策略:
1. 问题含规则编号 (如 BS-BAL-001) → 返回规则定义
2. 问题含财务/操作关键词 → 检索知识库
3. 都不匹配 → 返回通用帮助 (附当前可用功能)
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from fsa.agent.knowledge import search_knowledge

if TYPE_CHECKING:
    from fsa.gui.app_state import AppState

# 规则编号模式: BS-BAL-001 / LR-GM-001 / SCE-IS-002 等
_RULE_ID_RE = re.compile(r"\b([A-Z]{2,5}(?:-[A-Z]{2,5})+-\d{3})\b", re.IGNORECASE)

# 关键词 -> 意图 (用于知识库检索词构造)
_KEYWORD_INTENTS: list[tuple[tuple[str, ...], str]] = [
    (("勾稽", "勾稽关系", "什么是勾稽"), "勾稽关系"),
    (("容差", "差额超过", "超容差", "精度"), "容差 精确 相对 阈值"),
    (("跳过", "缺少数据", "没校验", "未执行"), "跳过 缺少数据"),
    (("导入", "支持格式", "什么格式", "怎么导入"), "导入 支持格式 Excel PDF"),
    (("导出", "底稿", "审计底稿", "怎么导出"), "导出 审计底稿"),
    (("新增规则", "自定义规则", "怎么加规则", "创建规则"), "新增规则 自定义规则"),
    (("未识别", "映射", "科目没", "识别不"), "未识别 科目 映射"),
    (("货币资金", "现金及现金等价物", "现金不等"), "货币资金 现金及现金等价物"),
    (("减值", "信用减值", "资产减值"), "减值损失 信用减值 资产减值 符号"),
    (("资产负债表", "平衡", "恒等式"), "资产负债表 平衡"),
    (("利润表", "净利润", "营业利润"), "利润表 净利润 营业利润"),
    (("现金流量表", "直接法", "间接法", "现金流"), "现金流量表 直接法 间接法"),
]


def fallback_answer(question: str, state: AppState) -> str:
    """无 LLM 时的智能规则化应答。

    Args:
        question: 用户问题
        state: 应用状态 (只读)

    Returns:
        中文回答文本
    """
    question = question.strip()
    if not question:
        return "请输入您的问题。"

    # 1. 识别规则编号
    rule_answer = _try_rule_lookup(question, state)
    if rule_answer is not None:
        return rule_answer

    # 2. 关键词 -> 知识库检索
    knowledge_answer = _try_knowledge(question)
    if knowledge_answer is not None:
        return knowledge_answer

    # 3. 通用帮助
    return _generic_help()


def _try_rule_lookup(question: str, state: AppState) -> str | None:
    """识别问题中的规则编号并返回规则定义。"""
    match = _RULE_ID_RE.search(question)
    if not match:
        return None
    rule_id = match.group(1).upper()

    registry = state.registry
    if registry is None:
        return None
    rule = registry.get_by_id(rule_id)
    if rule is None:
        return f"规则库中不存在规则 {rule_id}，请检查编号是否正确。"

    from fsa.gui.formula_display import formula_to_chinese
    lines = [
        f"规则 {rule.rule_id}: {rule.name}",
        "",
        f"校验公式: {formula_to_chinese(rule.formula)}",
        f"分类: {rule.category}  ·  涉及报表: {', '.join(rule.statements)}",
        f"容差: {rule.tolerance}  ·  严重级别: {rule.severity.value}",
    ]
    if rule.notes:
        lines.append(f"说明: {rule.notes}")
    if rule.cas_ref:
        lines.append(f"准则依据: {rule.cas_ref}")
    return "\n".join(lines)


def _try_knowledge(question: str) -> str | None:
    """按关键词检索知识库。"""
    for keywords, search_query in _KEYWORD_INTENTS:
        if any(kw in question for kw in keywords):
            return search_knowledge(search_query)
    return None


def _generic_help() -> str:
    """通用帮助 (仅在无法匹配任何问题意图时返回)。"""
    return (
        "我是 AI 诊断助手。您可以这样使用我：\n\n"
        "1. 点击校验结果中的「AI 诊断」或「深度辩论」按钮，针对具体规则深入分析\n"
        "2. 直接提问，例如：\n"
        "   · 「BS-BAL-001 规则是什么」— 查询规则定义\n"
        "   · 「什么是勾稽关系」— 财务知识解答\n"
        "   · 「差额超过容差怎么办」— 排查建议\n"
        "   · 「为什么有规则显示跳过」— 跳过原因说明\n\n"
        "（在 系统设置 → AI 助手 中配置大模型后，可进行多轮对话式深入分析）"
    )
