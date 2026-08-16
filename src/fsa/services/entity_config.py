"""主体级口径配置: 现金等价物范围、余额表映射、容差、行业等可按公司覆盖。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from fsa.core.engine.thresholds import threshold_vars_for
from fsa.services.detail_validation_service import (
    _DEFAULT_TB_BS_MAPPINGS,
    DetailCheckConfig,
)


@dataclass(frozen=True)
class EntityConfig:
    """单个主体的明细校验口径。

    Attributes:
        entity_id: 主体标识
        tolerance: 明细勾稽容差
        industry: 行业 (general/financial/real_estate/construction/retail/
            cyclical/high_growth), 用于逻辑合理性规则(LR-*)的阈值配置,
            默认 general (与规则库默认行为一致)。
        cash_equivalent_codes: 现金等价物科目编码
        tb_to_bs_mappings: 余额表 -> 资产负债表映射
        reclass_pairs: 重分类科目对（标准科目 -> 目标标准科目），
            None 时使用默认科目对
        balance_sheet_accounts: 重分类核对报表项目 key -> 标准科目，
            None 时使用默认映射
        margin_tolerance: 毛利率核对容差（相对比例），None 时默认 0.01
        bilateral_pairs: 内部现金流双边核对科目对（流入项目 -> 流出项目），
            None 时使用默认科目对
        bilateral_tolerance: 内部现金流双边核对容差（元），None 时默认 0.01
    """

    entity_id: str = ""
    tolerance: float = 0.01
    industry: str = "general"
    cash_equivalent_codes: tuple[str, ...] = ("1001", "1002")
    tb_to_bs_mappings: dict[str, dict[str, object]] = field(
        default_factory=lambda: dict(_DEFAULT_TB_BS_MAPPINGS)
    )
    reclass_pairs: dict[str, tuple[str, ...]] | None = None
    balance_sheet_accounts: dict[str, str] | None = None
    margin_tolerance: float | None = None
    bilateral_pairs: dict[str, str] | None = None
    bilateral_tolerance: float | None = None

    def threshold_vars(self) -> dict[str, float]:
        """按行业返回逻辑合理性规则(LR-*)的阈值变量 -> 值映射。

        未知行业回落 general (P1: 保守, 不改变默认行为)。
        """
        return threshold_vars_for(self.industry)

    def to_detail_config(self) -> DetailCheckConfig:
        """转换为明细校验配置。"""
        return DetailCheckConfig(
            tolerance=self.tolerance,
            cash_equivalent_codes=self.cash_equivalent_codes,
            tb_to_bs_mappings=self.tb_to_bs_mappings,
            reclass_pairs=self.reclass_pairs,
            balance_sheet_accounts=self.balance_sheet_accounts,
            margin_tolerance=self.margin_tolerance,
        )


def _parse_str_tuple(raw: object) -> tuple[str, ...]:
    """将 JSON 中的字符串/字符串列表解析为元组。"""
    if isinstance(raw, str):
        return (raw,)
    if isinstance(raw, list):
        return tuple(str(item) for item in raw)
    return ()


def load_entity_configs(path: str | Path) -> dict[str, EntityConfig]:
    """从 JSON 文件加载主体配置。

    格式:
    {
      "entities": {
        "杭州杰为科技有限公司": {
          "tolerance": 0.01,
          "industry": "construction",
          "cash_equivalent_codes": ["1001", "1002"],
          "tb_to_bs_mappings": {
            "monetary_funds": {"codes": ["1001","1002","1012"], "side": "debit"}
          },
          "reclass_pairs": {"应收账款": ["预付款项"]},
          "balance_sheet_accounts": {"accounts_receivable": "应收账款"},
          "margin_tolerance": 0.02,
          "bilateral_pairs": {"收到的其他与投资活动的现金": "支付的其他与投资活动的现金"},
          "bilateral_tolerance": 0.05
        }
      }
    }
    """
    config_path = Path(path)
    if not config_path.exists():
        return {}
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    result: dict[str, EntityConfig] = {}
    for entity_id, raw in payload.get("entities", {}).items():
        mappings = raw.get("tb_to_bs_mappings")
        reclass_raw = raw.get("reclass_pairs")
        bs_accounts_raw = raw.get("balance_sheet_accounts")
        bilateral_raw = raw.get("bilateral_pairs")
        result[entity_id] = EntityConfig(
            entity_id=entity_id,
            tolerance=float(raw.get("tolerance", 0.01)),
            industry=str(raw.get("industry", "general")),
            cash_equivalent_codes=tuple(
                str(code) for code in raw.get("cash_equivalent_codes", ["1001", "1002"])
            ),
            tb_to_bs_mappings=(
                dict(_DEFAULT_TB_BS_MAPPINGS)
                if mappings is None
                else {str(key): dict(value) for key, value in mappings.items()}
            ),
            reclass_pairs=(
                None
                if reclass_raw is None
                else {
                    str(key): _parse_str_tuple(value)
                    for key, value in reclass_raw.items()
                }
            ),
            balance_sheet_accounts=(
                None
                if bs_accounts_raw is None
                else {str(key): str(value) for key, value in bs_accounts_raw.items()}
            ),
            margin_tolerance=(
                None if raw.get("margin_tolerance") is None
                else float(raw["margin_tolerance"])
            ),
            bilateral_pairs=(
                None
                if bilateral_raw is None
                else {str(key): str(value) for key, value in bilateral_raw.items()}
            ),
            bilateral_tolerance=(
                None if raw.get("bilateral_tolerance") is None
                else float(raw["bilateral_tolerance"])
            ),
        )
    return result
