"""应用共享状态: 报表、校验结果、规则注册表、持久化。

AppState 通过 Qt 信号通知 UI 更新, 避免页面间直接耦合。
规则注册表从项目根目录的 JSON 文件加载。
校验结果自动持久化到 SQLite (通过 HistoryRepo)。
"""

from __future__ import annotations

import json
import sqlite3

from loguru import logger
from PySide6.QtCore import QObject, Signal

from fsa.core.engine.registry import RuleRegistry
from fsa.core.models.detail import DetailDataset
from fsa.core.models.report import Report
from fsa.core.models.result import ValidationSummary
from fsa.core.resources import resource_path
from fsa.storage.chat_repo import ChatRepo
from fsa.storage.database import Database
from fsa.storage.history_repo import HistoryRepo
from fsa.storage.override_repo import RuleOverrideRepo

_RULES_FILE = resource_path("cas_gouji_rule_library.json")


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
        self._detail_dataset: DetailDataset | None = None
        self._results: ValidationSummary | None = None
        self._registry: RuleRegistry | None = None
        self._period: str = ""

        # 持久化层
        self._db = Database()
        self._history_repo: HistoryRepo | None = None
        self._chat_repo: ChatRepo | None = None
        self._override_repo: RuleOverrideRepo | None = None
        self._init_storage()

    def _init_storage(self) -> None:
        """初始化 SQLite 持久化, 失败时降级为无持久化模式。"""
        try:
            self._db.connect()
            self._db.init_schema()
            self._history_repo = HistoryRepo(self._db)
            self._chat_repo = ChatRepo(self._db)
            self._override_repo = RuleOverrideRepo(self._db)
            logger.info("SQLite 持久化初始化成功")
            self._cleanup_history()
        except sqlite3.OperationalError as e:
            logger.error(f"数据库初始化失败, 降级为无持久化模式: {e}")
            self._history_repo = None
            self._chat_repo = None
            self._override_repo = None

    @property
    def history_repo(self) -> HistoryRepo | None:
        return self._history_repo

    @property
    def chat_repo(self) -> ChatRepo | None:
        return self._chat_repo

    @property
    def override_repo(self) -> RuleOverrideRepo | None:
        return self._override_repo

    @property
    def reports(self) -> list[Report]:
        return self._reports

    @property
    def detail_dataset(self) -> DetailDataset | None:
        return self._detail_dataset

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

    def set_default_tolerance(self, tolerance: float) -> None:
        """设置默认容差 (供设置页写入)。"""
        self._default_tolerance = tolerance

    @property
    def default_tolerance(self) -> float:
        """当前默认容差。"""
        return getattr(self, "_default_tolerance", 0.01)

    def set_reports(self, reports: list[Report]) -> None:
        self._reports = reports
        self.reports_changed.emit()

    def set_detail_dataset(self, dataset: DetailDataset | None) -> None:
        """设置明细数据集（附表 2~6 合并结果）。"""
        self._detail_dataset = dataset

    def set_results(self, results: ValidationSummary, persist: bool = True) -> None:
        """设置校验结果并可选持久化到 SQLite。

        查看历史记录时传 persist=False，避免重复保存产生新历史条目。
        持久化失败不影响内存中的结果, 仅记录日志。
        """
        self._results = results
        if persist:
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
        self._detail_dataset = None
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
            self._merge_custom_rules()
            count = self._registry.count()
            logger.info(f"加载规则库: {count} 条规则")
            self._apply_overrides()
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

    def _apply_overrides(self) -> None:
        """将 SQLite 中保存的容差覆写应用到规则注册表。"""
        if self._override_repo is None or self._registry is None:
            return
        overrides = self._override_repo.get_all()
        if not overrides:
            return
        count = 0
        for rule_id, tolerance in overrides.items():
            if self._registry.set_tolerance(rule_id, tolerance):
                count += 1
        if count > 0:
            logger.info(f"已应用 {count} 条容差覆写")

    def _merge_custom_rules(self) -> None:
        """合并自定义规则到注册表 (在内置规则加载后调用)。"""
        if self._registry is None:
            return
        from fsa.core.engine.custom_rules import load_custom_rules
        count = 0
        for rule in load_custom_rules():
            if self._registry.add_rule(rule, custom=True):
                count += 1
        if count > 0:
            logger.info(f"合并自定义规则: {count} 条")

    def _cleanup_history(self) -> None:
        """根据设置中的保留天数清理过期校验历史。"""
        if self._history_repo is None:
            return
        try:
            from PySide6.QtCore import QSettings
            settings = QSettings("FSA", "FinancialAudit")
            days_str = str(settings.value("history_retention_days", "90"))
            days = int(days_str)
        except (ValueError, TypeError):
            days = 90
        if days <= 0:
            return
        try:
            deleted = self._history_repo.delete_older_than(days)
            if deleted > 0:
                logger.info(f"启动时清理过期历史记录: {deleted} 条")
        except sqlite3.OperationalError as e:
            logger.error(f"清理过期历史记录失败: {e}")
        except RuntimeError as e:
            logger.error(f"清理过期历史记录失败: {e}")

    def close(self) -> None:
        """关闭数据库连接, 应在应用退出时调用。"""
        self._db.close()
        logger.info("AppState 已关闭, 数据库连接已释放")
