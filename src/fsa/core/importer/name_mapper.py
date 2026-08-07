"""科目名称映射: 中文报表项目名 -> snake_case 公式变量名。

所有变量名与规则库公式中的变量一一对应。
映射字典不可变（使用 MappingProxyType），防止运行时意外修改。
"""

from __future__ import annotations

from types import MappingProxyType

# 中文科目名 -> 英文 snake_case key
_NAME_TO_KEY: dict[str, str] = {
    # === 资产负债表 ===
    "资产总计": "asset_total",
    "负债合计": "liability_total",
    "所有者权益合计": "equity_total",
    "流动资产合计": "current_assets",
    "非流动资产合计": "non_current_assets",
    "流动负债合计": "current_liabilities",
    "非流动负债合计": "non_current_liabilities",
    "货币资金": "monetary_funds",
    "应收账款": "accounts_receivable",
    "应付账款": "accounts_payable",
    "其他应收款": "other_receivable",
    "其他应付款": "other_payable",
    "预收款项": "advance_from_customers",
    "预付款项": "prepayments",
    "在建工程": "construction_in_progress",
    "实收资本": "paid_in_capital",
    "资本公积": "capital_reserve",
    "其他综合收益": "other_comprehensive_income",
    "盈余公积": "surplus_reserve",
    "未分配利润": "undistributed_profit",
    "库存股": "treasury_stock",
    "少数股东权益": "minority_interest",
    "归属于母公司所有者权益": "parent_equity",
    # === 利润表 ===
    "营业收入": "revenue",
    "营业成本": "operating_cost",
    "营业利润": "operating_profit",
    "利润总额": "total_profit",
    "净利润": "net_profit",
    "税金及附加": "taxes_surcharges",
    "销售费用": "selling_exp",
    "管理费用": "admin_exp",
    "研发费用": "rnd_exp",
    "财务费用": "finance_exp",
    "资产减值损失": "asset_impairment",
    "信用减值损失": "credit_impairment",
    "其他收益": "other_income",
    "投资收益": "investment_income",
    "公允价值变动收益": "fair_value_change",
    "资产处置收益": "asset_disposal_gain",
    "营业外收入": "non_operating_income",
    "营业外支出": "non_operating_expense",
    "所得税费用": "income_tax_expense",
    "主营业务收入": "primary_revenue",
    "其他业务收入": "other_revenue",
    "综合收益总额": "total_comprehensive_income",
    "税后其他综合收益": "other_comprehensive_income_after_tax",
    "扣除非经常性损益的净利润": "non_recurring_net_profit",
    # === 现金流量表 ===
    "经营活动产生的现金流量净额": "operating_net",
    "投资活动产生的现金流量净额": "investing_net",
    "筹资活动产生的现金流量净额": "financing_net",
    "现金及现金等价物净增加额": "net_increase_cash",
    "汇率变动对现金的影响": "fx_effect",
    "销售商品、提供劳务收到的现金": "cash_received_from_sales",
    "期初现金及现金等价物余额": "beginning_cash_equiv",
    "期末现金及现金等价物余额": "ending_cash_equiv",
    # === 折旧摊销 ===
    "折旧": "depreciation",
    "摊销": "amortization",
    "减值准备": "impairment",
    # === 所得税 ===
    "当期所得税": "current_income_tax",
    "递延所得税": "deferred_tax",
    "递延所得税负债变动": "deferred_tax_liab_change",
    "递延所得税资产变动": "deferred_tax_asset_change",
    "存货变动": "inventory_change",
    "经营性应收项目变动": "operating_receivable_change",
    "经营性应付项目变动": "operating_payable_change",
    "财务费用调整": "finance_expense_adjust",
}

# 英文 key -> 中文名称反向映射
_KEY_TO_NAME: dict[str, str] = {v: k for k, v in _NAME_TO_KEY.items()}

# 不可变映射（只读）
NAME_TO_KEY: MappingProxyType[str, str] = MappingProxyType(_NAME_TO_KEY)
KEY_TO_NAME: MappingProxyType[str, str] = MappingProxyType(_KEY_TO_NAME)


def get_key(name: str | None, default: str | None = None) -> str | None:
    """根据中文科目名获取对应的英文 key。

    Args:
        name: 中文科目名
        default: 未找到时返回的默认值

    Returns:
        对应的 key，未找到则返回 default
    """
    if name is None:
        return default
    return _NAME_TO_KEY.get(name.strip(), default)


def get_name(key: str, default: str | None = None) -> str | None:
    """根据英文 key 获取对应的中文名称。

    Args:
        key: 英文变量名
        default: 未找到时返回的默认值

    Returns:
        对应的中文名称，未找到则返回 default
    """
    return _KEY_TO_NAME.get(key, default)


def is_known(name: str) -> bool:
    """检查中文科目名是否在映射表中。

    Args:
        name: 中文科目名

    Returns:
        是否在映射表中
    """
    return name.strip() in _NAME_TO_KEY if name else False
