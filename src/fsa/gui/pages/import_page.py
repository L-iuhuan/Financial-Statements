"""数据导入与校验页面。

用户在此页面导入 Excel 文件并执行勾稽校验,
校验结果以卡片形式直接显示在本页面。

匹配 Demo v4 设计: 拖放区 + 报表卡片 + 汇总卡片 + 筛选标签 + 规则明细卡片。

结果卡片渲染与筛选逻辑在 import_page_results.py (ImportPageResultsMixin)。
"""

from __future__ import annotations

from loguru import logger
from PySide6.QtCore import Qt, Signal
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
from qfluentwidgets import FluentIcon, IndeterminateProgressBar

from fsa.core.exceptions import FSAError
from fsa.core.importer.detail_importer import DetailImporter
from fsa.core.importer.importer import ImportService
from fsa.core.models.detail import DetailDataset
from fsa.core.models.report import Report, ReportType
from fsa.core.models.result import ValidationResult
from fsa.gui.app_state import AppState
from fsa.gui.pages.import_page_results import ImportPageResultsMixin
from fsa.gui.widgets.drop_zone import DropZone
from fsa.gui.widgets.result_card import ResultCard
from fsa.gui.widgets.summary_card import SummaryCard
from fsa.services.package_service import PackageValidationService


class ImportPage(ImportPageResultsMixin):
    """数据导入与校验页面 (继承 mixin 提供结果卡片渲染与筛选逻辑)。"""

    validate_enabled_changed = Signal(bool)
    diagnose_requested = Signal(str)  # rule_id -> 主窗口打开 AI 抽屉
    debate_requested = Signal(str)  # rule_id -> 主窗口打开深度辩论

    def __init__(self, state: AppState) -> None:
        super().__init__()
        self.setObjectName("ImportPage")
        self._state = state
        self._importer = ImportService()
        self._detail_importer = DetailImporter()
        self._current_filter = "all"
        self._result_cards: list[tuple[ValidationResult, ResultCard]] = []
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        content.setObjectName("PageContent")
        layout = QVBoxLayout(content)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # 拖放区
        self._drop_zone = DropZone()
        layout.addWidget(self._drop_zone)

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

        # 空状态
        self._empty_state = QFrame()
        self._empty_state.setObjectName("EmptyContainer")
        empty_layout = QVBoxLayout(self._empty_state)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.setSpacing(8)

        empty_icon = QLabel()
        empty_icon.setPixmap(FluentIcon.INFO.icon().pixmap(48, 48))
        empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(empty_icon)

        empty_text = QLabel("等待导入财务报表")
        empty_text.setObjectName("EmptyTitle")
        empty_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(empty_text)

        empty_hint = QLabel("可一次拖入主表与附表（1~6），点击「执行校验」开始勾稽校验")
        empty_hint.setObjectName("MetaLabel")
        empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(empty_hint)

        layout.addWidget(self._empty_state)

        # 进度指示 (导入/校验期间显示)
        self._progress = IndeterminateProgressBar()
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        layout.addStretch()

        scroll.setWidget(content)
        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.addWidget(scroll)

    def _connect_signals(self) -> None:
        self._drop_zone.files_dropped.connect(self._on_files)
        self._state.reports_changed.connect(self._update_reports)
        self._state.results_changed.connect(self._update_results)

    def _on_file(self, file_path: str) -> None:
        self._on_files([file_path])

    def _on_files(self, file_paths: list[str]) -> None:
        """一次导入一个或多个文件（主表 + 附表），分别识别并合并。

        单文件失败不中断整批（错误信息含文件名）；
        失败文件的主表与明细数据均不进入最终结果。
        """
        logger.info(f"导入文件: {file_paths}")
        self._progress.setVisible(True)
        try:
            self._importer.period = self._state.period
            self._detail_importer.period = self._state.period

            reports_by_type: dict[ReportType, Report] = {}
            successful_datasets: list[DetailDataset] = []
            errors: list[str] = []
            for path in file_paths:
                try:
                    file_reports = self._importer.import_file(path)
                    file_dataset = self._detail_importer.import_file(path)
                except FileNotFoundError:
                    logger.warning(f"文件「{path}」不存在")
                    errors.append(f"{path}: 文件不存在")
                    continue
                except (FSAError, ValueError, OSError, ImportError, KeyError, TypeError) as e:
                    logger.warning(f"文件「{path}」导入失败: {e}")
                    errors.append(f"{path}: {e}")
                    continue
                for report in file_reports:
                    if report.report_type not in reports_by_type:
                        reports_by_type[report.report_type] = report
                successful_datasets.append(file_dataset)

            dataset = DetailDataset(period=self._state.period)
            for file_dataset in successful_datasets:
                dataset.merge(file_dataset)

            reports = list(reports_by_type.values())
            if not reports and dataset.is_empty:
                if errors:
                    self._show_info(
                        f"{len(errors)} 个文件失败: {'; '.join(errors)}", "warning"
                    )
                else:
                    self._show_info("未识别到任何财务报表或明细数据", "warning")
                return

            self._state.set_reports(reports)
            self._state.set_detail_dataset(dataset)
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
            if errors:
                message += f"；{len(errors)} 个文件失败: {'; '.join(errors)}"
                self._show_info(message, "warning")
            else:
                self._show_info(message, "success")
            self.validate_enabled_changed.emit(bool(reports) or detail_rows > 0)
        finally:
            # 任何退出路径 (成功/失败/空文件/异常) 都隐藏进度条
            self._progress.setVisible(False)

    def trigger_validate(self) -> None:
        """触发校验 (供顶栏按钮调用)。"""
        registry = self._state.registry
        if registry is None:
            self._show_info("规则库未加载，请检查规则文件", "error")
            return
        dataset = self._state.detail_dataset
        if not self._state.reports and dataset is None:
            self._show_info("请先导入报表", "warning")
            return

        service = PackageValidationService(registry)
        summary = service.validate(
            self._state.reports, dataset or DetailDataset(period=self._state.period), self._state.period
        )
        self._state.set_results(summary)
        kind = "success" if summary.all_passed else "warning"
        self._show_info(
            f"校验完成: 通过 {summary.passed}, 不通过 {summary.failed}",
            kind,
        )
