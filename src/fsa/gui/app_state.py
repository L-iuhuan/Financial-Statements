"""应用共享状态: 报表、校验结果、规则注册表。

AppState 通过 Qt 信号通知 UI 更新, 避免页面间直接耦合。
规则注册表从项目根目录的 JSON 文件加载。
"""

from __future__ import annotations

import json
from pathlib import Path

from loguru import logger
from PySide6.QtCore import QObject, Signal

from fsa.core.engine.registry import RuleRegistry
from fsa.core.models.report import Report
from fsa.core.models.result import ValidationSummary

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_RULES_FILE = _PROJECT_ROOT / "cas_gouji_rule_library.json"


class AppState(QObject):
    """应用全局状态, 通过信号通知 UI 更新。

    Attributes:
        reports: 当前导入的报表列表
        results: 最近一次校验的汇总结果
        registry: 规则注册表 (从 JSON 加载)
        period: 报告期间, 如 "2024-12"
    """

    reports_changed = Signal()
    results_changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._reports: list[Report] = []
        self._results: ValidationSummary | None = None
        self._registry: RuleRegistry | None = None
        self._period: str = ""

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
        self._results = results
        self.results_changed.emit()

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
