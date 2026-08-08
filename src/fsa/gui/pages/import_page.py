"""数据导入与校验页面。

用户在此页面导入 Excel 文件并执行勾稽校验,
校验结果以卡片形式直接显示在本页面。

匹配 Demo v4 设计: 拖放区 + 报表卡片 + 汇总卡片 + 筛选标签 + 规则明细卡片。
"""

from __future__ import annotations

from loguru import logger
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import InfoBar, InfoBarPosition, PrimaryPushButton, PushButton

from fsa.core.importer.importer import ImportService
from fsa.gui.app_state import AppState
from fsa.gui.theme import get_mono_font
from fsa.gui.widgets.drop_zone import DropZone
from fsa.gui.widgets.result_card import ResultCard
from fsa.gui.widgets.summary_card import SummaryCard
from fsa.services.validation_service import ValidationService


class ImportPage(QWidget):
    """数据导入与校验页面。"""

    validate_enabled_changed = Signal(bool)

    def __init__(self, state: AppState) -> None:
        super().__init__()
        self.setObjectName("ImportPage")
        self._state = state
        self._importer = ImportService()
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
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

        self._reports_info = QLabel("")
        self._reports_info.setStyleSheet("font-size: 13px; color: #6b7280;")
        reports_layout.addWidget(self._reports_info)
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
        self._card_fail = SummaryCard("error")
        self._card_error = SummaryCard("warning")
        self._card_total = SummaryCard("info")
        for card in [self._card_pass, self._card_fail, self._card_error, self._card_total]:
            cards_row.addWidget(card)
        summary_layout.addLayout(cards_row)
        layout.addWidget(self._summary_section)

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
        self._empty_label = QLabel("等待导入财务报表")
        self._empty_label.setStyleSheet(
            "font-size: 14px; color: #9ca3af; text-align: center;"
        )
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._empty_label)

        layout.addStretch()

        scroll.setWidget(content)
        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.addWidget(scroll)

    def _connect_signals(self) -> None:
        self._drop_zone.file_dropped.connect(self._on_file)
        self._state.reports_changed.connect(self._update_reports)
        self._state.results_changed.connect(self._update_results)

    def _on_file(self, file_path: str) -> None:
        logger.info(f"导入文件: {file_path}")
        self._importer.period = self._state.period
        try:
            reports = self._importer.import_file(file_path)
        except FileNotFoundError:
            self._show_info("文件不存在，请检查文件路径", "error")
            return
        except ValueError as e:
            self._show_info(f"文件格式错误: {e}", "error")
            return
        except OSError as e:
            self._show_info(f"读取文件失败: {e}", "error")
            return

        if not reports:
            self._show_info("文件中未找到可识别的财务报表", "warning")
            return

        self._state.set_reports(reports)
        self._show_info(f"成功导入 {len(reports)} 张报表", "success")

    def trigger_validate(self) -> None:
        """触发校验 (供顶栏按钮调用)。"""
        registry = self._state.registry
        if registry is None:
            self._show_info("规则库未加载，请检查规则文件", "error")
            return
        if not self._state.reports:
            self._show_info("请先导入报表", "warning")
            return

        service = ValidationService(registry)
        summary = service.validate(self._state.reports, self._state.period)
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
            self._empty_label.setVisible(True)
            self.validate_enabled_changed.emit(False)
            return

        self._reports_section.setVisible(True)
        self._empty_label.setVisible(False)

        lines = []
        for r in reports:
            lines.append(f"  {r.report_type.value} ({r.period}) - {len(r.items)} 个项目")
        self._reports_info.setText("\n".join(lines))
        self.validate_enabled_changed.emit(True)

    def _update_results(self) -> None:
        summary = self._state.results
        if summary is None:
            return

        self._summary_section.setVisible(True)
        self._detail_section.setVisible(True)

        self._card_pass.set_data("通过", summary.passed, "校验通过")
        self._card_fail.set_data("不通过", summary.failed, "差额超容差")
        self._card_error.set_data("异常", summary.errored, "无法执行")
        self._card_total.set_data("总数", summary.total, f"成功率 {summary.success_rate:.0%}")

        self._clear_cards()
        for result in summary.results:
            self._cards_layout.addWidget(ResultCard(result))

    def _clear_cards(self) -> None:
        while self._cards_layout.count():
            item = self._cards_layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
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
