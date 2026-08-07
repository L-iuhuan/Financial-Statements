"""从 JSON 规则库文件加载勾稽校验规则。"""

from __future__ import annotations

import json
from pathlib import Path

from fsa.core.models.rule import ReconciliationRule, Severity, ToleranceType


def load_rules_from_json(file_path: str | Path) -> list[ReconciliationRule]:
    """从 JSON 规则库文件加载规则。

    Args:
        file_path: 规则库 JSON 文件路径

    Returns:
        list[ReconciliationRule] 规则列表

    Raises:
        FileNotFoundError: 文件不存在
        json.JSONDecodeError: JSON 格式无效
        KeyError: 缺少必需字段
        ValueError: tolerance_type 或 severity 字符串无效
    """
    path = Path(file_path)
    data = json.loads(path.read_text(encoding="utf-8"))

    rules_data = data["ruleLibrary"]["rules"]
    return [_parse_rule(raw) for raw in rules_data]


def _parse_rule(raw: dict) -> ReconciliationRule:
    """将单条 JSON 规则数据转换为 ReconciliationRule。"""
    return ReconciliationRule(
        rule_id=raw["id"],
        name=raw["name"],
        category=raw["category"],
        statements=raw["statements"],
        formula=raw["formula"],
        tolerance_type=ToleranceType(raw["tolerance_type"]),
        tolerance=float(raw["default_tolerance"]),
        severity=Severity(raw["severity"]),
        cas_ref=raw.get("cas_ref", ""),
        notes=raw.get("notes", ""),
    )
