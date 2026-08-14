"""诊断引擎: 规则驱动的确定性中文诊断分析。

DiagnosisEngine 接收一条失败的 ValidationResult，输出结构化的中文诊断报告。
诊断逻辑完全基于规则，不使用 LLM、不依赖网络、不依赖时间。

diagnose_with_llm() 方法支持可选的 Ollama LLM 增强诊断，LLM 不可用时
无缝回退到规则化诊断，保证确定性。
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from urllib.error import URLError

from fsa.agent.llm_client import DISCLAIMER_TEXT, LLMError
from fsa.agent.sanitize import sanitize_llm_input
from fsa.core.models.result import TraceItem, ValidationResult

if TYPE_CHECKING:
    from fsa.agent.llm_client import LLMClient
    from fsa.agent.ollama_client import OllamaClient

# LLM 调用可能抛出的具体异常 (用于诊断降级, 避免宽 catch)
_LLM_ERRORS: tuple[type[BaseException], ...] = (
    LLMError,
    URLError,
    TimeoutError,
    OSError,
    json.JSONDecodeError,
)


def _fmt_amount(value: float) -> str:
    """格式化金额为千分位字符串。"""
    return f"{value:,.2f}"


def _build_header(result: ValidationResult) -> str:
    """构建诊断报告头部: 规则 ID、名称、状态、差额。"""
    status = "未通过" if not result.passed else "已通过（异常）"
    lines = [
        f"【{result.rule_id}】{result.rule_name}",
        f"校验状态: {status}",
        f"差额: {_fmt_amount(abs(result.diff))} 元",
        f"容差阈值: {result.tolerance}",
    ]
    return "\n".join(lines)


def _build_trace_section(trace: list[TraceItem]) -> str:
    """构建涉及科目追溯部分。"""
    if not trace:
        return "涉及科目: 暂无追溯信息（数据来源未记录）。"

    lines: list[str] = ["【涉及科目追溯】"]
    for item in trace:
        side_label = "左侧" if item.side == "left" else "右侧"
        lines.append(
            f"  - {item.name}（{item.key}）: {_fmt_amount(item.amount)} 元"
            f" — {side_label}，第 {item.row} 行 {item.column}"
        )
    return "\n".join(lines)


def _build_magnitude_analysis(result: ValidationResult) -> str:
    """根据差额大小给出量级分析。"""
    diff = abs(result.diff)
    tolerance = result.tolerance

    lines = ["【差额量级分析】"]

    if diff <= 1.0:
        lines.append("差额极小（≤ 1 元），疑似四舍五入或精度差异。")
        lines.append("建议核对各科目金额的小数位精度设置是否一致。")
    elif diff <= tolerance * 100:
        lines.append("差额较小，可能为精度差异或尾差。")
        lines.append("建议检查各科目取数时的小数位精度，确认是否存在系统性的尾差累积。")
    else:
        lines.append("差额较大，超出正常尾差范围。")
        lines.append("建议重点核查相关科目的取数是否完整、报表编制是否正确。")
        lines.append("可能的原因包括: 科目遗漏、重分类未处理、合并抵销不完整、期初余额衔接错误。")

    return "\n".join(lines)


def _build_category_advice(result: ValidationResult) -> str:
    """根据规则分类和规则 ID 给出针对性建议。"""
    lines = ["【分类诊断建议】"]
    rule_id = result.rule_id
    category = result.category

    # 按规则 ID 前缀精确匹配
    if rule_id == "BS-BAL-001":
        lines.append("这是会计基本恒等式（资产 = 负债 + 所有者权益）。")
        lines.append("该规则不通过说明报表编制存在根本性错误，可能的原因包括:")
        lines.append("  • 资产、负债、权益三大类中的某一类科目金额录入错误")
        lines.append("  • 报表中存在重复科目或遗漏科目")
        lines.append("  • 重分类调整未完整处理")
        lines.append("  • 合并抵销分录未正确计入")
    elif rule_id == "CF-BAL-001":
        lines.append("现金流量表平衡校验涉及期初期末现金等价物和汇率变动。")
        lines.append("常见遗漏: 请检查是否遗漏「汇率变动对现金及现金等价物的影响」项目。")
        lines.append("汇率变动金额通常较小，但若企业有大量外币业务则可能显著。")
    elif (
        rule_id.startswith(("BS-", "IS-"))
        or (
            rule_id.startswith("CF-")
            and not rule_id.startswith(("CF-DTL", "CF-JNL", "CF-CLS"))
        )
    ):
        if "BAL" in rule_id:
            lines.append("表内平衡规则不通过，说明相关合计项的取数不完整。")
            lines.append("建议检查: 各明细项目是否都已取数、是否有漏项、是否有重分类错误。")
        else:
            lines.append("表内勾稽规则不通过，建议检查相关科目之间的逻辑关系。")
    elif category.startswith("B-表间勾稽") or "表间" in category:
        lines.append("表间勾稽规则不通过，需要检查跨表数据衔接。")
        lines.append("常见原因: 期初期末口径不一致、附注数据与主表不匹配、科目映射关系错误。")
        lines.append("建议逐一核对: 期初余额是否衔接上期期末、附注明细合计是否与主表一致。")
    elif category.startswith("C-逻辑合理性") or "LR" in category:
        lines.append("逻辑合理性规则属于业务合理性提示，而非硬性错误。")
        lines.append("这类规则的结果需要结合企业实际业务情况判断，不一定代表数据错误。")
        lines.append("建议: 结合行业特征、企业经营状况、历史同期数据进行综合判断。")
    elif rule_id == "JNL-BAL-001":
        lines.append("序时账逐凭证借贷不平衡，属于记账层面的硬性错误。")
        lines.append("建议: 按提示中的凭证号打开凭证，核对借方与贷方分录是否完整、")
        lines.append("是否存在漏记、串户或方向录入错误。")
    elif rule_id == "CF-DTL-001":
        lines.append("现金流量明细与主表项目不一致，可能是主表与明细的口径不同。")
        lines.append("建议: 核对主表是否包含明细之外的调整项，例如不涉及现金的")
        lines.append("投资活动、受限资金、内部划转等，必要时按企业口径调整填报。")
    elif rule_id == "CF-JNL-001":
        lines.append("现金流明细与序时账现金科目不一致，通常是现金等价物口径差异。")
        lines.append("建议: 确认企业把哪些科目视为现金等价物（如理财产品 1012 是否纳入），")
        lines.append("在主体配置中调整口径后重新核对。")
    elif rule_id == "TB-BS-001":
        lines.append("余额表与资产负债表不一致，常见于坏账准备、重分类和抵销调整。")
        lines.append("建议: 用往来重分类明细（附表3）复核重分类结果，")
        lines.append("并核对减值准备对报表净额的影响。")
    elif rule_id in ("RC-001", "RC-002"):
        lines.append("往来重分类检查关注负数余额转正与科目对应关系。")
        lines.append("建议: 逐笔核对六大往来的负数余额是否已重分类到对应科目，")
        lines.append("差额部分优先排查坏账准备等报表调整。")
    elif rule_id == "RP-001":
        lines.append("关联方采购总金额与成本/费用分类合计不一致。")
        lines.append("建议: 核对采购金额在存货、主营业务成本、研发费用等分类中")
        lines.append("是否分摊完整，是否存在遗漏或重复归类。")
    elif rule_id in ("SAL-001", "SAL-002"):
        lines.append("销售收入成本明细与账务不一致。")
        lines.append("建议: 核对收入/成本金额与成本构成四要素（材料/加工/人工/制造费），")
        lines.append("并按收入类型与利润表营业收入、营业成本逐项勾稽。")
    elif rule_id == "ICF-001":
        lines.append("内部交易现金流超过主表对应项目，属于需要解释的口径问题。")
        lines.append("建议: 核对内部交易是否存在代收代付、轧差列报，")
        lines.append("或内部现金流项目与主表项目的口径映射是否准确。")
    elif rule_id.startswith("CF-CLS-"):
        lines.append("这是现金流项目选择的复核提示，不一定是数据错误。")
        lines.append("对方科目不在常见范围内，通常是因为企业有特殊业务（如理财、")
        lines.append("保证金）或凭证为复合分录。建议结合凭证摘要确认分类口径。")
    else:
        # 通用分类建议
        if "A-表内平衡" in category:
            lines.append("表内平衡规则不通过，建议检查相关合计项的取数完整性。")
        elif "B-表间" in category:
            lines.append("表间勾稽规则不通过，建议检查跨表数据衔接。")
        elif "C-逻辑" in category:
            lines.append("逻辑合理性规则属于业务合理性提示，建议结合业务实际判断。")

    return "\n".join(lines)


def _build_action_steps() -> str:
    """构建建议操作步骤（编号列表）。"""
    lines = [
        "【建议操作步骤】",
        "1. 核对原始报表中对应科目的金额，确认录入是否正确。",
        "2. 检查是否有重分类调整未处理，确认科目归属是否准确。",
        "3. 检查合并抵销分录是否完整，确认合并范围是否正确。",
        "4. 核对期初余额是否衔接上期期末余额。",
        "5. 如确认数据无误，可考虑适当调整容差范围或将该规则标记为不适用。",
    ]
    return "\n".join(lines)


def _build_llm_prompt(result: ValidationResult) -> str:
    """构建发送给 LLM 的诊断提示词（确定性：相同输入生成相同提示词）。

    提示词包含规则信息、差额、容差、公式、涉及科目追溯，
    要求模型从财务审计角度分析差异根因并给出排查建议。
    """
    lines: list[str] = [
        "请从财务审计角度分析以下勾稽校验未通过的原因，并给出排查建议。",
        "要求：中文、简洁、不超过300字。",
        "",
        f"规则编号: {sanitize_llm_input(result.rule_id)}",
        f"规则名称: {sanitize_llm_input(result.rule_name)}",
        f"校验公式: {sanitize_llm_input(result.formula)}",
        f"左侧计算值: {_fmt_amount(result.left_value)} 元",
        f"右侧计算值: {_fmt_amount(result.right_value)} 元",
        f"差额: {_fmt_amount(abs(result.diff))} 元",
        f"容差阈值: {sanitize_llm_input(str(result.tolerance))}",
    ]

    if result.trace:
        lines.append("")
        lines.append("涉及科目追溯:")
        for item in result.trace:
            lines.append(
                f"  - {sanitize_llm_input(item.name)}（{sanitize_llm_input(item.key)}）: "
                f"{_fmt_amount(item.amount)} 元"
                f"（{sanitize_llm_input(item.side)}侧，第{item.row}行 "
                f"{sanitize_llm_input(item.column)}）"
            )

    lines.append("")
    lines.append("请分析差异可能的根因，并给出具体的排查建议。")

    return "\n".join(lines)


_LLM_SYSTEM_PROMPT: str = (
    "你是一位资深审计师，精通中国企业会计准则（CAS）和财务报表勾稽关系。"
    "你的任务是分析财务报表勾稽校验未通过的原因，从财务审计角度给出专业、"
    "简洁的诊断建议。请用中文回答，不超过300字。"
)


class DiagnosisEngine:
    """规则驱动的确定性诊断引擎。

    接收失败的 ValidationResult，输出结构化的中文诊断报告。
    诊断逻辑完全确定性，无随机、无网络、无时间依赖。
    """

    def diagnose(self, result: ValidationResult) -> str:
        """对一条失败的校验结果生成中文诊断报告。

        Args:
            result: 校验结果（通常为未通过状态）

        Returns:
            结构化的中文诊断文本, 已含「（规则引擎确定性诊断 · 未使用 AI）」标注
            (P0 免责, 调用方无需再拼接)
        """
        sections = [
            _build_header(result),
            _build_trace_section(result.trace),
            _build_magnitude_analysis(result),
            _build_category_advice(result),
            _build_action_steps(),
        ]
        return "\n\n".join(sections) + "\n\n（规则引擎确定性诊断 · 未使用 AI）"

    def diagnose_with_llm(
        self,
        result: ValidationResult,
        client: OllamaClient | None = None,
    ) -> str:
        """使用可选的 LLM 增强诊断。

        若 Ollama 可用则调用 LLM 生成更深入的诊断分析；
        若不可用则回退到规则化诊断 diagnose()，保证确定性。

        Args:
            result: 校验结果（通常为未通过状态）
            client: Ollama 客户端，为 None 时回退到规则化诊断

        Returns:
            中文诊断文本（可能来自 LLM 或规则引擎）
        """
        from fsa.agent.ollama_client import OllamaError

        # 无客户端 -> 回退
        if client is None:
            return self.diagnose(result)

        # 服务不可用 -> 回退
        if not client.is_available():
            return self.diagnose(result)

        # 尝试 LLM 诊断
        prompt = _build_llm_prompt(result)
        try:
            llm_response = client.generate(
                prompt=prompt,
                system=_LLM_SYSTEM_PROMPT,
            )
        except (OllamaError, URLError, TimeoutError, OSError, json.JSONDecodeError):
            # 捕获 LLM 调用相关异常 (含 OllamaError), 保证不回传异常给调用方
            return self.diagnose(result)

        # LLM 返回空 -> 回退
        if not llm_response.strip():
            return self.diagnose(result)

        return llm_response

    def diagnose_with_client(
        self,
        result: ValidationResult,
        client: LLMClient | None = None,
    ) -> str:
        """使用 LLMClient 协议（Ollama / OpenAI 兼容）的增强诊断。

        客户端不可用、调用失败或返回空内容时，回退到规则化诊断。
        返回值已含 DISCLAIMER_TEXT 免责标注 (P0, 调用方无需再拼接)。
        """
        if client is None:
            return self.diagnose(result)
        try:
            available = client.is_available()
        except _LLM_ERRORS:
            return self.diagnose(result)
        if not available:
            return self.diagnose(result)

        from fsa.agent.llm_client import ChatMessage, response_text

        messages = [
            ChatMessage(role="system", content=_LLM_SYSTEM_PROMPT),
            ChatMessage(role="user", content=_build_llm_prompt(result)),
        ]
        try:
            response = client.chat(messages)
        except _LLM_ERRORS:
            return self.diagnose(result)
        # content 为空时用 reasoning 尾部兜底 (推理模型 max_tokens 耗尽场景)
        text = response_text(response).strip()
        if not text:
            return self.diagnose(result)
        return text + "\n\n" + DISCLAIMER_TEXT
