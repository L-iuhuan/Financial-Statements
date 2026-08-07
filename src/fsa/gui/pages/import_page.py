"""数据导入与校验页面。

用户在此页面导入 Excel 文件并执行勾稽校验,
校验结果以卡片形式直接显示在本页面。
"""

from __future__ import annotations

from loguru import logger
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    InfoBar,
    InfoBarPosition,
    PrimaryPushButton,
    ProgressBar,
    PushButton,
)

from fsa.core.importer.importer import ImportService
from fsa.gui.app_state import AppState
from fsa.gui.widgets.drop_zone import DropZone
from fsa.gui.widgets.result_card import ResultCard
from fsa.services.validation_service import ValidationService


class ImportPage(QWidget):
    """数据导入与校验页面。"""

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

        title = QLabel("数据导入与校验")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        layout.addWidget(title)

        self._drop_zone = DropZone()
        layout.addWidget(self._drop_zone)

        buttons = QHBoxLayout()
        self._file_btn = PushButton("选择文件")
        self._validate_btn = PrimaryPushButton("开始校验")
        self._validate_btn.setEnabled(False)
        buttons.addWidget(self._file_btn)
        buttons.addWidget(self._validate_btn)
        buttons.addStretch()
        layout.addLayout(buttons)

        self._reports_label = QLabel("尚未导入报表")
        self._reports_label.setStyleSheet("color: #64748b;")
        layout.addWidget(self._reports_label)

        self._summary_label = QLabel("")
        self._summary_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(self._summary_label)

        self._progress = ProgressBar()
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        self._cards_layout = QVBoxLayout()
        self._cards_layout.setSpacing(8)
        layout.addLayout(self._cards_layout)
        layout.addStretch()

        scroll.setWidget(content)
        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.addWidget(scroll)

    def _connect_signals(self) -> None:
        self._drop_zone.file_dropped.connect(self._on_file)
        self._file_btn.clicked.connect(self._on_select_file)
        self._validate_btn.clicked.connect(self._on_validate)
        self._state.reports_changed.connect(self._update_reports)
        self._state.results_changed.connect(self._update_results)

    def _on_select_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 Excel 文件", "", "Excel 文件 (*.xlsx *.xls)"
        )
        if path:
            self._on_file(path)

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

    def _on_validate(self) -> None:
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
            f"校验完成: 通过 {summary.passed}, 不通过 {summary.failed}", kind
        )

    def _update_reports(self) -> None:
        reports = self._state.reports
        if not reports:
            self._reports_label.setText("尚未导入报表")
            self._validate_btn.setEnabled(False)
            return

        lines = [f"已导入 {len(reports)} 张报表:"]
        for r in reports:
            lines.append(f"  {r.report_type.value} ({r.period}) - {len(r.items)} 个项目")
        self._reports_label.setText("\n".join(lines))
        self._validate_btn.setEnabled(True)

    def _update_results(self) -> None:
        summary = self._state.results
        if summary is None:
            return

        self._summary_label.setText(
            f"通过: {summary.passed}  不通过: {summary.failed}  "
            f"异常: {summary.errored}  跳过: {summary.skipped}"
        )
        color = "#10b981" if summary.all_passed else "#ef4444"
        self._summary_label.setStyleSheet(
            f"font-size: 16px; font-weight: bold; color: {color};"
        )

        self._progress.setVisible(True)
        self._progress.setValue(int(summary.success_rate * 100))

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
