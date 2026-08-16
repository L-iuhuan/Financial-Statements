"""数据导入与校验页面。

用户在此页面导入 Excel 文件并执行勾稽校验,
校验结果以卡片形式直接显示在本页面。

匹配 Demo v4 设计: 拖放区 + 报表卡片 + 汇总卡片 + 筛选标签 + 规则明细卡片。

拆分结构 (纯移动, 不改行为):
- 结果卡片渲染与筛选: import_page_results.py (ImportPageResultsMixin)
- 后台任务启动/取消/代际守卫/信号桥: import_page_tasks.py (ImportPageTasksMixin)
- 导入/校验结果应用与多主体落库: import_page_apply.py (ImportPageApplyMixin)

本模块保留: 类壳 + UI 构建 + 信号接线 + 纯数据管线
(_import_paths / _run_validation / _run_multi_entity)。
注意: 测试经 fsa.gui.pages.import_page 模块级 monkeypatch read_excel /
sha256_file, 故引用这两个名字的管线不可外移。
"""

from __future__ import annotations

import threading
from pathlib import Path

from loguru import logger
from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import FluentIcon, IconWidget, IndeterminateProgressBar

from fsa.core.exceptions import FSAError
from fsa.core.importer.detail_importer import DetailImporter
from fsa.core.importer.excel_reader import read_excel
from fsa.core.importer.importer import ImportService
from fsa.core.models.detail import DetailDataset
from fsa.core.models.report import Report, ReportType
from fsa.core.models.result import ValidationResult
from fsa.core.resources import sha256_file
from fsa.gui.app_state import AppState
from fsa.gui.pages.import_page_apply import ImportPageApplyMixin
from fsa.gui.pages.import_page_results import ImportPageResultsMixin
from fsa.gui.pages.import_page_tasks import (
    ImportPageTasksMixin,
    _ImportBridge,
    _MultiEntityBridge,
    _ValidationBridge,
)
from fsa.gui.widgets.drop_zone import DropZone
from fsa.gui.widgets.period_picker import PeriodPicker
from fsa.gui.widgets.result_card import ResultCard
from fsa.gui.widgets.summary_card import SummaryCard
from fsa.services.package_service import PackageValidationService


class ImportPage(ImportPageTasksMixin, ImportPageApplyMixin, ImportPageResultsMixin):
    """数据导入与校验页面 (继承 mixin 提供后台任务/结果应用/结果卡片渲染与筛选逻辑)。"""

    validate_enabled_changed = Signal(bool)
    diagnose_requested = Signal(str)  # rule_id -> 主窗口打开 AI 抽屉
    debate_requested = Signal(str)  # rule_id -> 主窗口打开深度辩论
    history_view_exit_requested = Signal()

    def __init__(self, state: AppState) -> None:
        super().__init__()
        self.setObjectName("ImportPage")
        self._state = state
        self._importer = ImportService()
        self._detail_importer = DetailImporter()
        self._current_filter = "all"
        self._result_cards: list[tuple[ValidationResult, ResultCard]] = []
        self._import_cancel_event: threading.Event | None = None
        self._import_bridge: _ImportBridge | None = None
        self._validation_cancel_event: threading.Event | None = None
        self._validation_bridge: _ValidationBridge | None = None
        self._validation_running = False
        self._multi_cancel_event: threading.Event | None = None
        self._multi_bridge: _MultiEntityBridge | None = None
        self._multi_running = False
        # B1-1 代际守卫: 三类后台任务各自独立的代际计数器。
        # 每次启动任务递增并捕获当时的代际值, 完成回调应用结果前比对,
        # 不等则丢弃 (用户在任务进行中点「重置」/「取消」后, 旧结果不得写回 AppState)。
        self._import_generation = 0
        self._validation_generation = 0
        self._multi_generation = 0
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        scroll = QScrollArea()
        self._scroll = scroll
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        content.setObjectName("PageContent")
        layout = QVBoxLayout(content)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # 报告期间 (校验结果/历史记录/导出底稿都会使用)
        period_row = QHBoxLayout()
        period_row.setSpacing(8)
        period_label = QLabel("报告期间")
        period_label.setObjectName("PageTitle")
        period_label.setStyleSheet("font-size: 13px;")
        period_row.addWidget(period_label)
        self._period_input = PeriodPicker(QDate.currentDate())
        self._period_input.setObjectName("StyledDateEdit")
        self._period_input.setFixedWidth(130)
        self._period_input.setToolTip("选择报告期间；该期间将写入导入报表、校验历史与导出底稿，历史回看时只读")
        self._period_input.dateChanged.connect(self._on_period_changed)
        period_row.addWidget(self._period_input)
        self._on_period_changed(self._period_input.date())
        self._multi_entity_btn = QPushButton("多主体批量校验")
        self._multi_entity_btn.setObjectName("BtnSecondary")
        self._multi_entity_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._multi_entity_btn.setFixedHeight(32)
        self._multi_entity_btn.setToolTip("选择包含多个主体文件夹的目录，每个子文件夹按一个主体批量校验")
        self._multi_entity_btn.clicked.connect(self._on_multi_entity_clicked)
        period_row.addWidget(self._multi_entity_btn)
        period_row.addStretch()
        layout.addLayout(period_row)

        # 拖放区
        self._drop_zone = DropZone()
        layout.addWidget(self._drop_zone)

        # 历史回看横幅 (默认隐藏, 仅在查看历史结果时显示)
        self._history_banner = QFrame()
        self._history_banner.setObjectName("HistoryViewBanner")
        self._history_banner.setVisible(False)
        banner_layout = QHBoxLayout(self._history_banner)
        banner_layout.setContentsMargins(12, 8, 12, 8)
        self._history_banner_text = QLabel()
        self._history_banner_text.setObjectName("HistoryViewBannerText")
        self._history_banner_text.setWordWrap(True)
        banner_layout.addWidget(self._history_banner_text, stretch=1)
        exit_btn = QPushButton("退出回看")
        exit_btn.setObjectName("TextBtn")
        exit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        exit_btn.clicked.connect(self.history_view_exit_requested.emit)
        banner_layout.addWidget(exit_btn)
        layout.addWidget(self._history_banner)

        # 已导入报表区域 (默认隐藏)
        self._reports_section = QFrame()
        self._reports_section.setVisible(False)
        reports_layout = QVBoxLayout(self._reports_section)
        reports_layout.setSpacing(8)

        reports_title = QLabel("已导入报表")
        reports_title.setObjectName("PageTitle")
        reports_layout.addWidget(reports_title)

        self._cards_grid = QGridLayout()
        self._cards_grid.setSpacing(12)
        reports_layout.addLayout(self._cards_grid)
        layout.addWidget(self._reports_section)

        # 校验概览 (汇总卡片)
        self._summary_section = QFrame()
        self._summary_section.setVisible(False)
        summary_layout = QVBoxLayout(self._summary_section)
        summary_layout.setSpacing(12)

        summary_title = QLabel("校验概览")
        summary_title.setObjectName("PageTitle")
        summary_layout.addWidget(summary_title)

        # 4 列汇总卡片
        cards_row = QHBoxLayout()
        cards_row.setSpacing(12)
        self._card_pass = SummaryCard("success")
        self._card_error = SummaryCard("error")
        self._card_warn = SummaryCard("warning")
        self._card_total = SummaryCard("info")
        for card in [self._card_pass, self._card_error, self._card_warn, self._card_total]:
            cards_row.addWidget(card)
        summary_layout.addLayout(cards_row)
        layout.addWidget(self._summary_section)

        # 筛选标签栏
        self._filter_section = QFrame()
        self._filter_section.setVisible(False)
        filter_layout = QHBoxLayout(self._filter_section)
        filter_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.setSpacing(8)

        self._filter_buttons: dict[str, QPushButton] = {}
        for key, label in [
            ("all", "全部"),
            ("error", "错误"),
            ("warning", "警告"),
            ("pass", "通过"),
        ]:
            btn = QPushButton(f"{label} (0)")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(30)
            btn.setObjectName("FilterTab")
            btn.clicked.connect(lambda checked, k=key: self._on_filter(k))
            self._filter_buttons[key] = btn
            filter_layout.addWidget(btn)

        filter_layout.addStretch()
        layout.addWidget(self._filter_section)

        # 校验明细
        self._detail_section = QFrame()
        self._detail_section.setVisible(False)
        detail_layout = QVBoxLayout(self._detail_section)
        detail_layout.setSpacing(12)

        detail_title = QLabel("校验明细")
        detail_title.setObjectName("PageTitle")
        detail_layout.addWidget(detail_title)

        self._cards_layout = QVBoxLayout()
        self._cards_layout.setSpacing(8)
        detail_layout.addLayout(self._cards_layout)
        layout.addWidget(self._detail_section)

        # 空状态 (已移除展示: 首页只保留一个明确的文件选择/拖放区)
        self._empty_state = QFrame()
        self._empty_state.setObjectName("EmptyContainer")
        self._empty_state.setVisible(False)
        empty_layout = QVBoxLayout(self._empty_state)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.setSpacing(8)

        # IconWidget: 主题同步图标 (QLabel+pixmap 烘焙颜色, 切主题后不刷新)
        empty_icon = IconWidget(FluentIcon.INFO)
        empty_icon.setFixedSize(48, 48)
        empty_layout.addWidget(empty_icon, alignment=Qt.AlignmentFlag.AlignCenter)

        empty_text = QLabel("等待导入财务报表")
        empty_text.setObjectName("EmptyTitle")
        empty_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(empty_text)

        empty_hint = QLabel("可一次拖入主表与附表（1~6），点击「执行校验」开始勾稽校验")
        empty_hint.setObjectName("MetaLabel")
        empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(empty_hint)

        layout.addWidget(self._empty_state)

        # 进度指示 (后台导入期间显示, 带取消按钮)
        progress_row = QHBoxLayout()
        progress_row.setSpacing(8)
        self._progress = IndeterminateProgressBar()
        self._progress.setVisible(False)
        progress_row.addWidget(self._progress, stretch=1)
        self._import_status_label = QLabel("")
        self._import_status_label.setObjectName("MetaLabel")
        self._import_status_label.setVisible(False)
        progress_row.addWidget(self._import_status_label)
        self._cancel_import_btn = QPushButton("取消导入")
        self._cancel_import_btn.setObjectName("TextBtn")
        self._cancel_import_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cancel_import_btn.setVisible(False)
        self._cancel_import_btn.clicked.connect(self._cancel_import)
        progress_row.addWidget(self._cancel_import_btn)

        self._retry_failed_btn = QPushButton("重试失败文件")
        self._retry_failed_btn.setObjectName("TextBtn")
        self._retry_failed_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._retry_failed_btn.setVisible(False)
        self._retry_failed_btn.setToolTip("仅重新导入上次失败的文件")
        self._retry_failed_btn.clicked.connect(self._on_retry_failed)
        progress_row.addWidget(self._retry_failed_btn)
        layout.addLayout(progress_row)

        layout.addStretch()

        scroll.setWidget(content)
        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.addWidget(scroll)

    def _connect_signals(self) -> None:
        self._drop_zone.files_dropped.connect(self._on_files_async)
        self._drop_zone.clicked.connect(self._on_choose_files)
        self._state.reports_changed.connect(self._update_reports)
        self._state.results_changed.connect(self._update_results)

    def _on_choose_files(self) -> None:
        """点击文件选择区时打开文件选择框 (支持多选)。"""
        from PySide6.QtWidgets import QFileDialog

        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "选择财务报表",
            "",
            "财务报表与附表 (*.xlsx *.xls *.xlsm *.csv *.pdf)",
        )
        if paths:
            self._on_files_async(paths)

    def scroll_to_top(self) -> None:
        """将页面滚动位置重置到顶部 (查看历史时确保拖放区可见)。"""
        self._scroll.verticalScrollBar().setValue(0)

    def _on_period_changed(self, date: QDate) -> None:
        """报告期间变化时写入 AppState, 供导入/校验/历史持久化使用。"""
        self._state.set_period(date.toString("yyyy-MM"))

    def _sync_history_banner(self) -> None:
        """按 AppState.history_view_id 刷新历史回看横幅。"""
        history_id = self._state.history_view_id
        summary = self._state.results
        if history_id is None:
            self._period_input.setEnabled(True)
            self._history_banner.setVisible(False)
            return
        # 历史回看时期间跟随历史记录, 不允许修改
        self._period_input.setEnabled(False)
        period_text = summary.period if summary is not None else ""
        parsed = QDate.fromString(period_text, "yyyy-MM")
        if not parsed.isValid():
            parsed = QDate.currentDate()
        self._period_input.blockSignals(True)
        self._period_input.setDate(parsed)
        self._period_input.blockSignals(False)
        period = summary.period if summary is not None else ""
        self._history_banner_text.setText(
            f"历史回看 #{history_id} · 期间 {period or '未设置'} · 当前为历史结果，导入新文件将自动退出回看"
        )
        self._history_banner.setVisible(True)

    def _on_file(self, file_path: str) -> None:
        self._on_files([file_path])

    def _on_files(self, file_paths: list[str]) -> None:
        """同步导入入口 (保留给测试与内部调用)。

        UI 中的拖放/点击文件区已改走 _on_files_async。
        """
        logger.info(f"导入文件(同步): {file_paths}")
        self._set_import_running(True)
        try:
            reports, dataset, errors = self._import_paths(file_paths)
            self._apply_import_result(file_paths, reports, dataset, errors)
        finally:
            self._set_import_running(False)

    def _import_paths(
        self,
        file_paths: list[str],
        progress_cb: object | None = None,
        cancel_event: threading.Event | None = None,
    ) -> tuple[list[Report], DetailDataset, list[str]]:
        """纯数据导入管线 (可在后台线程运行, 不触碰任何 Qt 控件)。"""
        self._importer.period = self._state.period
        self._detail_importer.period = self._state.period

        reports_by_type: dict[ReportType, Report] = {}
        successful_datasets: list[DetailDataset] = []
        errors: list[str] = []

        for path in file_paths:
            if cancel_event is not None and cancel_event.is_set():
                errors.append(f"{path}: 已取消")
                continue
            emit = progress_cb
            if callable(emit):
                emit(f"正在读取: {Path(path).name}")
            pdf_diagnostics = None
            try:
                suffix = Path(path).suffix.lower()
                if suffix == ".pdf":
                    from fsa.core.importer.pdf_reader import (
                        PdfReadDiagnostics,
                        read_pdf,
                    )

                    pdf_diagnostics = PdfReadDiagnostics()
                    raw_data = read_pdf(path, diagnostics=pdf_diagnostics)
                else:
                    raw_data = read_excel(path)
            except FileNotFoundError:
                logger.warning(f"文件「{path}」不存在")
                errors.append(f"{path}: 文件不存在")
                continue
            except (FSAError, ValueError, OSError, ImportError, KeyError, TypeError) as e:
                logger.warning(f"文件「{path}」读取失败: {e}")
                errors.append(f"{path}: {e}")
                continue

            if cancel_event is not None and cancel_event.is_set():
                errors.append(f"{path}: 已取消")
                continue

            # 审查修正 (2026-08-16 终审 P2): 主表/明细导入失败计入 errors,
            # 使成功计数与「重试失败文件」准确 (此前仅 debug 日志, 文件被误计为成功)
            file_failures: list[str] = []
            try:
                file_reports = self._importer.import_data(raw_data, path, suffix)
            except Exception as e:
                logger.warning(f"主表导入失败（明细不受影响）: {path}: {e}")
                file_failures.append(f"主表导入失败: {e}")
                file_reports = []
            if pdf_diagnostics is not None:
                for report in file_reports:
                    report.parse_diagnostics = pdf_diagnostics.summary_text()

            try:
                file_dataset = self._detail_importer.import_data(raw_data)
            except Exception as e:
                logger.warning(f"明细导入失败（主表不受影响）: {path}: {e}")
                file_failures.append(f"明细导入失败: {e}")
                file_dataset = DetailDataset(source_file=path, period=self._state.period)
            if file_failures:
                errors.append(f"{path}: {'；'.join(file_failures)}")

            for report in file_reports:
                if report.report_type not in reports_by_type:
                    reports_by_type[report.report_type] = report
            successful_datasets.append(file_dataset)

        dataset = DetailDataset(period=self._state.period)
        for file_dataset in successful_datasets:
            dataset.merge(file_dataset)
        return list(reports_by_type.values()), dataset, errors

    def trigger_validate(self) -> None:
        """同步校验入口 (保留给测试与内部调用)。"""
        summary = self._run_validation()
        if summary is not None:
            self._apply_validation_summary(summary)

    def _run_validation(self, cancel_event: threading.Event | None = None) -> object | None:
        """纯校验管线 (可在后台线程运行, 不触碰 Qt 控件)。"""
        registry = self._state.registry
        if registry is None:
            return None
        dataset = self._state.detail_dataset
        if not self._state.reports and dataset is None:
            return None
        if cancel_event is not None and cancel_event.is_set():
            return None

        service = PackageValidationService(registry)
        summary = service.validate(
            self._state.reports,
            dataset or DetailDataset(period=self._state.period),
            self._state.period,
            threshold_vars=self._industry_threshold_vars(),
        )

        source_files = sorted({report.source_file for report in self._state.reports if report.source_file})
        if not source_files and dataset is not None and dataset.source_file:
            source_files = [dataset.source_file]
        summary.source_files = source_files
        hashes: list[str] = []
        sizes: list[int] = []
        for path in source_files:
            if cancel_event is not None and cancel_event.is_set():
                return None
            # S5: 读取失败返回空串时记「未计算」, 保持与 source_files/sizes 平行对齐
            digest = sha256_file(path)
            hashes.append(digest if digest else "未计算")
            try:
                sizes.append(Path(path).stat().st_size)
            except OSError:
                sizes.append(-1)
        summary.source_hashes = hashes
        summary.source_file_sizes = sizes
        summary.rule_version = registry.rule_library_version
        return summary

    @staticmethod
    def _industry_threshold_vars() -> dict[str, float] | None:
        """按设置页选择的行业生成 LR-* 阈值变量; 通用行业返回 None (走默认)。"""
        from PySide6.QtCore import QSettings

        from fsa.core.engine.thresholds import threshold_vars_for

        industry = str(QSettings("FSA", "FinancialAudit").value("industry", "general"))
        if industry == "general":
            return None
        return threshold_vars_for(industry)

    def _run_multi_entity(self, folders: list[str], cancel_event: threading.Event | None = None) -> object:
        """执行多主体批量校验 (后台线程)。"""
        from fsa.services.multi_entity_service import MultiEntityService

        registry = self._state.registry
        if registry is None:
            raise RuntimeError("规则库未加载")
        service = MultiEntityService(registry)
        # 按文件夹逐个校验; 无法中断单个主体内部文件读取, 但在主体间检查取消
        outcomes = []
        for folder in folders:
            if cancel_event is not None and cancel_event.is_set():
                break
            outcomes.append(service.validate_folder(folder, period=self._state.period))
        from fsa.services.package_service import merge_summaries

        summaries = [o.summary for o in outcomes if o.summary is not None]
        combined = merge_summaries(*summaries) if summaries else None
        bilateral = service.check_bilateral(outcomes)
        from fsa.services.multi_entity_service import MultiEntityResult

        return MultiEntityResult(outcomes=outcomes, combined=combined, bilateral=bilateral)
