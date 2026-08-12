"""RuleOverrideRepo 规则容差覆写仓库测试。

覆盖: 设置、读取、覆盖、删除、清空、跨实例持久化。
"""

from __future__ import annotations

from fsa.storage.database import Database
from fsa.storage.override_repo import RuleOverrideRepo


class TestRuleOverrideRepoSetAndGet:
    """设置与读取测试。"""

    def test_set_and_get_all_roundtrip(self, db: Database) -> None:
        # Arrange
        repo = RuleOverrideRepo(db)
        repo.set("BS-BAL-001", 0.05)
        repo.set("BS-BAL-002", 1.0)

        # Act
        overrides = repo.get_all()

        # Assert
        assert overrides == {"BS-BAL-001": 0.05, "BS-BAL-002": 1.0}

    def test_overwrite_existing_rule_id(self, db: Database) -> None:
        # Arrange
        repo = RuleOverrideRepo(db)
        repo.set("BS-BAL-001", 0.05)

        # Act
        repo.set("BS-BAL-001", 0.10)
        overrides = repo.get_all()

        # Assert
        assert overrides == {"BS-BAL-001": 0.10}

    def test_get_all_empty(self, db: Database) -> None:
        # Arrange
        repo = RuleOverrideRepo(db)

        # Act
        overrides = repo.get_all()

        # Assert
        assert overrides == {}


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
        assert overrides == {"BS-BAL-002": 1.0}

    def test_delete_nonexistent_is_noop(self, db: Database) -> None:
        # Arrange
        repo = RuleOverrideRepo(db)
        repo.set("BS-BAL-001", 0.05)

        # Act
        repo.delete("NONEXISTENT")
        overrides = repo.get_all()

        # Assert
        assert overrides == {"BS-BAL-001": 0.05}

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
        assert overrides == {"BS-BAL-001": 0.05, "BS-BAL-002": 1.0}

    def test_persistence_across_db_reopen(
        self, db_path
    ) -> None:
        # Arrange: 连接、写入、关闭
        db1 = Database(db_path)
        db1.connect()
        db1.init_schema()
        repo1 = RuleOverrideRepo(db1)
        repo1.set("BS-BAL-001", 0.05)
        db1.close()

        # Act: 重新连接、读取
        db2 = Database(db_path)
        db2.connect()
        db2.init_schema()
        repo2 = RuleOverrideRepo(db2)
        overrides = repo2.get_all()
        db2.close()

        # Assert
        assert overrides == {"BS-BAL-001": 0.05}
