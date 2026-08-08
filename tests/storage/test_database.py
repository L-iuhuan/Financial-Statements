"""Database 连接与 schema 初始化测试。"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from fsa.storage.database import Database


class TestDatabaseConnect:
    """数据库连接测试。"""

    def test_connect_creates_db_file(self, db_path: Path) -> None:
        # Arrange
        db = Database(db_path)

        # Act
        db.connect()

        # Assert
        assert db_path.exists()

        db.close()

    def test_connect_creates_parent_directory(self, tmp_path: Path) -> None:
        # Arrange
        path = tmp_path / "sub" / "deep" / "data.db"
        db = Database(path)

        # Act
        db.connect()

        # Assert
        assert path.exists()
        assert path.parent.exists()

        db.close()

    def test_connection_returns_valid_connection(self, db: Database) -> None:
        # Act
        conn = db.connection

        # Assert
        assert isinstance(conn, sqlite3.Connection)

    def test_connection_before_connect_raises(self, db_path: Path) -> None:
        # Arrange
        db = Database(db_path)

        # Act + Assert
        with pytest.raises(RuntimeError, match="数据库未连接"):
            _ = db.connection

    def test_path_property_returns_configured_path(
        self, db_path: Path
    ) -> None:
        # Arrange
        db = Database(db_path)

        # Act
        result = db.path

        # Assert
        assert result == db_path

    def test_close_sets_connection_to_none(self, db_path: Path) -> None:
        # Arrange
        db = Database(db_path)
        db.connect()

        # Act
        db.close()

        # Assert
        with pytest.raises(RuntimeError):
            _ = db.connection

    def test_close_when_already_closed_is_noop(
        self, db_path: Path
    ) -> None:
        # Arrange
        db = Database(db_path)
        db.connect()
        db.close()

        # Act (should not raise)
        db.close()


class TestDatabaseSchema:
    """Schema 初始化测试。"""

    def test_init_schema_creates_all_tables(self, db: Database) -> None:
        # Act
        conn = db.connection
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = {row["name"] for row in rows}

        # Assert
        assert "validation_history" in table_names
        assert "validation_results" in table_names
        assert "chat_sessions" in table_names
        assert "chat_messages" in table_names

    def test_init_schema_is_idempotent(self, db_path: Path) -> None:
        # Arrange
        db = Database(db_path)
        db.connect()
        db.init_schema()

        # Act - second init should not raise
        db.init_schema()

        # Assert
        conn = db.connection
        count = conn.execute(
            "SELECT COUNT(*) as cnt FROM sqlite_master "
            "WHERE type='table' AND name='validation_history'"
        ).fetchone()
        assert count["cnt"] == 1

        db.close()

    def test_init_schema_before_connect_raises(
        self, db_path: Path
    ) -> None:
        # Arrange
        db = Database(db_path)

        # Act + Assert
        with pytest.raises(RuntimeError, match="数据库未连接"):
            db.init_schema()

    def test_wal_mode_enabled(self, db: Database) -> None:
        # Act
        row = db.connection.execute(
            "PRAGMA journal_mode"
        ).fetchone()

        # Assert
        assert row[0].lower() == "wal"

    def test_foreign_keys_enabled(self, db: Database) -> None:
        # Act
        row = db.connection.execute(
            "PRAGMA foreign_keys"
        ).fetchone()

        # Assert
        assert row[0] == 1


class TestDatabaseContextManager:
    """上下文管理器测试。"""

    def test_context_manager_connects_and_inits(
        self, db_path: Path
    ) -> None:
        # Arrange
        db = Database(db_path)

        # Act
        with db:
            conn = db.connection
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()

        # Assert
        assert len(tables) >= 4

    def test_context_manager_closes_on_exit(
        self, db_path: Path
    ) -> None:
        # Arrange
        db = Database(db_path)

        # Act
        with db:
            _ = db.connection

        # Assert
        with pytest.raises(RuntimeError):
            _ = db.connection

    def test_context_manager_closes_on_exception(
        self, db_path: Path
    ) -> None:
        # Arrange
        db = Database(db_path)

        # Act
        with pytest.raises(ValueError):
            with db:
                raise ValueError("test error")

        # Assert
        with pytest.raises(RuntimeError):
            _ = db.connection
