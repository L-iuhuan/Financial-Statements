"""AppState 容差覆写持久化测试。

验证: 规则容差覆写从 SQLite 加载后应用到注册表。
"""

from __future__ import annotations

from pathlib import Path

from fsa.core.engine.registry import RuleRegistry
from fsa.core.models.rule import ReconciliationRule, Severity, ToleranceType
from fsa.gui.app_state import AppState
from fsa.storage.database import Database
from fsa.storage.history_repo import HistoryRepo
from fsa.storage.override_repo import RuleOverrideRepo


def _make_rule(rule_id: str, tolerance: float = 0.01) -> ReconciliationRule:
    """创建测试规则。"""
    return ReconciliationRule(
        rule_id=rule_id,
        name=f"测试规则{rule_id}",
        category="A-表内平衡",
        statements=["资产负债表"],
        formula="a == b",
        tolerance_type=ToleranceType.EXACT,
        tolerance=tolerance,
        severity=Severity.ERROR,
    )


def _make_registry() -> RuleRegistry:
    """创建测试注册表。"""
    return RuleRegistry([
        _make_rule("BS-BAL-001", tolerance=0.01),
        _make_rule("BS-BAL-002", tolerance=0.01),
        _make_rule("BS-BAL-003", tolerance=0.01),
    ])


class TestTolerancePersistence:
    """容差覆写持久化测试。"""

    def test_override_applied_to_registry_on_load(self, tmp_path: Path) -> None:
        # Arrange: 创建数据库，写入覆写
        db_path = tmp_path / "test_tol.db"
        db = Database(db_path)
        db.connect()
        db.init_schema()
        repo = RuleOverrideRepo(db)
        repo.set("BS-BAL-001", 0.05)
        repo.set("BS-BAL-002", 1.0)
        db.close()

        # Act: 创建 AppState, 替换为测试 DB 并重建 repos
        state = AppState()
        state._db.close()
        state._db = Database(db_path)
        state._db.connect()
        state._db.init_schema()
        state._override_repo = RuleOverrideRepo(state._db)
        state._history_repo = HistoryRepo(state._db)
        state._registry = _make_registry()
        state._apply_overrides()

        # Assert
        registry = state.registry
        assert registry is not None
        rule1 = registry.get_by_id("BS-BAL-001")
        rule2 = registry.get_by_id("BS-BAL-002")
        rule3 = registry.get_by_id("BS-BAL-003")
        assert rule1 is not None and rule1.tolerance == 0.05
        assert rule2 is not None and rule2.tolerance == 1.0
        assert rule3 is not None and rule3.tolerance == 0.01  # 未覆写, 保持默认

        state.close()

    def test_no_overrides_when_table_empty(self, tmp_path: Path) -> None:
        # Arrange: 空数据库（无覆写记录）
        db_path = tmp_path / "test_tol_empty.db"
        db = Database(db_path)
        db.connect()
        db.init_schema()
        db.close()

        # Act
        state = AppState()
        state._db.close()
        state._db = Database(db_path)
        state._db.connect()
        state._db.init_schema()
        state._override_repo = RuleOverrideRepo(state._db)
        state._history_repo = HistoryRepo(state._db)
        state._registry = _make_registry()
        state._apply_overrides()

        # Assert: 所有规则保持默认容差
        registry = state.registry
        assert registry is not None
        for rule in registry.get_all():
            assert rule.tolerance == 0.01

        state.close()

    def test_override_applied_after_load_registry(self, tmp_path: Path) -> None:
        # Arrange: 具有覆写记录的数据库
        db_path = tmp_path / "test_tol_flow.db"
        db = Database(db_path)
        db.connect()
        db.init_schema()
        repo = RuleOverrideRepo(db)
        repo.set("BS-BAL-001", 0.05)
        db.close()

        # Act: 模拟 AppState 初始化流程
        state = AppState()
        state._db.close()
        state._db = Database(db_path)
        state._db.connect()
        state._db.init_schema()
        state._override_repo = RuleOverrideRepo(state._db)
        state._history_repo = HistoryRepo(state._db)
        state._registry = _make_registry()
        state._apply_overrides()

        # Assert: 覆写已生效
        rule = state.registry.get_by_id("BS-BAL-001")
        assert rule is not None
        assert rule.tolerance == 0.05

        state.close()
