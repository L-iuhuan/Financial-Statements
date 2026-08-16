"""SQLite 数据库连接管理: WAL 模式 + Schema 初始化。

遵循 AGENTS.md: 持久化层独立, 不依赖 GUI 或业务逻辑。
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from types import TracebackType

from loguru import logger

# 默认数据库路径
_DEFAULT_DB_PATH = Path.home() / ".fsa" / "data.db"

# Schema DDL (CREATE IF NOT EXISTS)
_SCHEMA_DDL = """
-- 校验历史主表
CREATE TABLE IF NOT EXISTS validation_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    period      TEXT NOT NULL DEFAULT '',
    total       INTEGER NOT NULL DEFAULT 0,
    passed      INTEGER NOT NULL DEFAULT 0,
    failed      INTEGER NOT NULL DEFAULT 0,
    errored     INTEGER NOT NULL DEFAULT 0,
    skipped     INTEGER NOT NULL DEFAULT 0,
    report_types TEXT NOT NULL DEFAULT '[]',
    source_files TEXT NOT NULL DEFAULT '[]',
    source_hashes TEXT NOT NULL DEFAULT '[]',
    rule_version TEXT NOT NULL DEFAULT ''
);

-- 校验结果明细表
CREATE TABLE IF NOT EXISTS validation_results (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    history_id  INTEGER NOT NULL REFERENCES validation_history(id) ON DELETE CASCADE,
    rule_id     TEXT NOT NULL,
    rule_name   TEXT NOT NULL DEFAULT '',
    passed      INTEGER NOT NULL DEFAULT 0,
    severity    TEXT NOT NULL DEFAULT 'error',
    left_value  REAL NOT NULL DEFAULT 0,
    right_value REAL NOT NULL DEFAULT 0,
    diff        REAL NOT NULL DEFAULT 0,
    tolerance   REAL NOT NULL DEFAULT 0,
    formula     TEXT NOT NULL DEFAULT '',
    message     TEXT NOT NULL DEFAULT '',
    errored     INTEGER NOT NULL DEFAULT 0,
    skipped     INTEGER NOT NULL DEFAULT 0,
    category    TEXT NOT NULL DEFAULT '',
    trace       TEXT NOT NULL DEFAULT '[]'
);
CREATE INDEX IF NOT EXISTS idx_results_history
    ON validation_results(history_id);

-- AI 对话会话表
CREATE TABLE IF NOT EXISTS chat_sessions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    title       TEXT NOT NULL DEFAULT '新对话',
    context_rule_id TEXT NOT NULL DEFAULT ''
);

-- AI 对话消息表
CREATE TABLE IF NOT EXISTS chat_messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  INTEGER NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role        TEXT NOT NULL DEFAULT 'user',
    content     TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_messages_session
    ON chat_messages(session_id);

-- 规则容差覆写表
CREATE TABLE IF NOT EXISTS rule_overrides (
    rule_id   TEXT PRIMARY KEY,
    tolerance REAL NOT NULL
);
"""

# validation_results 表 v1.3.0 新增列迁移配置
# 按列名 -> (列定义, 中文日志名)
_RESULT_MIGRATION_COLUMNS: dict[str, tuple[str, str]] = {
    "skipped": ("skipped INTEGER NOT NULL DEFAULT 0", "跳过"),
    "category": ("category TEXT NOT NULL DEFAULT ''", "分类"),
    "trace": ("trace TEXT NOT NULL DEFAULT '[]'", "追溯"),
}

# validation_history 表 v0.4.1 新增审计证据链列迁移配置
_HISTORY_MIGRATION_COLUMNS: dict[str, tuple[str, str]] = {
    "source_files": ("source_files TEXT NOT NULL DEFAULT '[]'", "源文件"),
    "source_hashes": ("source_hashes TEXT NOT NULL DEFAULT '[]'", "源文件哈希"),
    "rule_version": ("rule_version TEXT NOT NULL DEFAULT ''", "规则版本"),
}


class Database:
    """SQLite 数据库连接管理器。

    使用 WAL 模式, 支持多线程访问 (GUI + worker)。
    """

    def __init__(self, db_path: Path | str | None = None) -> None:
        if db_path is None:
            self._path = _DEFAULT_DB_PATH
        else:
            self._path = Path(str(db_path))
        self._conn: sqlite3.Connection | None = None

    @property
    def path(self) -> Path:
        """数据库文件路径。"""
        return self._path

    @property
    def connection(self) -> sqlite3.Connection:
        """当前数据库连接 (未连接则报错)。"""
        if self._conn is None:
            raise RuntimeError("数据库未连接, 请先调用 connect()")
        return self._conn

    def connect(self) -> sqlite3.Connection:
        """连接数据库并配置 WAL 模式。

        Returns:
            已配置的 sqlite3.Connection

        Raises:
            sqlite3.OperationalError: 无法打开数据库文件
        """
        self._path.parent.mkdir(parents=True, exist_ok=True)
        logger.info(f"连接数据库: {self._path}")

        self._conn = sqlite3.connect(
            str(self._path),
            check_same_thread=False,
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA foreign_keys=ON")

        return self._conn

    def init_schema(self) -> None:
        """初始化数据库 schema (幂等操作)。

        对已存在的旧数据库，自动检测并迁移新增列 (v1.3.0+)。
        迁移使用 PRAGMA table_info 检测列是否存在，再 ALTER TABLE ADD COLUMN，
        确保旧数据不丢失。

        Raises:
            RuntimeError: 数据库未连接
        """
        if self._conn is None:
            raise RuntimeError("数据库未连接, 请先调用 connect()")
        self._conn.executescript(_SCHEMA_DDL)
        self._conn.commit()
        logger.info("数据库 schema 初始化完成")

        # 迁移: 为旧数据库补齐新增列
        self._migrate_columns("validation_results", _RESULT_MIGRATION_COLUMNS)
        self._migrate_columns("validation_history", _HISTORY_MIGRATION_COLUMNS)

    def _migrate_columns(
        self, table_name: str, columns: dict[str, tuple[str, str]]
    ) -> None:
        """检测并迁移指定表的新增列 (幂等)。"""
        if self._conn is None:
            return
        existing = {
            row[1] for row in
            self._conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        for col_name, (col_def, label) in columns.items():
            if col_name not in existing:
                self._conn.execute(
                    f"ALTER TABLE {table_name} ADD COLUMN {col_def}"
                )
                self._conn.commit()
                logger.info(f"数据库迁移: {table_name} 表新增「{label}」列")

    def close(self) -> None:
        """关闭数据库连接。"""
        if self._conn is not None:
            self._conn.close()
            self._conn = None
            logger.info("数据库连接已关闭")

    def __enter__(self) -> Database:
        self.connect()
        self.init_schema()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()
