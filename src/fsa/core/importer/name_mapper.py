"""科目名称映射: 中文报表项目名 -> snake_case 公式变量名。

支持:
1. 标准 CAS 科目名精确匹配
2. 企业常用别名匹配
3. 前缀清洗 (一、, 减：, 加： 等)

映射字典不可变（MappingProxyType），防止运行时意外修改。
"""

from __future__ import annotations

import re
from types import MappingProxyType

# 前缀正则: 匹配 一、二、...十、 减：加： 等；
# 同时匹配（一）/(1) 等数字序号前缀 (与 sce_extractor 对齐)
_PREFIX_RE = re.compile(
    r"^[一二三四五六七八九十]+、"
    r"|^减[：:]|^加[：:]|^其中[：:]"
    r"|^[（(][一二三四五六七八九十\d]+[)）]"
    r"|^\s+"
)

# 后缀正则: 去除行尾的括号注释，如 "净利润（净亏损以“-”号填列）" -> "净利润"
_SUFFIX_RE = re.compile(r"[（(][^）)]*[）)]\s*$")

# 行尾冒号
_TRAILING_COLON_RE = re.compile(r"[：:]+\s*$")

# 标准 CAS 科目名 -> 英文 snake_case key
_STANDARD_NAMES: dict[str, str] = {
    # === 资产负债表 - 流动资产 ===
    "货币资金": "monetary_funds",
    "交易性金融资产": "trading_financial_assets",
    "应收票据": "notes_receivable",
    "应收账款": "accounts_receivable",
    "预付款项": "prepayments",
    "其他应收款": "other_receivable",
    "存货": "inventory",
    "合同资产": "contract_assets",
    "持有待售资产": "held_for_sale_assets",
    "应收款项融资": "receivables_financing",
    "其他流动资产": "other_current_assets",
    "一年内到期的非流动资产": "current_portion_non_current_assets",
    "流动资产合计": "current_assets",
    # === 资产负债表 - 非流动资产 ===
    "固定资产": "fixed_assets",
    "在建工程": "construction_in_progress",
    "使用权资产": "right_of_use_assets",
    "无形资产": "intangible_assets",
    "商誉": "goodwill",
    "长期待摊费用": "long_term_prepaid_expenses",
    "投资性房地产": "investment_property",
    "开发支出": "development_expenditure",
    "长期应收款": "long_term_receivables",
    "其他非流动资产": "other_non_current_assets",
    "递延所得税资产": "deferred_tax_assets",
    "非流动资产合计": "non_current_assets",
    "资产总计": "asset_total",
    # === 资产负债表 - 流动负债 ===
    "短期借款": "short_term_borrowings",
    "应付票据": "notes_payable",
    "应付账款": "accounts_payable",
    "预收款项": "advance_from_customers",
    "合同负债": "contract_liabilities",
    "应付职工薪酬": "employee_benefits_payable",
    "应交税费": "taxes_payable",
    "其他应付款": "other_payable",
    "一年内到期的非流动负债": "current_portion_non_current_liab",
    "其他流动负债": "other_current_liabilities",
    "流动负债合计": "current_liabilities",
    # === 资产负债表 - 非流动负债 ===
    "长期借款": "long_term_borrowings",
    "应付债券": "bonds_payable",
    "租赁负债": "lease_liabilities",
    "递延所得税负债": "deferred_tax_liabilities",
    "预计负债": "provisions",
    "递延收益": "deferred_income",
    "应付股利": "dividends_payable",
    "长期应付款": "long_term_payables",
    "其他非流动负债": "other_non_current_liabilities",
    "非流动负债合计": "non_current_liabilities",
    "负债合计": "liability_total",
    # === 资产负债表 - 所有者权益 ===
    "实收资本": "paid_in_capital",
    "资本公积": "capital_reserve",
    "库存股": "treasury_stock",
    "其他综合收益": "other_comprehensive_income",
    "盈余公积": "surplus_reserve",
    "未分配利润": "undistributed_profit",
    "所有者权益合计": "equity_total",
    "负债和所有者权益总计": "liability_equity_total",
    "少数股东权益": "minority_interest",
    "归属于母公司所有者权益": "parent_equity",
    "一般风险准备": "general_risk_reserve",
    "专项储备": "special_reserve",
    "其他权益工具": "other_equity_instruments",
    # === 利润表 ===
    "营业收入": "revenue",
    "营业成本": "operating_cost",
    "营业总收入": "total_revenue",
    "营业总成本": "total_operating_cost",
    "利息收入": "interest_income",
    "利息支出": "interest_expense",
    "手续费及佣金收入": "fee_commission_income",
    "手续费及佣金支出": "fee_commission_expense",
    "已赚保费": "earned_premium",
    "退保金": "surrender_value",
    "赔付支出": "claim_payment",
    "提取保险责任准备金净额": "insurance_reserve_change",
    "保单红利支出": "policy_dividend_expense",
    "分保费用": "reinsurance_cost",
    "税金及附加": "taxes_surcharges",
    "销售费用": "selling_exp",
    "管理费用": "admin_exp",
    "研发费用": "rnd_exp",
    "财务费用": "finance_exp",
    "其他收益": "other_income",
    "投资收益": "investment_income",
    "公允价值变动收益": "fair_value_change",
    "信用减值损失": "credit_impairment",
    "资产减值损失": "asset_impairment",
    "资产处置收益": "asset_disposal_gain",
    "营业利润": "operating_profit",
    "营业外收入": "non_operating_income",
    "营业外支出": "non_operating_expense",
    "利润总额": "total_profit",
    "所得税费用": "income_tax_expense",
    "净利润": "net_profit",
    "主营业务收入": "primary_revenue",
    "其他业务收入": "other_revenue",
    "综合收益总额": "total_comprehensive_income",
    "税后其他综合收益": "other_comprehensive_income_after_tax",
    "扣除非经常性损益的净利润": "non_recurring_net_profit",
    # === 利润表 - 补充 ===
    "持续经营净利润": "net_profit_continuing",
    "终止经营净利润": "net_profit_discontinued",
    "归属于母公司股东的净利润": "net_profit_parent",
    "少数股东损益": "minority_profit",
    # === 现金流量表 ===
    "销售商品、提供劳务收到的现金": "cash_received_from_sales",
    "收到的税费返还": "tax_refunds_received",
    "收到其他与经营活动有关的现金": "other_operating_cash_inflow",
    "经营活动现金流入小计": "operating_cash_inflow",
    "购买商品、接受劳务支付的现金": "cash_paid_for_purchases",
    "支付给职工以及为职工支付的现金": "cash_paid_for_employees",
    "支付的各项税费": "taxes_paid",
    "支付其他与经营活动有关的现金": "other_operating_cash_outflow",
    "经营活动现金流出小计": "operating_cash_outflow",
    "经营活动产生的现金流量净额": "operating_net",
    "收回投资收到的现金": "cash_from_investment_recovery",
    "取得投资收益收到的现金": "cash_from_investment_income",
    "处置固定资产收回的现金净额": "cash_from_asset_disposal",
    "处置固定资产、无形资产和其他长期资产收回的现金净额": "cash_from_asset_disposal",
    "投资活动现金流入小计": "investing_cash_inflow",
    "购建固定资产支付的现金": "cash_paid_for_fixed_assets",
    "购建固定资产、无形资产和其他长期资产支付的现金": "cash_paid_for_fixed_assets",
    "投资支付的现金": "cash_paid_for_investments",
    "投资活动现金流出小计": "investing_cash_outflow",
    "投资活动产生的现金流量净额": "investing_net",
    "取得借款收到的现金": "cash_from_borrowings",
    "筹资活动现金流入小计": "financing_cash_inflow",
    "偿还债务支付的现金": "cash_for_debt_repayment",
    "分配股利支付现金": "cash_for_dividends",
    "筹资活动现金流出小计": "financing_cash_outflow",
    "筹资活动产生的现金流量净额": "financing_net",
    # === 现金流量表 - 补充 ===
    "吸收投资收到的现金": "cash_from_investments_received",
    "收到其他与筹资活动有关的现金": "other_financing_cash_inflow",
    "支付其他与筹资活动有关的现金": "other_financing_cash_outflow",
    "现金及现金等价物净增加额": "net_increase_cash",
    "汇率变动对现金的影响": "fx_effect",
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

# 企业常用别名 -> 英文 key（与标准名映射到同一 key）
_ALIASES: dict[str, str] = {
    "现金及银行存款": "monetary_funds",
    "应收账款净额": "accounts_receivable",
    "预付账款": "prepayments",
    "预收账款": "advance_from_customers",
    "固定资产净值": "fixed_assets",
    "股本": "paid_in_capital",
    "实收资本（或股本）": "paid_in_capital",
    "其他综合收益的税后净额": "other_comprehensive_income_after_tax",
    "负债和所有者权益总计（或股东权益总计）": "liability_equity_total",
    "所有者权益合计（或股东权益合计）": "equity_total",
    "归属于母公司所有者权益合计": "parent_equity",
    "归属于母公司股东权益合计": "parent_equity",
    "分配股利、利润或偿付利息支付的现金": "cash_for_dividends",
    "汇率变动对现金及现金等价物的影响": "fx_effect",
    "归属于母公司所有者的净利润": "net_profit_parent",
}

# 合并: 标准名 + 别名 -> key
_NAME_TO_KEY: dict[str, str] = {**_STANDARD_NAMES, **_ALIASES}

# 英文 key -> 中文名称反向映射（标准名优先）
_KEY_TO_NAME: dict[str, str] = {v: k for k, v in _STANDARD_NAMES.items()}

# 不可变映射（只读）
NAME_TO_KEY: MappingProxyType[str, str] = MappingProxyType(_NAME_TO_KEY)
KEY_TO_NAME: MappingProxyType[str, str] = MappingProxyType(_KEY_TO_NAME)

# 补充资料科目名 -> cf_notes_ 前缀的 key
# 现金流量表补充资料区域的科目映射
_SUPPLEMENTARY_NAMES: dict[str, str] = {
    "净利润": "cf_notes_net_profit",
    "固定资产折旧": "cf_notes_depreciation",
    "固定资产折旧、油气资产折耗、生产性生物资产折旧": "cf_notes_depreciation",
    "无形资产摊销": "cf_notes_amortization",
    "长期待摊费用摊销": "cf_notes_long_term_amortization",
    "资产减值准备": "cf_notes_impairment",
    "信用减值损失": "cf_notes_credit_impairment",
    "处置固定资产、无形资产和其他长期资产的损失": "cf_notes_disposal_loss",
    "固定资产报废损失": "cf_notes_scrap_loss",
    "公允价值变动损失": "cf_notes_fair_value_loss",
    "财务费用": "cf_notes_finance_expense",
    "投资损失": "cf_notes_investment_loss",
    "递延所得税资产减少": "cf_notes_deferred_tax_asset_decrease",
    "递延所得税负债增加": "cf_notes_deferred_tax_liab_increase",
    "存货的减少": "cf_notes_inventory_decrease",
    "经营性应收项目的减少": "cf_notes_operating_receivable_decrease",
    "经营性应付项目的增加": "cf_notes_operating_payable_increase",
    "经营活动产生的现金流量净额": "cf_notes_operating_net",
    "现金及现金等价物净增加额": "cf_notes_net_increase_cash",
    "现金的期末余额": "cf_notes_ending_cash",
    "现金的期初余额": "cf_notes_beginning_cash",
}


def clean_name(name: str) -> str:
    """规范化科目名称，容忍报表中常见的多余字符。

    处理顺序:
    1. 去除首尾空格
    2. 去除行尾括号注释（如"（净亏损以“-”号填列）"、"（元/股）"）
    3. 去除行尾冒号
    4. 去除前缀（一、/减：/加：/其中：等）
    5. 再次去除行尾冒号与空格

    Args:
        name: 原始科目名称

    Returns:
        清理后的科目名称
    """
    result = name.strip()
    if not result:
        return ""
    result = _SUFFIX_RE.sub("", result)
    result = _TRAILING_COLON_RE.sub("", result)
    result = result.strip()
    result = _PREFIX_RE.sub("", result).strip()
    result = _TRAILING_COLON_RE.sub("", result).strip()
    return result


def get_key(name: str | None, default: str | None = None) -> str | None:
    """根据中文科目名获取对应的英文 key。

    自动清洗前缀（一、, 减：, 加：等）、行尾括号注释和首尾空格，
    依次查找标准名和别名。

    Args:
        name: 中文科目名
        default: 未找到时返回的默认值

    Returns:
        对应的 key，未找到则返回 default
    """
    if name is None:
        return default
    cleaned = clean_name(name)
    return _NAME_TO_KEY.get(cleaned, default)


def get_name(key: str, default: str | None = None) -> str | None:
    """根据英文 key 获取对应的标准中文名称。

    Args:
        key: 英文变量名
        default: 未找到时返回的默认值

    Returns:
        对应的中文名称，未找到则返回 default
    """
    return _KEY_TO_NAME.get(key, default)


def is_known(name: str) -> bool:
    """检查中文科目名是否在映射表中（含别名和前缀清洗）。

    Args:
        name: 中文科目名

    Returns:
        是否在映射表中
    """
    if not name:
        return False
    return clean_name(name) in _NAME_TO_KEY


def get_supplementary_key(name: str | None) -> str | None:
    """根据补充资料中文科目名获取对应的 cf_notes_ 前缀 key。

    仅用于现金流量表补充资料区域的科目映射。
    名称精确匹配，不做前缀清洗。

    Args:
        name: 补充资料中文科目名

    Returns:
        对应的 cf_notes_ 前缀 key，未找到返回 None
    """
    if name is None:
        return None
    cleaned = clean_name(name)
    if not cleaned:
        return None
    return _SUPPLEMENTARY_NAMES.get(cleaned)
