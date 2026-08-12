"""自定义规则持久化: 读写 custom_rules.json。

自定义规则独立于内置规则库存储, 启动时合并加载。
冻结模式下写入用户目录 (内置规则库所在目录可能只读)。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from loguru import logger

from fsa.core.models.rule import ReconciliationRule, Severity, ToleranceType
from fsa.core.resources import resource_path

_FILE_NAME = "custom_rules.json"


def _custom_rules_path() -> Path:
    """返回自定义规则文件路径。

    冻结模式下内置规则库所在目录可能只读, 故写到用户目录;
    开发模式写到项目根目录 (与内置规则库同级)。
    """
    if getattr(sys, "frozen", False):
        base = Path.home() / ".fsa"
        base.mkdir(parents=True, exist_ok=True)
        return base / _FILE_NAME
    return resource_path(_FILE_NAME)


def load_custom_rules() -> list[ReconciliationRule]:
    """加载自定义规则。文件不存在或损坏时返回空列表 (不抛异常)。"""
    path = _custom_rules_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"自定义规则文件损坏, 忽略: {e}")
        return []
    rules: list[ReconciliationRule] = []
    for raw in data.get("rules", []):
        try:
            rules.append(_parse(raw))
        except (KeyError, ValueError) as e:
            logger.warning(f"跳过无效自定义规则: {e}")
    return rules


def save_custom_rules(rules: list[ReconciliationRule]) -> None:
    """将自定义规则写入 JSON 文件。"""
    path = _custom_rules_path()
    payload = {"rules": [_to_dict(r) for r in rules]}
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logger.info(f"已保存 {len(rules)} 条自定义规则到 {path}")


def _parse(raw: dict) -> ReconciliationRule:
    """将 JSON 字典解析为 ReconciliationRule。"""
    return ReconciliationRule(
        rule_id=raw["id"],
        name=raw["name"],
        category=raw["category"],
        statements=list(raw["statements"]),
        formula=raw["formula"],
        tolerance_type=ToleranceType(raw["tolerance_type"]),
        tolerance=float(raw["default_tolerance"]),
        severity=Severity(raw["severity"]),
        cas_ref=raw.get("cas_ref", ""),
        notes=raw.get("notes", ""),
    )


def _to_dict(rule: ReconciliationRule) -> dict:
    """将 ReconciliationRule 转为 JSON 字典。"""
    return {
        "id": rule.rule_id,
        "name": rule.name,
        "category": rule.category,
        "statements": rule.statements,
        "formula": rule.formula,
        "tolerance_type": rule.tolerance_type.value,
        "default_tolerance": rule.tolerance,
        "severity": rule.severity.value,
        "cas_ref": rule.cas_ref,
        "notes": rule.notes,
    }
