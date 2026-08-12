"""诊断引擎: 规则驱动的确定性中文诊断分析。

DiagnosisEngine 接收一条失败的 ValidationResult，输出结构化的中文诊断报告。
诊断逻辑完全基于规则，不使用 LLM、不依赖网络、不依赖时间。

diagnose_with_llm() 方法支持可选的 Ollama LLM 增强诊断，LLM 不可用时
无缝回退到规则化诊断，保证确定性。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fsa.core.models.result import TraceItem, ValidationResult

if TYPE_CHECKING:
    from fsa.agent.ollama_client import OllamaClient


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
    elif rule_id.startswith("BS-") or rule_id.startswith("IS-") or rule_id.startswith("CF-"):
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
        f"规则编号: {result.rule_id}",
        f"规则名称: {result.rule_name}",
        f"校验公式: {result.formula}",
        f"左侧计算值: {_fmt_amount(result.left_value)} 元",
        f"右侧计算值: {_fmt_amount(result.right_value)} 元",
        f"差额: {_fmt_amount(abs(result.diff))} 元",
        f"容差阈值: {result.tolerance}",
    ]

    if result.trace:
        lines.append("")
        lines.append("涉及科目追溯:")
        for item in result.trace:
            lines.append(
                f"  - {item.name}（{item.key}）: {_fmt_amount(item.amount)} 元"
                f"（{item.side}侧，第{item.row}行 {item.column}）"
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
            结构化的中文诊断文本
        """
        sections = [
            _build_header(result),
            _build_trace_section(result.trace),
            _build_magnitude_analysis(result),
            _build_category_advice(result),
            _build_action_steps(),
        ]
        return "\n\n".join(sections)

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
        except Exception:
            # 捕获所有异常（包括 OllamaError），保证不回传异常给调用方
            return self.diagnose(result)

        # LLM 返回空 -> 回退
        if not llm_response.strip():
            return self.diagnose(result)

        return llm_response
