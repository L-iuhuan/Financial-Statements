"""RuleLoader 的单元测试。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fsa.core.engine.rule_loader import load_rules_from_json
from fsa.core.models.rule import Severity, ToleranceType

RULE_LIBRARY = (
    Path(__file__).resolve().parent.parent.parent / "cas_gouji_rule_library.json"
)


def _write_json(tmp_path: Path, payload: dict) -> Path:
    """将 dict 写入临时 JSON 文件并返回路径。"""
    path = tmp_path / "rules.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


class TestLoadFromRealFile:
    """从真实规则库文件加载。"""

    def test_load_all_44_rules(self) -> None:
        rules = load_rules_from_json(RULE_LIBRARY)
        assert len(rules) == 44

    def test_first_rule_fields(self) -> None:
        rules = load_rules_from_json(RULE_LIBRARY)
        first = rules[0]
        assert first.rule_id == "BS-BAL-001"
        assert first.name == "资产=负债+所有者权益"
        assert first.category == "A-表内平衡"
        assert first.statements == ["资产负债表"]
        assert first.formula == "asset_total == liability_total + equity_total"
        assert first.tolerance_type is ToleranceType.EXACT
        assert first.tolerance == 0.01
        assert first.severity is Severity.ERROR
        assert "会计恒等式" in first.cas_ref
        assert first.notes == "基本平衡关系; 破坏即报表编制错误"

    def test_rule_id_preserved_for_all(self) -> None:
        rules = load_rules_from_json(RULE_LIBRARY)
        expected_ids = {
            "BS-BAL-001",
            "BS-BAL-002",
            "BS-BAL-003",
            "BS-BAL-004",
            "BS-BAL-005",
            "IS-BAL-001",
            "IS-BAL-002",
            "IS-BAL-003",
            "IS-BAL-004",
            "IS-BAL-005",
            "CF-BAL-001",
            "CF-BAL-002",
            "CF-BAL-003",
            "CF-BAL-004",
            "SCE-BAL-001",
            "SCE-BAL-002",
            "BS-IS-001",
            "BS-IS-002",
            "BS-CF-001",
            "IS-CF-001",
            "IS-CF-002",
            "IS-CF-003",
            "SCE-IS-001",
            "SCE-IS-002",
            "SCE-IS-003",
            "SCE-BS-001",
            "IS-TAX-001",
            "NOTES-001",
            "NOTES-002",
            "NOTES-003",
            "LR-GM-001",
            "LR-GM-002",
            "LR-DAR-001",
            "LR-OCF-001",
            "LR-ART-001",
            "LR-INV-001",
            "LR-FLUC-001",
            "LR-RE-001",
            "LR-RE-002",
            "LR-SALES-001",
            "LR-QUICK-001",
            "LR-OCF-002",
            "LR-NONREC-001",
            "LR-FIX-001",
        }
        assert {r.rule_id for r in rules} == expected_ids

    def test_tolerance_types_present(self) -> None:
        rules = load_rules_from_json(RULE_LIBRARY)
        types = {r.tolerance_type for r in rules}
        assert types == {
            ToleranceType.EXACT,
            ToleranceType.ABSOLUTE,
            ToleranceType.RELATIVE,
            ToleranceType.THRESHOLD,
        }

    def test_severities_present(self) -> None:
        rules = load_rules_from_json(RULE_LIBRARY)
        sevs = {r.severity for r in rules}
        assert sevs == {Severity.ERROR, Severity.WARNING, Severity.INFO}

    def test_float_tolerance_conversion(self) -> None:
        """NOTES-003 的 default_tolerance=0.2 应转为 float。"""
        rules = load_rules_from_json(RULE_LIBRARY)
        by_id = {r.rule_id: r for r in rules}
        assert by_id["NOTES-003"].tolerance == 0.2
        assert isinstance(by_id["NOTES-003"].tolerance, float)


class TestLoadEdgeCases:
    """加载边界场景。"""

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        missing = tmp_path / "nope.json"
        with pytest.raises(FileNotFoundError):
            load_rules_from_json(missing)

    def test_invalid_json_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.json"
        path.write_text("{not valid json", encoding="utf-8")
        with pytest.raises(json.JSONDecodeError):
            load_rules_from_json(path)

    def test_missing_required_field_raises(self, tmp_path: Path) -> None:
        payload = {
            "ruleLibrary": {
                "rules": [
                    {
                        "id": "X-001",
                        "name": "测试",
                        "category": "A",
                        "statements": ["资产负债表"],
                        "formula": "a == b",
                        "tolerance_type": "exact",
                        "default_tolerance": 0.01,
                        "severity": "error",
                    }
                ]
            }
        }
        # 删除 formula 字段以触发 KeyError
        del payload["ruleLibrary"]["rules"][0]["formula"]
        path = _write_json(tmp_path, payload)
        with pytest.raises(KeyError):
            load_rules_from_json(path)

    def test_invalid_tolerance_type_raises(self, tmp_path: Path) -> None:
        payload = {
            "ruleLibrary": {
                "rules": [
                    {
                        "id": "X-001",
                        "name": "测试",
                        "category": "A",
                        "statements": ["资产负债表"],
                        "formula": "a == b",
                        "tolerance_type": "bogus",
                        "default_tolerance": 0.01,
                        "severity": "error",
                    }
                ]
            }
        }
        path = _write_json(tmp_path, payload)
        with pytest.raises(ValueError):
            load_rules_from_json(path)

    def test_invalid_severity_raises(self, tmp_path: Path) -> None:
        payload = {
            "ruleLibrary": {
                "rules": [
                    {
                        "id": "X-001",
                        "name": "测试",
                        "category": "A",
                        "statements": ["资产负债表"],
                        "formula": "a == b",
                        "tolerance_type": "exact",
                        "default_tolerance": 0.01,
                        "severity": "bogus",
                    }
                ]
            }
        }
        path = _write_json(tmp_path, payload)
        with pytest.raises(ValueError):
            load_rules_from_json(path)

    def test_empty_rules_returns_empty_list(self, tmp_path: Path) -> None:
        payload = {"ruleLibrary": {"rules": []}}
        path = _write_json(tmp_path, payload)
        rules = load_rules_from_json(path)
        assert rules == []

    def test_name_en_ignored(self, tmp_path: Path) -> None:
        """name_en 字段存在时不应报错，且不进入模型。"""
        payload = {
            "ruleLibrary": {
                "rules": [
                    {
                        "id": "X-001",
                        "name": "测试",
                        "name_en": "Test",
                        "category": "A",
                        "statements": ["资产负债表"],
                        "formula": "a == b",
                        "tolerance_type": "absolute",
                        "default_tolerance": 0.5,
                        "severity": "warning",
                        "cas_ref": "ref",
                        "notes": "note",
                    }
                ]
            }
        }
        path = _write_json(tmp_path, payload)
        rules = load_rules_from_json(path)
        rule = rules[0]
        assert rule.tolerance_type is ToleranceType.ABSOLUTE
        assert rule.severity is Severity.WARNING
        assert rule.tolerance == 0.5
        assert not hasattr(rule, "name_en")


class TestEnumConversion:
    """枚举转换测试。"""

    def test_tolerance_type_conversions(self, tmp_path: Path) -> None:
        cases = {
            "exact": ToleranceType.EXACT,
            "absolute": ToleranceType.ABSOLUTE,
            "relative": ToleranceType.RELATIVE,
            "threshold": ToleranceType.THRESHOLD,
        }
        for raw, expected in cases.items():
            payload = {
                "ruleLibrary": {
                    "rules": [
                        {
                            "id": "X-001",
                            "name": "测试",
                            "category": "A",
                            "statements": ["资产负债表"],
                            "formula": "a == b",
                            "tolerance_type": raw,
                            "default_tolerance": 0.01,
                            "severity": "error",
                        }
                    ]
                }
            }
            path = _write_json(tmp_path, payload)
            rules = load_rules_from_json(path)
            assert rules[0].tolerance_type is expected

    def test_severity_conversions(self, tmp_path: Path) -> None:
        cases = {
            "error": Severity.ERROR,
            "warning": Severity.WARNING,
            "info": Severity.INFO,
        }
        for raw, expected in cases.items():
            payload = {
                "ruleLibrary": {
                    "rules": [
                        {
                            "id": "X-001",
                            "name": "测试",
                            "category": "A",
                            "statements": ["资产负债表"],
                            "formula": "a == b",
                            "tolerance_type": "exact",
                            "default_tolerance": 0.01,
                            "severity": raw,
                        }
                    ]
                }
            }
            path = _write_json(tmp_path, payload)
            rules = load_rules_from_json(path)
            assert rules[0].severity is expected
