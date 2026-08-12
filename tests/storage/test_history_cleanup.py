"""HistoryRepo 历史记录自动清理测试。

覆盖: delete_older_than 删除过期记录、空表安全、返回正确计数。
"""

from __future__ import annotations

from fsa.storage.database import Database
from fsa.storage.history_repo import HistoryRepo
from tests.storage.conftest import make_summary


class TestHistoryRepoDeleteOlderThan:
    """delete_older_than 测试。"""

    def test_delete_older_than_removes_old_records(
        self, db: Database
    ) -> None:
        # Arrange: 插入多条记录并手动修改 created_at 为过去日期
        repo = HistoryRepo(db)
        conn = db.connection

        for i in range(5):
            summary = make_summary(period=f"2024年{i+1}月")
            repo.save(summary)

        # 将前 3 条记录 backdate 到 200 天前
        conn.execute(
            "UPDATE validation_history SET created_at = "
            "datetime('now', 'localtime', '-200 days') "
            "WHERE id IN (SELECT id FROM validation_history "
            "ORDER BY id LIMIT 3)"
        )
        conn.commit()

        # Act
        deleted = repo.delete_older_than(90)

        # Assert
        assert deleted == 3
        assert repo.count() == 2

    def test_delete_older_than_keeps_recent_records(
        self, db: Database
    ) -> None:
        # Arrange: 插入记录，不过期
        repo = HistoryRepo(db)
        for i in range(3):
            summary = make_summary(period=f"2024年{i+1}月")
            repo.save(summary)

        # Act
        deleted = repo.delete_older_than(90)

        # Assert
        assert deleted == 0
        assert repo.count() == 3

    def test_delete_older_than_empty_table_returns_zero(
        self, db: Database
    ) -> None:
        # Arrange
        repo = HistoryRepo(db)

        # Act
        deleted = repo.delete_older_than(90)

        # Assert
        assert deleted == 0

    def test_delete_older_than_with_zero_days_deletes_nothing(
        self, db: Database
    ) -> None:
        # Arrange
        repo = HistoryRepo(db)
        summary = make_summary()
        repo.save(summary)

        # Act: 0 天保留 = 不删除任何记录（datediff 为 0 不匹配 <）
        deleted = repo.delete_older_than(0)

        # Assert
        assert deleted == 0
        assert repo.count() == 1

    def test_delete_older_than_cascades_to_results(
        self, db: Database
    ) -> None:
        # Arrange: 创建一条已过期的记录
        repo = HistoryRepo(db)
        conn = db.connection
        summary = make_summary()
        history_id = repo.save(summary)
        conn.execute(
            "UPDATE validation_history SET created_at = "
            "datetime('now', 'localtime', '-200 days') "
            "WHERE id = ?", (history_id,)
        )
        conn.commit()

        # Act
        deleted = repo.delete_older_than(90)

        # Assert
        assert deleted == 1
        assert repo.count() == 0
        assert repo.get_detail(history_id) == []
