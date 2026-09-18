"""导入页后台任务管理 (mixin)。

从 import_page 拆分的三条后台任务管线 (导入/校验/多主体批量) 的启动、
取消、代际守卫与信号桥逻辑 (纯移动, 不改行为)。由 ImportPage 继承。

线程约定: threading.Thread 后台执行 + QObject Signal 桥跨线程 emit,
自动排队到 GUI 线程 (见 gui/AGENTS.md 线程约定)。

B1-1 代际守卫: 三类后台任务各自独立的代际计数器。每次启动任务递增并捕获
当时的代际值, 完成回调应用结果前比对, 不等则丢弃 (用户在任务进行中点
「重置」/「取消」后, 旧结果不得写回 AppState)。

依赖宿主 ImportPage 提供的属性 (均在 __init__/_setup_ui 中初始化):
_state / _import_status_label / _progress / _cancel_import_btn /
_import_cancel_event / _import_bridge / _import_generation /
_validation_cancel_event / _validation_bridge / _validation_generation / _validation_running /
_multi_cancel_event / _multi_bridge / _multi_generation / _multi_running;
跨 mixin/宿主方法仅以 TYPE_CHECKING 契约声明 (运行时不存在, 不参与 MRO):
_import_paths / _run_validation / _run_multi_entity (宿主 import_page 纯管线),
_apply_import_result / _apply_validation_summary / _persist_multi_entity_results
(import_page_apply), _show_info (import_page_results)。
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, cast

from loguru import logger
from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QDialog, QLabel, QPushButton, QWidget
from qfluentwidgets import IndeterminateProgressBar

from fsa.core.models.detail import DetailDataset
from fsa.gui.app_state import AppState
from fsa.gui.widgets.import_file_list import ImportFileList

if TYPE_CHECKING:
    from fsa.core.models.report import Report


class _ImportBridge(QObject):
    """后台导入线程 -> GUI 线程的信号桥。"""

    finished = Signal(object)  # dict: reports / dataset / errors / file_count
    failed = Signal(str)
    progress = Signal(str)
    file_started = Signal(int, str)  # index, name
    file_completed = Signal(int)  # index
    file_failed = Signal(int, str)  # index, reason


class _ValidationBridge(QObject):
    """后台校验线程 -> GUI 线程的信号桥。"""

    finished = Signal(object)  # ValidationSummary
    failed = Signal(str)
    progress = Signal(str)


class _MultiEntityBridge(QObject):
    """多主体批量校验线程 -> GUI 线程的信号桥。"""

    finished = Signal(object)  # MultiEntityResult
    failed = Signal(str)
    progress = Signal(str)


class ImportPageTasksMixin(QWidget):
    """三条后台任务 (导入/校验/多主体批量) 的启动、取消与代际守卫 (继承 QWidget 以便作为信号桥 parent)。"""

    validate_enabled_changed: Signal

    # 进度反馈状态 (mixin 自有; 计时器惰性创建, 见 _ensure_progress_timer)
    _progress_base_text: str = ""
    _progress_started_at: float | None = None
    _progress_timer: QTimer | None = None
    # 最近一次多主体结果与落库数 (供「上次批量结果」按钮回看)
    _last_multi_result: object | None = None
    _last_multi_saved_count: int | None = None
    # 宿主 import_page._setup_ui 创建 (与 _import_status_label 等同批)
    _last_multi_btn: QPushButton

    _state: AppState
    _import_status_label: QLabel
    _file_list: ImportFileList
    _progress: IndeterminateProgressBar
    _cancel_import_btn: QPushButton
    _import_cancel_event: threading.Event | None
    _import_bridge: _ImportBridge | None
    _import_generation: int
    _validation_cancel_event: threading.Event | None
    _validation_bridge: _ValidationBridge | None
    _validation_generation: int
    _validation_running: bool
    _multi_cancel_event: threading.Event | None
    _multi_bridge: _MultiEntityBridge | None
    _multi_generation: int
    _multi_running: bool

    if TYPE_CHECKING:
        # 跨 mixin/宿主方法契约 (仅类型检查可见, 运行时不存在, 不占用 MRO)
        def _show_info(self, message: str, kind: str = "info") -> None: ...

        def _import_paths(
            self,
            file_paths: list[str],
            progress_cb: object | None = None,
            event_cb: Callable[[dict[str, object]], None] | None = None,
            cancel_event: threading.Event | None = None,
        ) -> tuple[list[Report], DetailDataset, list[str]]: ...

        def _apply_import_result(
            self,
            file_paths: list[str],
            reports: list[Report],
            dataset: DetailDataset,
            errors: list[str],
        ) -> None: ...

        def _run_validation(self, cancel_event: threading.Event | None = None) -> object | None: ...

        def _apply_validation_summary(self, summary: object) -> None: ...

        def _run_multi_entity(
            self,
            folders: list[str],
            cancel_event: threading.Event | None = None,
            progress_cb: Callable[[str], None] | None = None,
        ) -> object: ...

        def _persist_multi_entity_results(self, result: object) -> int: ...

    def _on_files_async(self, file_paths: list[str]) -> None:
        """后台导入入口: 不阻塞界面, 可取消。拖入后立即显示文件列表反馈。"""
        if self._import_cancel_event is not None:
            self._show_info("已有导入任务正在进行，请先取消或等待完成", "warning")
            return

        logger.info(f"导入文件(后台): {file_paths}")
        # 拖入即显: 用户能立刻看到拖入了哪些文件、共几个
        self._file_list.set_files(file_paths)
        self._set_import_running(True)
        cancel_event = threading.Event()
        self._import_cancel_event = cancel_event
        # B1-1: 捕获本次任务的代际值, 完成/失败回调比对后决定是否写回
        self._import_generation += 1
        generation = self._import_generation
        bridge = _ImportBridge(self)
        bridge.finished.connect(self._on_background_import_finished)
        bridge.failed.connect(
            lambda message, gen=generation: self._on_background_import_failed(message, gen)
        )
        bridge.progress.connect(self._set_progress_message)
        bridge.file_started.connect(self._on_file_started)
        bridge.file_completed.connect(self._on_file_completed)
        bridge.file_failed.connect(self._on_file_failed)
        self._import_bridge = bridge

        def run() -> None:
            try:
                reports, dataset, errors = self._import_paths(
                    file_paths,
                    progress_cb=bridge.progress.emit,
                    event_cb=lambda event: self._emit_file_event(bridge, event),
                    cancel_event=cancel_event,
                )
            except Exception as e:
                logger.exception("后台导入任务异常")
                bridge.failed.emit(str(e))
            else:
                bridge.finished.emit(
                    {
                        "generation": generation,
                        "file_paths": file_paths,
                        "reports": reports,
                        "dataset": dataset,
                        "errors": errors,
                    }
                )

        threading.Thread(target=run, daemon=True).start()

    def _retry_file_async(self, index: int, file_path: str) -> None:
        """单文件后台重试: 仅更新对应行, 不重置整个文件列表。"""
        if self._import_cancel_event is not None:
            self._show_info("已有导入任务正在进行，请先取消或等待完成", "warning")
            return

        logger.info(f"单文件重试: {file_path}")
        self._file_list.set_importing(index)
        self._set_import_running(True)
        cancel_event = threading.Event()
        self._import_cancel_event = cancel_event
        # B1-1: 捕获本次任务的代际值
        self._import_generation += 1
        generation = self._import_generation
        bridge = _ImportBridge(self)
        bridge.finished.connect(self._on_background_import_finished)
        bridge.failed.connect(
            lambda message, gen=generation: self._on_background_import_failed(message, gen)
        )
        bridge.progress.connect(self._set_progress_message)
        bridge.file_started.connect(self._on_file_started)
        bridge.file_completed.connect(self._on_file_completed)
        bridge.file_failed.connect(self._on_file_failed)
        self._import_bridge = bridge

        def run() -> None:
            try:
                reports, dataset, errors = self._import_paths(
                    [file_path],
                    event_cb=lambda event: self._emit_file_event(bridge, event),
                    cancel_event=cancel_event,
                )
            except Exception as e:
                logger.exception("单文件重试异常")
                bridge.failed.emit(str(e))
            else:
                bridge.finished.emit(
                    {
                        "generation": generation,
                        "file_paths": [file_path],
                        "reports": reports,
                        "dataset": dataset,
                        "errors": errors,
                    }
                )

        threading.Thread(target=run, daemon=True).start()

    def _emit_file_event(self, bridge: _ImportBridge, event: dict[str, object]) -> None:
        """在后台线程中将结构化文件事件转发到信号桥。"""
        kind = event.get("kind")
        index = cast(int, event.get("index", -1))
        if kind == "started":
            bridge.file_started.emit(index, str(event.get("name", "")))
        elif kind == "completed":
            bridge.file_completed.emit(index)
        elif kind == "failed":
            bridge.file_failed.emit(index, str(event.get("reason", "")))

    def _on_file_started(self, index: int, name: str) -> None:
        """单个文件开始导入 (GUI 线程)。"""
        _ = name
        self._file_list.set_importing(index)

    def _on_file_completed(self, index: int) -> None:
        """单个文件导入完成 (GUI 线程)。"""
        self._file_list.set_completed(index)

    def _on_file_failed(self, index: int, reason: str) -> None:
        """单个文件导入失败 (GUI 线程)。"""
        self._file_list.set_failed(index, reason)

    def _on_background_import_finished(self, payload: object) -> None:
        """后台导入完成 (queued 到 GUI 线程)。"""
        data = payload if isinstance(payload, dict) else {}
        self._set_import_running(False)
        generation = data.get("generation")
        if generation is not None and int(generation) != self._import_generation:
            # 任务进行中用户已重置/取消 (代际已推进): 丢弃迟到的旧结果
            logger.debug(f"丢弃过期的后台导入结果 (代际 {generation} != {self._import_generation})")
            return
        file_paths = list(data.get("file_paths", []))
        reports = list(data.get("reports", []))
        dataset = data.get("dataset", DetailDataset(period=self._state.period))
        errors = list(data.get("errors", []))
        self._apply_import_result(file_paths, reports, dataset, errors)

    def _on_background_import_failed(self, message: str, generation: int | None = None) -> None:
        """后台导入出现未预期异常。"""
        self._set_import_running(False)
        if generation is not None and generation != self._import_generation:
            logger.debug(f"丢弃过期的后台导入失败通知 (代际 {generation} != {self._import_generation})")
            return
        # 收尾文件列表: 未到终态的行标记失败, 否则永远停在「导入中」
        self._file_list.fail_all_pending(message)
        # 恢复顶栏校验按钮 (按既有数据判断), 批次失败不永久禁用入口
        has_data = bool(self._state.reports) or (
            self._state.detail_dataset is not None
            and not self._state.detail_dataset.is_empty
        )
        self.validate_enabled_changed.emit(has_data)
        self._show_info(f"导入失败: {message}", "error")

    def invalidate_background_tasks(self) -> None:
        """推进全部后台任务代际并请求取消 (重置/退出回看时调用)。

        已发出的完成回调会因代际不等被丢弃, 旧任务结果不会写回 AppState。
        """
        self._import_generation += 1
        self._validation_generation += 1
        self._multi_generation += 1
        self._cancel_import()

    def _cancel_import(self) -> None:
        """请求取消当前后台导入/校验/批量任务。"""
        # B1-1: 取消即推进代际, 已取消任务的迟到结果一律丢弃
        event = self._import_cancel_event
        if event is not None:
            self._import_generation += 1
            event.set()
            self._import_status_label.setText("正在取消…")
        validation_event = self._validation_cancel_event
        if validation_event is not None:
            self._validation_generation += 1
            validation_event.set()
            self._import_status_label.setText("正在取消校验…")
        multi_event = self._multi_cancel_event
        if multi_event is not None:
            self._multi_generation += 1
            multi_event.set()
            self._import_status_label.setText("正在取消批量校验…")

    def _set_import_running(self, running: bool) -> None:
        """切换导入进度/取消控件可见性。"""
        if not running:
            self._import_cancel_event = None
            self._import_bridge = None
        self._sync_progress_controls()

    def _set_validation_running(self, running: bool) -> None:
        """切换校验进度/取消控件可见性。"""
        self._validation_running = running
        if not running:
            self._validation_cancel_event = None
            self._validation_bridge = None
        # 校验期间禁用「开始校验」按钮, 防连点触发多条提示叠加
        self._file_list.set_validate_running(running)
        self._sync_progress_controls()

    def _set_multi_running(self, running: bool) -> None:
        """切换多主体批量校验进度/取消控件可见性。"""
        self._multi_running = running
        if not running:
            self._multi_cancel_event = None
            self._multi_bridge = None
        self._sync_progress_controls()

    def _sync_progress_controls(self) -> None:
        """按任一后台任务运行状态刷新进度控件 (含已用时长计时器)。"""
        running = self._import_cancel_event is not None or self._validation_running or self._multi_running
        self._progress.setVisible(running)
        self._cancel_import_btn.setVisible(running)
        self._import_status_label.setVisible(running)
        timer = self._ensure_progress_timer()
        if running:
            if self._progress_started_at is None:
                self._progress_started_at = time.monotonic()
            if not timer.isActive():
                timer.start()
        else:
            timer.stop()
            self._progress_started_at = None
            self._progress_base_text = ""
            self._import_status_label.setText("")

    def _set_progress_message(self, text: str) -> None:
        """记录进度消息并立即显示 (已用时长后缀由 1s 计时器持续刷新)。

        大文件 (如 72MB 计提表) 单次 COM 读取可达 50s+, 若状态栏只在
        消息到达时更新, 用户会长时间盯着静止文本误以为卡死; 计时器每秒
        刷新「已用 X 秒」后缀, 提供持续活动反馈 (2026-09-18 用户反馈)。
        """
        self._progress_base_text = text
        if self._progress_started_at is None:
            self._progress_started_at = time.monotonic()
        self._refresh_progress_elapsed()

    def _refresh_progress_elapsed(self) -> None:
        """刷新状态栏文本: 基础消息 + 已用时长。"""
        base = self._progress_base_text
        if not base or self._progress_started_at is None:
            self._import_status_label.setText(base)
            return
        elapsed = int(time.monotonic() - self._progress_started_at)
        suffix = (
            f"已用 {elapsed} 秒"
            if elapsed < 60
            else f"已用 {elapsed // 60} 分 {elapsed % 60} 秒"
        )
        self._import_status_label.setText(f"{base}（{suffix}）")

    def _ensure_progress_timer(self) -> QTimer:
        """惰性创建 1s 进度计时器。"""
        timer = self._progress_timer
        if timer is None:
            timer = QTimer(self)
            timer.setInterval(1000)
            timer.timeout.connect(self._refresh_progress_elapsed)
            self._progress_timer = timer
        return timer

    def _on_view_last_multi_result(self) -> None:
        """重新打开最近一次多主体批量校验结果 (关闭对话框后仍可回看)。"""
        result = self._last_multi_result
        if result is None:
            self._show_info("还没有多主体批量校验结果", "warning")
            return
        from fsa.gui.widgets.multi_entity_dialog import MultiEntityResultDialog
        from fsa.services.multi_entity_service import MultiEntityResult

        if not isinstance(result, MultiEntityResult):
            return
        dialog = MultiEntityResultDialog(
            result, self, saved_count=self._last_multi_saved_count
        )
        dialog.show()

    def trigger_validate_async(self) -> None:
        """后台校验入口: 不阻塞界面, 可取消。"""
        if self._validation_running:
            self._show_info("已有校验任务正在进行", "warning")
            return
        registry = self._state.registry
        if registry is None:
            self._show_info("规则库未加载，请检查规则文件", "error")
            return
        dataset = self._state.detail_dataset
        if not self._state.reports and dataset is None:
            self._show_info("请先导入报表", "warning")
            return

        self._set_validation_running(True)
        cancel_event = threading.Event()
        self._validation_cancel_event = cancel_event
        # B1-1: 捕获本次任务的代际值
        self._validation_generation += 1
        generation = self._validation_generation
        bridge = _ValidationBridge(self)
        bridge.finished.connect(
            lambda payload, gen=generation: self._on_background_validation_finished(payload, gen)
        )
        bridge.failed.connect(
            lambda message, gen=generation: self._on_background_validation_failed(message, gen)
        )
        bridge.progress.connect(self._set_progress_message)
        self._validation_bridge = bridge

        def run() -> None:
            try:
                summary = self._run_validation(cancel_event)
            except Exception as e:
                logger.exception("后台校验任务异常")
                bridge.failed.emit(str(e))
            else:
                if summary is None:
                    bridge.failed.emit("校验已取消或无可校验数据")
                else:
                    bridge.finished.emit(summary)

        threading.Thread(target=run, daemon=True).start()

    def _on_background_validation_finished(self, payload: object, generation: int | None = None) -> None:
        """后台校验完成 (queued 到 GUI 线程)。"""
        self._set_validation_running(False)
        if generation is not None and generation != self._validation_generation:
            # 重置/取消后迟到的旧结果: 丢弃, 不写回 AppState
            logger.debug(f"丢弃过期的后台校验结果 (代际 {generation} != {self._validation_generation})")
            return
        self._apply_validation_summary(payload)

    def _on_background_validation_failed(self, message: str, generation: int | None = None) -> None:
        """后台校验异常。"""
        self._set_validation_running(False)
        if generation is not None and generation != self._validation_generation:
            logger.debug(f"丢弃过期的后台校验失败通知 (代际 {generation} != {self._validation_generation})")
            return
        self._show_info(f"校验失败: {message}", "error")

    def _pick_entities_for_multi(self, root: str) -> list[str] | None:
        """列出 root 下子文件夹并弹出勾选对话框，返回选中主体的完整路径列表。"""
        root_path = Path(root)
        names = sorted(path.name for path in root_path.iterdir() if path.is_dir())
        if not names:
            self._show_info("所选目录下没有主体子文件夹", "warning")
            return None

        from fsa.services.entity_config import load_default_entity_configs

        configs = load_default_entity_configs()
        descriptions = {
            name: configs[name].aliases[0]
            for name in names
            if name in configs and configs[name].aliases
        }

        from fsa.gui.widgets.entity_select_dialog import EntitySelectDialog

        dialog = EntitySelectDialog(names, descriptions, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        selected = dialog.selected_entities()
        if not selected:
            return None
        return [str(root_path / name) for name in selected]

    def _on_multi_entity_clicked(self) -> None:
        """选择根目录, 勾选主体后将选中的子文件夹批量校验。"""
        from PySide6.QtWidgets import QFileDialog

        root = QFileDialog.getExistingDirectory(self, "选择多主体根目录（每个子文件夹一个主体）")
        if not root:
            return
        if self._multi_running:
            self._show_info("已有批量校验任务正在进行", "warning")
            return
        folders = self._pick_entities_for_multi(root)
        if not folders:
            return

        self._set_multi_running(True)
        cancel_event = threading.Event()
        self._multi_cancel_event = cancel_event
        # B1-1: 捕获本次任务的代际值
        self._multi_generation += 1
        generation = self._multi_generation
        bridge = _MultiEntityBridge(self)
        bridge.finished.connect(
            lambda payload, gen=generation: self._on_multi_entity_finished(payload, gen)
        )
        bridge.failed.connect(
            lambda message, gen=generation: self._on_multi_entity_failed(message, gen)
        )
        bridge.progress.connect(self._set_progress_message)
        self._multi_bridge = bridge

        def run() -> None:
            try:
                result = self._run_multi_entity(
                    folders, cancel_event, progress_cb=bridge.progress.emit
                )
            except Exception as e:
                logger.exception("后台多主体批量校验任务异常")
                bridge.failed.emit(str(e))
            else:
                bridge.finished.emit(result)

        threading.Thread(target=run, daemon=True).start()

    def _on_multi_entity_finished(self, payload: object, generation: int | None = None) -> None:
        """多主体校验完成: 落库各主体结果并展示结果对话框（非模态）。"""
        self._set_multi_running(False)
        if generation is not None and generation != self._multi_generation:
            # 重置/取消后迟到的旧结果: 丢弃, 不落库不弹窗
            logger.debug(f"丢弃过期的多主体批量校验结果 (代际 {generation} != {self._multi_generation})")
            return
        from fsa.gui.widgets.multi_entity_dialog import MultiEntityResultDialog
        from fsa.services.multi_entity_service import MultiEntityResult

        if not isinstance(payload, MultiEntityResult):
            self._show_info("批量校验结果无效，请重试", "error")
            return
        saved_count = self._persist_multi_entity_results(payload)
        # 保留最近一次结果供「上次批量结果」按钮回看 (历史按主体分散保存)
        self._last_multi_result = payload
        self._last_multi_saved_count = saved_count
        self._last_multi_btn.setVisible(True)
        dialog = MultiEntityResultDialog(payload, self, saved_count=saved_count)
        dialog.show()

    def _on_multi_entity_failed(self, message: str, generation: int | None = None) -> None:
        """多主体校验异常。"""
        self._set_multi_running(False)
        if generation is not None and generation != self._multi_generation:
            logger.debug(f"丢弃过期的多主体批量校验失败通知 (代际 {generation} != {self._multi_generation})")
            return
        self._show_info(f"批量校验失败: {message}", "error")
