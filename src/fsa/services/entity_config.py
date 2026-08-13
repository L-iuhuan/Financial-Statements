"""主体级口径配置: 现金等价物范围、余额表映射、容差等可按公司覆盖。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from fsa.services.detail_validation_service import (
    _DEFAULT_TB_BS_MAPPINGS,
    DetailCheckConfig,
)


@dataclass(frozen=True)
class EntityConfig:
    """单个主体的明细校验口径。"""

    entity_id: str = ""
    tolerance: float = 0.01
    cash_equivalent_codes: tuple[str, ...] = ("1001", "1002")
    tb_to_bs_mappings: dict[str, dict[str, object]] = field(
        default_factory=lambda: dict(_DEFAULT_TB_BS_MAPPINGS)
    )

    def to_detail_config(self) -> DetailCheckConfig:
        """转换为明细校验配置。"""
        return DetailCheckConfig(
            tolerance=self.tolerance,
            cash_equivalent_codes=self.cash_equivalent_codes,
            tb_to_bs_mappings=self.tb_to_bs_mappings,
        )


def load_entity_configs(path: str | Path) -> dict[str, EntityConfig]:
    """从 JSON 文件加载主体配置。

    格式:
    {
      "entities": {
        "杭州杰为科技有限公司": {
          "tolerance": 0.01,
          "cash_equivalent_codes": ["1001", "1002"],
          "tb_to_bs_mappings": {
            "monetary_funds": {"codes": ["1001","1002","1012"], "side": "debit"}
          }
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
        result[entity_id] = EntityConfig(
            entity_id=entity_id,
            tolerance=float(raw.get("tolerance", 0.01)),
            cash_equivalent_codes=tuple(
                str(code) for code in raw.get("cash_equivalent_codes", ["1001", "1002"])
            ),
            tb_to_bs_mappings=(
                dict(_DEFAULT_TB_BS_MAPPINGS)
                if mappings is None
                else {str(key): dict(value) for key, value in mappings.items()}
            ),
        )
    return result
