"""Agent 工具集: LLM 可调用的本地工具定义与执行。

每个工具 = JSON schema 定义 (供 LLM tool calling) + 本地执行函数 (读 AppState)。
工具只读, 不修改任何校验数据 (AGENTS.md 模块边界)。
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from fsa.core.models.report import Report, ReportItem
from fsa.core.models.result import ValidationResult

if TYPE_CHECKING:
    from fsa.gui.app_state import AppState

# ── 工具 JSON schema 定义 (OpenAI/Ollama tool calling 格式) ──

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_validation_results",
            "description": "获取最近一次校验的汇总结果: 通过/不通过/异常/跳过数量及各规则状态",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_rule_trace",
            "description": "获取指定规则的差异科目追溯: 每个科目的名称/金额/左右侧/原始行列定位。用于解释'差额怎么算出来的、数据取自哪里'",
            "parameters": {
                "type": "object",
                "properties": {
                    "rule_id": {"type": "string", "description": "规则编号, 如 BS-BAL-001"}
                },
                "required": ["rule_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_rule_definition",
            "description": "获取指定规则的定义: 公式/CAS准则引用/容差/说明",
            "parameters": {
                "type": "object",
                "properties": {
                    "rule_id": {"type": "string", "description": "规则编号"}
                },
                "required": ["rule_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_report_item",
            "description": "按中文科目名查询其金额和来源 (哪张表/哪行/哪列)",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "中文科目名, 如 资产总计"}
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_knowledge",
            "description": "检索财务知识库: CAS准则要点/勾稽规则说明/软件使用方法",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "检索关键词"}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_with_history",
            "description": "对比最近一次校验与历史记录, 找出状态发生变化的规则",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_imported_reports",
            "description": "获取已导入报表的概览: 报表类型/科目数量/来源文件",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_unmapped_items",
            "description": "获取导入后未能识别为标准科目的项目列表 (这些科目不参与校验)",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_skipped_rules",
            "description": "获取被跳过的规则及其跳过原因 (缺少哪些数据)",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]


# ── 工具执行 ──


def execute_tool(name: str, arguments: dict[str, Any], state: AppState) -> str:
    """执行一个工具调用, 返回中文文本结果 (供 LLM 阅读)。

    Args:
        name: 工具名
        arguments: 工具参数
        state: 应用状态 (只读访问)

    Returns:
        工具执行结果的中文文本
    """
    handler = _HANDLERS.get(name)
    if handler is None:
        return f"未知工具: {name}"
    return handler(arguments, state)


def _fmt_money(v: float) -> str:
    return f"{v:,.2f}"


def _get_validation_results(args: dict[str, Any], state: AppState) -> str:
    s = state.results
    if s is None:
        return "当前没有校验结果。请先导入报表并执行校验。"
    lines = [
        f"本次校验共执行 {s.total} 条规则:",
        f"  通过 {s.passed} / 不通过 {s.failed} / 异常 {s.errored} / 跳过 {s.skipped}",
    ]
    failed = [r for r in s.results if not r.passed and not r.errored]
    if failed:
        lines.append("不通过的规则:")
        for r in failed:
            lines.append(
                f"  {r.rule_id} {r.rule_name}: 差额 {_fmt_money(r.diff)} 元"
            )
    else:
        lines.append("没有不通过的规则。")
    return "\n".join(lines)


def _find_result(state: AppState, rule_id: str) -> ValidationResult | None:
    s = state.results
    if s is None:
        return None
    for r in s.results:
        if r.rule_id == rule_id:
            return r
    return None


def _get_rule_trace(args: dict[str, Any], state: AppState) -> str:
    rule_id = args.get("rule_id", "")
    r = _find_result(state, rule_id)
    if r is None:
        return f"未找到规则 {rule_id} 的校验结果 (可能未执行或未导入相关报表)。"
    lines = [
        f"规则 {r.rule_id} {r.rule_name}",
        f"公式: {r.formula}",
        f"左侧值: {_fmt_money(r.left_value)} 元, 右侧值: {_fmt_money(r.right_value)} 元",
        f"差额: {_fmt_money(r.diff)} 元 (容差 {r.tolerance})",
        "涉及科目数据来源:",
    ]
    if not r.trace:
        lines.append("  (无科目追溯数据)")
    for t in r.trace:
        side = "左侧" if t.side == "left" else "右侧"
        loc = f"第{t.row}行 {t.column}列" if t.row > 0 else "位置未知"
        lines.append(f"  [{side}] {t.name}: {_fmt_money(t.amount)} 元 ({loc})")
    return "\n".join(lines)


def _get_rule_definition(args: dict[str, Any], state: AppState) -> str:
    rule_id = args.get("rule_id", "")
    registry = state.registry
    if registry is None:
        return "规则库未加载。"
    rule = registry.get_by_id(rule_id)
    if rule is None:
        return f"规则库中不存在规则 {rule_id}。"
    lines = [
        f"规则 {rule.rule_id}: {rule.name}",
        f"分类: {rule.category}, 涉及报表: {', '.join(rule.statements)}",
        f"公式: {rule.formula}",
        f"容差: {rule.tolerance} ({rule.tolerance_type.value})",
    ]
    if rule.cas_ref:
        lines.append(f"CAS 准则引用: {rule.cas_ref}")
    if rule.notes:
        lines.append(f"说明: {rule.notes}")
    return "\n".join(lines)


def _get_report_item(args: dict[str, Any], state: AppState) -> str:
    name = args.get("name", "")
    reports = state.reports
    if not reports:
        return "当前没有导入任何报表。"

    def _fmt(report: Report, item: ReportItem) -> str:
        loc = f"第{item.row}行 {item.column}列" if item.row > 0 else ""
        return (
            f"{item.name}: {_fmt_money(item.amount)} 元 "
            f"(来自 {report.report_type.value} {loc})"
        )

    # 精确匹配优先 (科目名或 key 完全相等), 避免"资产"命中"资产总计"类歧义
    for report in reports:
        for item in report.items:
            if name == item.name or name == item.key:
                return _fmt(report, item)
    # 子串兜底: 返回首个命中, 并提示其他相似科目
    first_hit: str | None = None
    similar: list[str] = []
    for report in reports:
        for item in report.items:
            if name in item.name or name in item.key:
                if first_hit is None:
                    first_hit = _fmt(report, item)
                similar.append(item.name)
    if first_hit is None:
        return f"未找到科目「{name}」(可能未导入或未被识别为标准科目)。"
    if len(similar) > 1:
        first_hit += f"\n另匹配到 {len(similar) - 1} 个相似科目: " + "、".join(similar[1:4])
    return first_hit


def _search_knowledge(args: dict[str, Any], state: AppState) -> str:
    from fsa.agent.knowledge import search_knowledge
    query = args.get("query", "")
    return search_knowledge(query)


def _compare_with_history(args: dict[str, Any], state: AppState) -> str:
    repo = state.history_repo
    current = state.results
    if current is None:
        return "当前没有校验结果可对比。"
    if repo is None:
        return "历史记录存储不可用。"
    records = repo.get_recent(limit=2)
    # 排除刚保存的本次 (第一条即当前)
    if len(records) < 2:
        return "暂无历史校验记录可对比 (这是首次校验)。"
    prev = records[1]
    return (
        f"与上次校验 ({prev['created_at']}) 对比:\n"
        f"  上次: 通过 {prev['passed']} / 不通过 {prev['failed']} / 异常 {prev['errored']}\n"
        f"  本次: 通过 {current.passed} / 不通过 {current.failed} / 异常 {current.errored}"
    )


def _get_imported_reports(args: dict[str, Any], state: AppState) -> str:
    reports = state.reports
    if not reports:
        return "当前没有导入任何报表。"
    lines = [f"已导入 {len(reports)} 张报表:"]
    for r in reports:
        src = r.source_file or "未知来源"
        # 路径泄露防护 (P1): 只保留文件名, 不暴露本地完整路径
        src = os.path.basename(src)
        lines.append(f"  {r.report_type.value}: {len(r.items)} 个科目 (来源: {src})")
    return "\n".join(lines)


def _get_unmapped_items(args: dict[str, Any], state: AppState) -> str:
    reports = state.reports
    if not reports:
        return "当前没有导入任何报表。"
    lines: list[str] = []
    total = 0
    for r in reports:
        names = list(getattr(r, "unmapped_names", []))
        total += len(names)
        if names:
            shown = "、".join(names[:20])
            suffix = f" 等 {len(names)} 个" if len(names) > 20 else ""
            lines.append(f"  {r.report_type.value}: {shown}{suffix}")
        else:
            lines.append(f"  {r.report_type.value}: 无未识别科目 (识别 {len(r.items)} 个标准科目)")
    if total == 0:
        return "所有报表科目均已识别为标准科目。\n" + "\n".join(lines)
    header = (
        f"共 {total} 个项目未能识别为标准科目 (不参与校验, "
        "通常是'其中:'明细或非标准科目, 如需参与校验请反馈管理员补充映射):"
    )
    return header + "\n" + "\n".join(lines)


def _get_skipped_rules(args: dict[str, Any], state: AppState) -> str:
    s = state.results
    if s is None:
        return "当前没有校验结果。"
    skipped = [r for r in s.results if r.skipped]
    if not skipped:
        return "没有规则被跳过, 所有适用规则均已执行。"
    lines = [f"共 {len(skipped)} 条规则被跳过 (缺少数据, 不算不通过):"]
    for r in skipped[:15]:
        reason = r.message.split("跳过 - ")[-1] if "跳过" in r.message else "缺少相关数据"
        lines.append(f"  {r.rule_id} {r.rule_name}: {reason[:60]}")
    return "\n".join(lines)


_HANDLERS = {
    "get_validation_results": _get_validation_results,
    "get_rule_trace": _get_rule_trace,
    "get_rule_definition": _get_rule_definition,
    "get_report_item": _get_report_item,
    "search_knowledge": _search_knowledge,
    "compare_with_history": _compare_with_history,
    "get_imported_reports": _get_imported_reports,
    "get_unmapped_items": _get_unmapped_items,
    "get_skipped_rules": _get_skipped_rules,
}
