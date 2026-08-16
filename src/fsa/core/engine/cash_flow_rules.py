"""现金流分类规则库: 现金流量项目与对方科目的常见对应关系。

规则用于"宁可漏报不可误报"的复核提示：凭证的现金流量项目与序时账
对方科目明显不属于同一业务场景时，输出警告供人工确认，而非直接判错。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CashFlowClassificationRule:
    """一条现金流分类规则。

    Attributes:
        rule_id: 规则编号
        project_keyword: 现金流量项目关键字（用于匹配明细项目名）
        direction: 方向，"流入" 或 "流出"
        counterpart_prefixes: 非现金对方科目的编码前缀（常见范围）
        description: 中文说明
    """

    rule_id: str
    project_keyword: str
    direction: str
    counterpart_prefixes: tuple[str, ...]
    description: str = ""


DEFAULT_CASH_FLOW_RULES: tuple[CashFlowClassificationRule, ...] = (
    CashFlowClassificationRule(
        rule_id="CF-CLS-001",
        project_keyword="销售商品、提供劳务收到的现金",
        direction="流入",
        counterpart_prefixes=("1121", "1122", "1123", "2203", "2205", "6001", "6051"),
        description="销售收款应对应应收票据/应收账款/预收款项/合同负债/收入类科目",
    ),
    CashFlowClassificationRule(
        rule_id="CF-CLS-002",
        project_keyword="购买商品、接受劳务支付的现金",
        direction="流出",
        counterpart_prefixes=("1401", "1402", "1403", "1404", "1405", "1406", "2202", "2221"),
        description="采购付款应对应存货/材料/应付账款/应交税费类科目",
    ),
    CashFlowClassificationRule(
        rule_id="CF-CLS-003",
        project_keyword="支付给职工以及为职工支付的现金",
        direction="流出",
        counterpart_prefixes=("2211", "2221"),
        description="职工薪酬付款应对应应付职工薪酬/代扣税费",
    ),
    CashFlowClassificationRule(
        rule_id="CF-CLS-004",
        project_keyword="支付的各项税费",
        direction="流出",
        counterpart_prefixes=("2221",),
        description="税费付款应对应交税费",
    ),
    CashFlowClassificationRule(
        rule_id="CF-CLS-005",
        project_keyword="收回投资收到的现金",
        direction="流入",
        counterpart_prefixes=("1101", "1503", "1504", "1511", "1521"),
        description="收回投资应对交易性金融资产/其他债权投资/其他权益工具投资/长期股权投资/投资性房地产",
    ),
    CashFlowClassificationRule(
        rule_id="CF-CLS-006",
        project_keyword="投资支付的现金",
        direction="流出",
        counterpart_prefixes=("1101", "1503", "1504", "1511", "1521"),
        description="投资支付应对交易性金融资产/其他债权投资/其他权益工具投资/长期股权投资/投资性房地产等投资科目",
    ),
    CashFlowClassificationRule(
        rule_id="CF-CLS-007",
        project_keyword="取得投资收益收到的现金",
        direction="流入",
        counterpart_prefixes=("6111",),
        description="取得投资收益应对投资收益科目",
    ),
    CashFlowClassificationRule(
        rule_id="CF-CLS-008",
        project_keyword="购建固定资产、无形资产和其他长期资产支付的现金",
        direction="流出",
        counterpart_prefixes=("1601", "1604", "1701", "1801"),
        description="长期资产购建应对固定资产/在建工程/无形资产/长期待摊费用",
    ),
)


def find_rule(
    project_name: str, direction: str
) -> CashFlowClassificationRule | None:
    """按现金流量项目名与方向匹配规则。"""
    for rule in DEFAULT_CASH_FLOW_RULES:
        if rule.project_keyword in project_name and rule.direction == direction:
            return rule
    return None
