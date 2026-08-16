"""导入页结果应用与消息组装 (mixin)。

从 import_page 拆分的导入/校验结果写回 AppState、中文反馈消息组装与
多主体结果落库逻辑 (纯移动, 不改行为)。由 ImportPage 继承。

依赖宿主 ImportPage 提供的属性 (均在 __init__/_setup_ui 中初始化):
_state / _retry_failed_btn / _retry_failed_paths 及 validate_enabled_changed 信号;
跨 mixin 方法仅以 TYPE_CHECKING 契约声明 (运行时不存在, 不参与 MRO):
_on_files_async (import_page_tasks), _show_info (import_page_results)。
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QPushButton, QWidget

from fsa.core.models.detail import DetailDataset
from fsa.core.models.report import Report
from fsa.gui.app_state import AppState


def _format_import_failure(errors: list[str], failed_paths: list[str]) -> str:
    """组装导入失败提示: 数量 + 文件名清单, 详情指向日志 (避免长路径/异常栈刷屏)。

    文件名取自已识别的失败路径 (最多列 3 个, 超出以"等 N 个文件"概括);
    无法识别文件名时仅给数量。
    """
    names = [Path(path).name for path in failed_paths]
    if not names:
        return f"{len(errors)} 个文件导入失败（详情见日志）"
    shown = "、".join(names[:3])
    if len(names) > 3:
        shown += f" 等 {len(names)} 个文件"
    return f"{len(errors)} 个文件导入失败：{shown}（详情见日志）"


class ImportPageApplyMixin(QWidget):
    """导入/校验结果应用与中文反馈消息组装 (继承 QWidget 以便访问 QWidget 方法)。"""

    validate_enabled_changed: Signal

    _state: AppState
    _retry_failed_btn: QPushButton
    _retry_failed_paths: list[str]

    if TYPE_CHECKING:
        # 跨 mixin 方法契约 (仅类型检查可见, 运行时不存在, 不占用 MRO)
        def _show_info(self, message: str, kind: str = "info") -> None: ...

        def _on_files_async(self, file_paths: list[str]) -> None: ...

    def _apply_import_result(
        self,
        file_paths: list[str],
        reports: list[Report],
        dataset: DetailDataset,
        errors: list[str],
    ) -> None:
        """将导入结果写回 AppState 并给出中文反馈 (仅 GUI 线程调用)。"""
        failed_paths = [path for path in file_paths if any(str(err).startswith(f"{path}:") for err in errors)]
        self._retry_failed_paths = failed_paths
        self._retry_failed_btn.setVisible(bool(failed_paths))
        if failed_paths:
            self._retry_failed_btn.setToolTip("重试: " + "\n".join(failed_paths))

        if not reports and dataset.is_empty:
            if errors:
                self._show_info(_format_import_failure(errors, failed_paths), "warning")
            else:
                self._show_info("未识别到任何财务报表或明细数据", "warning")
            self.validate_enabled_changed.emit(False)
            return

        self._state.set_reports(reports)
        self._state.set_detail_dataset(dataset)
        # 新批次导入成功后旧校验结果已失效 (B1-2): 清空, 防止旧底稿被误导出
        self._state.set_results(None)
        detail_rows = (
            len(dataset.trial_balance)
            + len(dataset.trial_balance_current)
            + len(dataset.journal)
            + len(dataset.journal_current)
            + len(dataset.cash_flow_detail)
            + len(dataset.cash_flow_detail_current)
            + len(dataset.reclassifications)
            + len(dataset.related_party_purchases)
            + len(dataset.sales_details)
            + len(dataset.internal_cash_flows)
        )
        succeeded = len(file_paths) - len(errors)
        message = f"成功导入 {succeeded} 个文件：{len(reports)} 张报表、{detail_rows} 行明细数据"
        unit_warnings = [f"{r.report_type.value}: {r.unit_warning}" for r in reports if r.unit_warning]
        unit_warnings.extend(dataset.unit_warnings)
        if unit_warnings:
            message += f"；金额单位提示: {'; '.join(unit_warnings)}"

        # A-P3-06: 未映射科目可见性 —— 追加提示但不打断主提示
        unmapped_count = sum(len(r.unmapped_names) for r in reports)
        if unmapped_count > 0:
            message += f"；{unmapped_count} 个有金额项目未映射为标准科目（可通过 AI 助手查询清单）"

        pdf_diagnostics = list(dict.fromkeys(r.parse_diagnostics for r in reports if r.parse_diagnostics))
        if pdf_diagnostics:
            message += "；PDF 为只读扫描识别，建议优先使用 Excel"
            message += f"；解析诊断: {'; '.join(pdf_diagnostics)}"

        if errors or unit_warnings or pdf_diagnostics:
            if errors:
                message += f"；{_format_import_failure(errors, failed_paths)}"
            self._show_info(message, "warning")
        else:
            self._show_info(message, "success")
        self.validate_enabled_changed.emit(bool(reports) or detail_rows > 0)

    def _on_retry_failed(self) -> None:
        """重试上次导入失败的文件 (单文件失败后继续的闭环)。"""
        failed = list(getattr(self, "_retry_failed_paths", []))
        if not failed:
            return
        self._retry_failed_btn.setVisible(False)
        self._retry_failed_paths = []
        self._on_files_async(failed)

    def _apply_validation_summary(self, summary: object) -> None:
        """将校验结果写回 AppState 并提示 (仅 GUI 线程调用)。"""
        from fsa.core.models.result import ValidationSummary

        if not isinstance(summary, ValidationSummary):
            self._show_info("校验结果无效，请重试", "error")
            return
        self._state.set_results(summary)
        kind = "success" if summary.all_passed else "warning"
        self._show_info(
            f"校验完成: 通过 {summary.passed}, 不通过 {summary.failed}",
            kind,
        )

    def _persist_multi_entity_results(self, result: object) -> int:
        """B1-5: 将每个主体的校验汇总写入历史记录, 返回成功保存的主体数。

        source_files 带主体目录标识以便在历史中区分; 单个主体保存失败
        只记录日志, 不中断其余主体落库与结果展示。
        """
        from fsa.services.multi_entity_service import MultiEntityResult

        if not isinstance(result, MultiEntityResult):
            return 0
        repo = self._state.history_repo
        if repo is None:
            logger.warning("历史存储不可用，多主体批量校验结果未保存")
            return 0
        saved = 0
        for outcome in result.outcomes:
            summary = outcome.summary
            if summary is None:
                continue
            if not summary.period:
                summary.period = self._state.period
            if not summary.source_files:
                summary.source_files = [f"[主体:{outcome.entity_id}] {outcome.folder}"]
            try:
                repo.save(summary)
            except (sqlite3.DatabaseError, RuntimeError) as e:
                logger.error(f"主体「{outcome.entity_id}」校验结果保存历史失败: {e}")
                continue
            saved += 1
        if saved:
            self._state.history_changed.emit()
        return saved
