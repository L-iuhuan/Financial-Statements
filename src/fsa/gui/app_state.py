"""应用共享状态: 报表、校验结果、规则注册表、持久化。

AppState 通过 Qt 信号通知 UI 更新, 避免页面间直接耦合。
规则注册表从项目根目录的 JSON 文件加载。
校验结果自动持久化到 SQLite (通过 HistoryRepo)。
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from loguru import logger
from PySide6.QtCore import QObject, Signal

from fsa.core.engine.registry import RuleRegistry
from fsa.core.models.report import Report
from fsa.core.models.result import ValidationSummary
from fsa.storage.chat_repo import ChatRepo
from fsa.storage.database import Database
from fsa.storage.history_repo import HistoryRepo

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_RULES_FILE = _PROJECT_ROOT / "cas_gouji_rule_library.json"


class AppState(QObject):
    """应用全局状态, 通过信号通知 UI 更新。

    Attributes:
        reports: 当前导入的报表列表
        results: 最近一次校验的汇总结果
        registry: 规则注册表 (从 JSON 加载)
        period: 报告期间, 如 "2024-12"
        history_repo: 校验历史仓库 (SQLite)
        chat_repo: AI 对话仓库 (SQLite)
    """

    reports_changed = Signal()
    results_changed = Signal()
    history_changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._reports: list[Report] = []
        self._results: ValidationSummary | None = None
        self._registry: RuleRegistry | None = None
        self._period: str = ""

        # 持久化层
        self._db = Database()
        self._history_repo: HistoryRepo | None = None
        self._chat_repo: ChatRepo | None = None
        self._init_storage()

    def _init_storage(self) -> None:
        """初始化 SQLite 持久化, 失败时降级为无持久化模式。"""
        try:
            self._db.connect()
            self._db.init_schema()
            self._history_repo = HistoryRepo(self._db)
            self._chat_repo = ChatRepo(self._db)
            logger.info("SQLite 持久化初始化成功")
        except sqlite3.OperationalError as e:
            logger.error(f"数据库初始化失败, 降级为无持久化模式: {e}")
            self._history_repo = None
            self._chat_repo = None

    @property
    def history_repo(self) -> HistoryRepo | None:
        return self._history_repo

    @property
    def chat_repo(self) -> ChatRepo | None:
        return self._chat_repo

    @property
    def reports(self) -> list[Report]:
        return self._reports

    @property
    def results(self) -> ValidationSummary | None:
        return self._results

    @property
    def registry(self) -> RuleRegistry | None:
        return self._registry

    @property
    def period(self) -> str:
        return self._period

    def set_period(self, period: str) -> None:
        self._period = period

    def set_reports(self, reports: list[Report]) -> None:
        self._reports = reports
        self.reports_changed.emit()

    def set_results(self, results: ValidationSummary) -> None:
        """设置校验结果并自动持久化到 SQLite。

        持久化失败不影响内存中的结果, 仅记录日志。
        """
        self._results = results
        self._persist_results(results)
        self.results_changed.emit()

    def _persist_results(self, results: ValidationSummary) -> None:
        """将校验结果保存到 SQLite (如果可用)。"""
        if self._history_repo is None:
            return
        try:
            self._history_repo.save(results)
            self.history_changed.emit()
        except sqlite3.OperationalError as e:
            logger.error(f"保存校验历史失败: {e}")
        except RuntimeError as e:
            logger.error(f"保存校验历史失败: {e}")

    def clear_all(self) -> None:
        """清空报表和结果。"""
        self._reports = []
        self._results = None
        self.reports_changed.emit()
        self.results_changed.emit()

    def load_registry(self) -> tuple[bool, str]:
        """从 JSON 文件加载规则注册表。

        Returns:
            (是否成功, 消息)
        """
        try:
            self._registry = RuleRegistry.from_json(str(_RULES_FILE))
            count = self._registry.count()
            logger.info(f"加载规则库: {count} 条规则")
            return True, f"成功加载 {count} 条规则"
        except FileNotFoundError:
            msg = f"规则库文件不存在: {_RULES_FILE.name}"
            logger.error(msg)
            return False, msg
        except json.JSONDecodeError as e:
            msg = f"规则库 JSON 格式错误: {e}"
            logger.error(msg)
            return False, msg
        except KeyError as e:
            msg = f"规则库缺少必需字段: {e}"
            logger.error(msg)
            return False, msg
        except ValueError as e:
            msg = f"规则库字段值无效: {e}"
            logger.error(msg)
            return False, msg

    def close(self) -> None:
        """关闭数据库连接, 应在应用退出时调用。"""
        self._db.close()
        logger.info("AppState 已关闭, 数据库连接已释放")
