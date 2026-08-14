"""行业阈值参数化: 逻辑合理性规则(LR-*)的阈值按行业配置。

设计说明:
- 规则库公式中的魔法数字已替换为阈值变量名(如 dar_threshold)。
- 求值前由 runner 将阈值变量注入命名空间; 未指定行业时使用 general 默认值,
  保证默认行为与替换前完全一致(回归不破, P2 确定性)。
- 行业值可在主体级配置(EntityConfig.industry)中覆写, 见 services/entity_config.py。
- 所有阈值为实务经验值(非准则强制), 可由用户按主体覆写。
"""

from __future__ import annotations

from loguru import logger

# 行业阈值规则使用的公式变量名 (规则ID -> 变量名), 用于审计追溯。
INDUSTRY_THRESHOLD_RULES: dict[str, str] = {
    "LR-DAR-001": "dar_threshold",
    "LR-GM-002": "gm_yoy_threshold",
    "LR-ART-001": "ar_to_revenue_threshold",
    "LR-FLUC-001": "yoy_fluctuation_threshold",
    "LR-SALES-001": "sales_cash_ratio_threshold",
    "LR-QUICK-001": "quick_ratio_threshold",
}

# 支持的行业枚举。未配置行业(未知值)时回落 general (P1: 保守, 不改变默认行为)。
KNOWN_INDUSTRIES: tuple[str, ...] = (
    "general",
    "financial",
    "real_estate",
    "construction",
    "retail",
    "cyclical",
    "high_growth",
)

# 各阈值变量按行业的取值。值均为实务经验值, 可由用户覆写。
INDUSTRY_THRESHOLDS: dict[str, dict[str, float]] = {
    # 资产负债率上限 (LR-DAR-001):
    #   general 85%: 一般行业警戒线; financial 92%: 金融机构天然高杠杆;
    #   real_estate 85%: 房地产高杠杆但预收/合同负债占比高, 实务常按 85% 提示;
    #   construction 80%: 建筑/工程垫资经营, 行业平均约 80%;
    #   retail 75%: 零售行业低杠杆, 收紧至 75%。
    "dar_threshold": {
        "general": 0.85,
        "financial": 0.92,
        "real_estate": 0.85,
        "construction": 0.80,
        "retail": 0.75,
    },
    # 毛利率同比波动容忍度 (LR-GM-002):
    #   general 30%; cyclical 50%: 周期行业(钢铁/化工/航运)毛利波动显著更大。
    "gm_yoy_threshold": {
        "general": 0.30,
        "cyclical": 0.50,
    },
    # 应收账款/营业收入警戒线 (LR-ART-001):
    #   general 30%; construction 60%: 建筑/工程回款周期长, 放宽至 60%。
    "ar_to_revenue_threshold": {
        "general": 0.30,
        "construction": 0.60,
    },
    # 收入同比波动警戒线 (LR-FLUC-001):
    #   general 30%; high_growth 50%: 高增长企业(新业态/成长期)波动更大。
    "yoy_fluctuation_threshold": {
        "general": 0.30,
        "high_growth": 0.50,
    },
    # 销售收现比率下限 (LR-SALES-001):
    #   general 80%; construction 50%: 建筑/工程垫资, 收现滞后, 下限放宽至 50%。
    "sales_cash_ratio_threshold": {
        "general": 0.8,
        "construction": 0.5,
    },
    # 流动比率下限 (LR-QUICK-001):
    #   general 1.0; retail 70%: 零售行业多为负现金周期, 放宽至 0.7。
    "quick_ratio_threshold": {
        "general": 1.0,
        "retail": 0.7,
    },
}

# general 行业默认阈值 = 规则库替换前的原始魔法数字。
DEFAULT_THRESHOLDS: dict[str, float] = {
    var: mapping["general"] for var, mapping in INDUSTRY_THRESHOLDS.items()
}


def threshold_vars_for(industry: str = "general") -> dict[str, float]:
    """返回某行业的所有阈值变量 -> 值映射。

    未配置行业(未知值)时回落 general 默认值 (P1: 保守, 不改变默认行为)。

    Args:
        industry: 行业枚举, 见 KNOWN_INDUSTRIES。

    Returns:
        阈值变量名 -> 值, 如 {"dar_threshold": 0.85, ...}。
    """
    if industry not in KNOWN_INDUSTRIES:
        logger.warning(f"未知行业「{industry}」, 阈值按 general 处理")
    return {
        var: mapping.get(industry, mapping["general"])
        for var, mapping in INDUSTRY_THRESHOLDS.items()
    }
