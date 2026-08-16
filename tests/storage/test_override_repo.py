"""RuleOverrideRepo 规则容差/启停覆写仓库测试。

覆盖: 容差设置/读取/覆盖/删除/清空、启停读写、幂等迁移、跨实例持久化。
"""

from __future__ import annotations

from pathlib import Path

from fsa.storage.database import Database
from fsa.storage.override_repo import RuleOverride, RuleOverrideRepo


class TestRuleOverrideRepoSetAndGet:
    """容差设置与读取测试。"""

    def test_set_and_get_all_roundtrip(self, db: Database) -> None:
        # Arrange
        repo = RuleOverrideRepo(db)
        repo.set("BS-BAL-001", 0.05)
        repo.set("BS-BAL-002", 1.0)

        # Act
        overrides = repo.get_all()

        # Assert
        assert overrides == {
            "BS-BAL-001": RuleOverride(tolerance=0.05, enabled=True),
            "BS-BAL-002": RuleOverride(tolerance=1.0, enabled=True),
        }

    def test_overwrite_existing_rule_id(self, db: Database) -> None:
        # Arrange
        repo = RuleOverrideRepo(db)
        repo.set("BS-BAL-001", 0.05)

        # Act
        repo.set("BS-BAL-001", 0.10)
        overrides = repo.get_all()

        # Assert
        assert overrides == {"BS-BAL-001": RuleOverride(tolerance=0.10, enabled=True)}

    def test_get_all_empty(self, db: Database) -> None:
        # Arrange
        repo = RuleOverrideRepo(db)

        # Act
        overrides = repo.get_all()

        # Assert
        assert overrides == {}


class TestRuleOverrideRepoEnabled:
    """启停覆写读写测试 (审查报告 2026-08-16 终审 P2 补修)。"""

    def test_set_enabled_insert_new_rule(self, db: Database) -> None:
        """尚无覆写记录时插入, 容差随当前生效值写入, 启停为新值。"""
        repo = RuleOverrideRepo(db)

        repo.set_enabled("BS-BAL-001", False, 0.01)
        overrides = repo.get_all()

        assert overrides == {"BS-BAL-001": RuleOverride(tolerance=0.01, enabled=False)}

    def test_set_enabled_preserves_existing_tolerance(self, db: Database) -> None:
        """已有容差覆写时切换启停, 容差不被覆盖。"""
        repo = RuleOverrideRepo(db)
        repo.set("BS-BAL-001", 0.05)

        repo.set_enabled("BS-BAL-001", False, 0.01)
        overrides = repo.get_all()

        assert overrides == {"BS-BAL-001": RuleOverride(tolerance=0.05, enabled=False)}

    def test_set_tolerance_preserves_existing_enabled(self, db: Database) -> None:
        """已禁用规则再改容差, 启停状态不被覆盖。"""
        repo = RuleOverrideRepo(db)
        repo.set_enabled("BS-BAL-001", False, 0.01)

        repo.set("BS-BAL-001", 0.10)
        overrides = repo.get_all()

        assert overrides == {"BS-BAL-001": RuleOverride(tolerance=0.10, enabled=False)}

    def test_set_enabled_toggle_back(self, db: Database) -> None:
        """禁用后可再启用。"""
        repo = RuleOverrideRepo(db)
        repo.set_enabled("BS-BAL-001", False, 0.01)

        repo.set_enabled("BS-BAL-001", True, 0.01)

        assert repo.get_all()["BS-BAL-001"].enabled is True


class TestRuleOverrideRepoDelete:
    """删除测试。"""

    def test_delete_removes_entry(self, db: Database) -> None:
        # Arrange
        repo = RuleOverrideRepo(db)
        repo.set("BS-BAL-001", 0.05)
        repo.set("BS-BAL-002", 1.0)

        # Act
        repo.delete("BS-BAL-001")
        overrides = repo.get_all()

        # Assert
        assert overrides == {"BS-BAL-002": RuleOverride(tolerance=1.0, enabled=True)}

    def test_delete_nonexistent_is_noop(self, db: Database) -> None:
        # Arrange
        repo = RuleOverrideRepo(db)
        repo.set("BS-BAL-001", 0.05)

        # Act
        repo.delete("NONEXISTENT")
        overrides = repo.get_all()

        # Assert
        assert overrides == {"BS-BAL-001": RuleOverride(tolerance=0.05, enabled=True)}

    def test_clear_removes_all(self, db: Database) -> None:
        # Arrange
        repo = RuleOverrideRepo(db)
        repo.set("A", 0.1)
        repo.set("B", 0.2)
        repo.set("C", 0.3)

        # Act
        repo.clear()
        overrides = repo.get_all()

        # Assert
        assert overrides == {}

    def test_clear_empty_table_is_noop(self, db: Database) -> None:
        # Arrange
        repo = RuleOverrideRepo(db)

        # Act
        repo.clear()
        overrides = repo.get_all()

        # Assert
        assert overrides == {}


class TestRuleOverrideRepoPersistence:
    """跨实例持久化测试。"""

    def test_persistence_across_repo_instances(
        self, db_path, db: Database
    ) -> None:
        # Arrange: 写入
        repo1 = RuleOverrideRepo(db)
        repo1.set("BS-BAL-001", 0.05)
        repo1.set("BS-BAL-002", 1.0)

        # Act: 用新实例读取（同一数据库）
        repo2 = RuleOverrideRepo(db)
        overrides = repo2.get_all()

        # Assert
        assert overrides == {
            "BS-BAL-001": RuleOverride(tolerance=0.05, enabled=True),
            "BS-BAL-002": RuleOverride(tolerance=1.0, enabled=True),
        }

    def test_persistence_across_db_reopen(
        self, db_path
    ) -> None:
        # Arrange: 连接、写入、关闭
        db1 = Database(db_path)
        db1.connect()
        db1.init_schema()
        repo1 = RuleOverrideRepo(db1)
        repo1.set("BS-BAL-001", 0.05)
        repo1.set_enabled("BS-BAL-002", False, 0.01)
        db1.close()

        # Act: 重新连接、读取
        db2 = Database(db_path)
        db2.connect()
        db2.init_schema()
        repo2 = RuleOverrideRepo(db2)
        overrides = repo2.get_all()
        db2.close()

        # Assert: 容差与启停均跨重开持久化
        assert overrides == {
            "BS-BAL-001": RuleOverride(tolerance=0.05, enabled=True),
            "BS-BAL-002": RuleOverride(tolerance=0.01, enabled=False),
        }


class TestRuleOverridesEnabledMigration:
    """rule_overrides 表 enabled 列幂等迁移测试 (终审 P2 补修)。"""

    def _create_legacy_table(self, db_path: Path) -> None:
        """模拟旧版本数据库: rule_overrides 无 enabled 列且已有数据。"""
        db = Database(db_path)
        db.connect()
        db.connection.execute(
            "CREATE TABLE rule_overrides (rule_id TEXT PRIMARY KEY, tolerance REAL NOT NULL)"
        )
        db.connection.execute(
            "INSERT INTO rule_overrides (rule_id, tolerance) VALUES ('BS-BAL-001', 0.05)"
        )
        db.connection.commit()
        db.close()

    def test_legacy_table_migrated_with_default_enabled(self, tmp_path: Path) -> None:
        """旧表迁移后新增 enabled 列, 存量行默认启用, 覆写数据不丢失。"""
        db_path = tmp_path / "legacy.db"
        self._create_legacy_table(db_path)

        db = Database(db_path)
        db.connect()
        db.init_schema()
        overrides = RuleOverrideRepo(db).get_all()
        db.close()

        assert overrides == {"BS-BAL-001": RuleOverride(tolerance=0.05, enabled=True)}

    def test_migration_is_idempotent(self, tmp_path: Path) -> None:
        """init_schema 重复执行不报错, 迁移可重入。"""
        db_path = tmp_path / "legacy_idem.db"
        self._create_legacy_table(db_path)

        db = Database(db_path)
        db.connect()
        db.init_schema()
        db.init_schema()
        db.init_schema()
        overrides = RuleOverrideRepo(db).get_all()
        db.close()

        assert overrides == {"BS-BAL-001": RuleOverride(tolerance=0.05, enabled=True)}
