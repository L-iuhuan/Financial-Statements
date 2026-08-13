"""数据导入与校验页面。

用户在此页面导入 Excel 文件并执行勾稽校验,
校验结果以卡片形式直接显示在本页面。

匹配 Demo v4 设计: 拖放区 + 报表卡片 + 汇总卡片 + 筛选标签 + 规则明细卡片。
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
from qfluentwidgets import FluentIcon, InfoBar, InfoBarPosition

from fsa.core.exceptions import FSAError
from fsa.core.importer.detail_importer import DetailImporter
from fsa.core.importer.importer import ImportService
from fsa.core.models.detail import DetailDataset
from fsa.core.models.report import Report, ReportType
from fsa.core.models.rule import Severity
from fsa.gui.app_state import AppState
from fsa.gui.widgets.drop_zone import DropZone
from fsa.gui.widgets.report_card import ReportCard
from fsa.gui.widgets.result_card import ResultCard
from fsa.gui.widgets.summary_card import SummaryCard
from fsa.services.package_service import PackageValidationService


class ImportPage(QWidget):
    """数据导入与校验页面。"""

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
        self._result_cards: list[tuple[object, ResultCard]] = []
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
        reports_title.setStyleSheet("font-size: 15px; font-weight: 600;")
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
        summary_title.setStyleSheet("font-size: 15px; font-weight: 600;")
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
        detail_title.setStyleSheet("font-size: 15px; font-weight: 600;")
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
        """一次导入一个或多个文件（主表 + 附表），分别识别并合并。"""
        logger.info(f"导入文件: {file_paths}")
        self._importer.period = self._state.period
        self._detail_importer.period = self._state.period

        reports_by_type: dict[ReportType, Report] = {}
        dataset = DetailDataset(period=self._state.period)
        errors: list[str] = []
        try:
            for path in file_paths:
                try:
                    for report in self._importer.import_file(path):
                        if report.report_type not in reports_by_type:
                            reports_by_type[report.report_type] = report
                    dataset.merge(self._detail_importer.import_file(path))
                except FileNotFoundError:
                    errors.append(f"{path}: 文件不存在")
                except (FSAError, ValueError, OSError, ImportError) as e:
                    errors.append(f"{path}: {e}")
        except (FSAError, ValueError, OSError, ImportError, KeyError, TypeError) as e:
            logger.error(f"导入报表包异常: {e}")
            errors.append(str(e))

        reports = list(reports_by_type.values())
        if not reports and not dataset.trial_balance and not dataset.journal:
            self._show_info("未识别到任何财务报表或明细数据", "warning")
            return

        self._state.set_reports(reports)
        self._state.set_detail_dataset(dataset)
        detail_rows = (
            len(dataset.trial_balance)
            + len(dataset.journal)
            + len(dataset.cash_flow_detail)
            + len(dataset.reclassifications)
            + len(dataset.related_party_purchases)
            + len(dataset.sales_details)
            + len(dataset.internal_cash_flows)
        )
        message = f"成功导入 {len(reports)} 张报表、{detail_rows} 行明细数据"
        if errors:
            message += f"；{len(errors)} 个文件失败"
            self._show_info(message, "warning")
        else:
            self._show_info(message, "success")
        self.validate_enabled_changed.emit(bool(reports) or detail_rows > 0)

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

    def _update_reports(self) -> None:
        reports = self._state.reports
        if not reports:
            self._reports_section.setVisible(False)
            self._drop_zone.setVisible(True)
            self._empty_state.setVisible(True)
            self.validate_enabled_changed.emit(False)
            self._clear_report_cards()
            return

        self._reports_section.setVisible(True)
        self._drop_zone.setVisible(False)
        self._empty_state.setVisible(False)
        self._clear_report_cards()

        for i, report in enumerate(reports):
            card = ReportCard(report)
            self._cards_grid.addWidget(card, i // 3, i % 3)

        self.validate_enabled_changed.emit(True)

    def _clear_report_cards(self) -> None:
        while self._cards_grid.count():
            item = self._cards_grid.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                # 先隐藏再删除: takeAt 使 widget 脱离父容器成为顶级窗口,
                # deleteLater 仅排队删除, 不 hide 会闪现为无标题"python"独立窗口
                widget.hide()
                widget.deleteLater()

    def _update_results(self) -> None:
        summary = self._state.results
        if summary is None:
            # 无结果 (重置后): 隐藏结果区, 恢复初始引导由 _update_reports 负责
            self._summary_section.setVisible(False)
            self._filter_section.setVisible(False)
            self._detail_section.setVisible(False)
            return

        # 有结果: 隐藏初始引导 (覆盖正常校验与查看历史两种场景)
        # 历史查看时 reports 为空, 报表区不显示, 但结果区必须显示
        self._drop_zone.setVisible(False)
        self._empty_state.setVisible(False)

        self._summary_section.setVisible(True)
        self._filter_section.setVisible(True)
        self._detail_section.setVisible(True)

        # 统计: 错误 = failed&ERROR + errored; 警告 = failed&WARNING/INFO
        error_count = sum(
            1
            for r in summary.results
            if (
                (not r.passed and not r.errored and r.severity is Severity.ERROR)
                or r.errored
            )
        )
        warn_count = sum(
            1
            for r in summary.results
            if not r.passed and not r.errored and r.severity in (Severity.WARNING, Severity.INFO)
        )

        self._card_pass.set_data("通过", summary.passed, "校验通过的规则")
        self._card_error.set_data("错误", error_count, "必须修正的差额")
        self._card_warn.set_data("警告", warn_count, "建议关注的异常")
        self._card_total.set_data("规则总数", summary.total, "规则库总数")

        # 更新筛选标签计数
        counts = {
            "all": summary.total,
            "error": error_count,
            "warning": warn_count,
            "pass": summary.passed,
        }
        labels = {"all": "全部", "error": "错误", "warning": "警告", "pass": "通过"}
        for key, btn in self._filter_buttons.items():
            btn.setText(f"{labels[key]} ({counts[key]})")

        # 默认选中"全部"
        if self._current_filter not in counts:
            self._current_filter = "all"
        self._update_filter_styles()
        self._rebuild_cards()

    def _on_filter(self, key: str) -> None:
        """切换筛选标签 (仅切可见性, 不重建卡片, 避免闪动)。"""
        self._current_filter = key
        self._update_filter_styles()
        self._apply_filter()

    def _update_filter_styles(self) -> None:
        """更新筛选按钮的选中/未选中样式。"""
        for key, btn in self._filter_buttons.items():
            active = key == self._current_filter
            btn.setChecked(active)
            btn.setProperty("active", active)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _rebuild_cards(self) -> None:
        """结果变化时重建全部卡片并缓存 (仅在校验完成/查看历史时调用一次)。"""
        summary = self._state.results
        if summary is None:
            return

        self._clear_cards()
        self._result_cards.clear()
        for result in summary.results:
            card = ResultCard(result)
            card.diagnose_clicked.connect(self.diagnose_requested.emit)
            card.debate_clicked.connect(self.debate_requested.emit)
            self._cards_layout.addWidget(card)
            self._result_cards.append((result, card))
        self._apply_filter()

    def _apply_filter(self) -> None:
        """按当前筛选条件切换卡片可见性 (不销毁/重建, 消除闪动)。"""
        for result, card in self._result_cards:
            card.setVisible(self._match_filter(result))

    def _match_filter(self, result) -> bool:
        """判断单个结果是否匹配当前筛选条件。"""
        if self._current_filter == "all":
            return True
        if self._current_filter == "pass":
            return result.passed and not result.errored
        if self._current_filter == "error":
            if result.errored:
                return True
            return not result.passed and result.severity is Severity.ERROR
        if self._current_filter == "warning":
            return (
                not result.passed
                and not result.errored
                and result.severity in (Severity.WARNING, Severity.INFO)
            )
        return True

    def _clear_cards(self) -> None:
        while self._cards_layout.count():
            item = self._cards_layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                # 先隐藏再删除, 避免脱离父容器后闪现为独立窗口
                widget.hide()
                widget.deleteLater()

    def _show_info(self, message: str, kind: str = "info") -> None:
        methods = {
            "success": InfoBar.success,
            "warning": InfoBar.warning,
            "error": InfoBar.error,
            "info": InfoBar.info,
        }
        method = methods.get(kind, InfoBar.info)
        method(
            "提示",
            message,
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=3000,
            parent=self,
        )
