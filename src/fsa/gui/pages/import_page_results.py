"""导入页结果卡片渲染与筛选逻辑 (mixin)。

从 import_page 拆分的报表/结果卡片渲染、筛选标签与中文反馈逻辑 (纯移动, 不改行为)。
由 ImportPage 继承。

依赖宿主 ImportPage 提供的属性 (均在 __init__/_setup_ui 中初始化):
_filter_buttons / _result_cards / _cards_layout / _cards_grid / _card_* /
_summary_section / _filter_section / _detail_section / _reports_section /
_drop_zone / _empty_state / _current_filter 及各 Signal。
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import InfoBar, InfoBarPosition

from fsa.core.models.result import ValidationResult
from fsa.core.models.rule import Severity
from fsa.gui.app_state import AppState
from fsa.gui.widgets.drop_zone import DropZone
from fsa.gui.widgets.report_card import ReportCard
from fsa.gui.widgets.result_card import ResultCard
from fsa.gui.widgets.summary_card import SummaryCard


class ImportPageResultsMixin(QWidget):
    """结果卡片渲染、筛选与反馈逻辑 (继承 QWidget 以便访问 QWidget 方法)。"""

    validate_enabled_changed: Signal
    diagnose_requested: Signal
    debate_requested: Signal

    _state: AppState
    _current_filter: str
    _result_cards: list[tuple[ValidationResult, ResultCard]]
    _cards_layout: QVBoxLayout
    _cards_grid: QGridLayout
    _filter_buttons: dict[str, QPushButton]
    _summary_section: QFrame
    _filter_section: QFrame
    _detail_section: QFrame
    _reports_section: QFrame
    _drop_zone: DropZone
    _empty_state: QFrame
    _card_pass: SummaryCard
    _card_error: SummaryCard
    _card_warn: SummaryCard
    _card_total: SummaryCard

    def _sync_history_banner(self) -> None:
        """由宿主 ImportPage 提供: 同步历史回看横幅。"""
        raise NotImplementedError

    def _update_reports(self) -> None:
        reports = self._state.reports
        if not reports:
            self._reports_section.setVisible(False)
            self._drop_zone.setVisible(True)
            self._empty_state.setVisible(True)
            self.validate_enabled_changed.emit(False)
            self._clear_report_cards()
            self._sync_history_banner()
            return

        self._reports_section.setVisible(True)
        # 拖放区始终保留 (用户可随时追加导入, 无需先重置)
        self._drop_zone.setVisible(True)
        self._empty_state.setVisible(False)
        self._clear_report_cards()
        self._sync_history_banner()
        self.setUpdatesEnabled(False)
        try:
            for i, report in enumerate(reports):
                card = ReportCard(report)
                self._cards_grid.addWidget(card, i // 3, i % 3)
        finally:
            self.setUpdatesEnabled(True)

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
            self._sync_history_banner()
            return

        # 有结果: 隐藏初始引导 (覆盖正常校验与查看历史两种场景)
        # 历史查看时 reports 为空, 报表区不显示, 但结果区必须显示
        # 拖放区保持可见: 查看历史后用户可直接导入新文件, 无需先重置
        self._drop_zone.setVisible(True)
        self._empty_state.setVisible(False)

        self._summary_section.setVisible(True)
        self._filter_section.setVisible(True)
        self._detail_section.setVisible(True)
        self._sync_history_banner()

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

        # 更新筛选标签计数 (B-14: 与 _match_filter 语义保持一致)
        # - "all" 显示全部结果卡片 (含 skipped), 故用 len(summary.results)
        # - "pass" 仅统计实际通过且未跳过的结果
        counts = {
            "all": len(summary.results),
            "error": error_count,
            "warning": warn_count,
            "pass": sum(
                1 for r in summary.results if r.passed and not r.errored and not r.skipped
            ),
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
        """结果变化时刷新卡片 (仅在校验完成/查看历史时调用一次)。

        复用策略: 结果数量相同且 rule_id 序列一致时, 原地更新现有卡片
        (避免 42 张含阴影特效卡片的 deleteLater+全量重建); 否则全量重建。
        """
        summary = self._state.results
        if summary is None:
            return

        new_results = summary.results
        if (
            len(self._result_cards) == len(new_results)
            and [r.rule_id for r, _ in self._result_cards]
            == [r.rule_id for r in new_results]
        ):
            # 复用路径: 仅刷新数据, 不销毁控件
            self.setUpdatesEnabled(False)
            try:
                refreshed: list[tuple[ValidationResult, ResultCard]] = []
                for (_, card), result in zip(self._result_cards, new_results, strict=True):
                    card.update_result(result)
                    refreshed.append((result, card))
                self._result_cards = refreshed
            finally:
                self.setUpdatesEnabled(True)
            self._apply_filter()
            return

        self._clear_cards()
        self._result_cards.clear()
        self.setUpdatesEnabled(False)
        try:
            for result in new_results:
                card = ResultCard(result)
                card.diagnose_clicked.connect(self.diagnose_requested.emit)
                card.debate_clicked.connect(self.debate_requested.emit)
                self._cards_layout.addWidget(card)
                self._result_cards.append((result, card))
        finally:
            self.setUpdatesEnabled(True)
        self._apply_filter()

    def _apply_filter(self) -> None:
        """按当前筛选条件切换卡片可见性 (不销毁/重建, 消除闪动)。"""
        for result, card in self._result_cards:
            card.setVisible(self._match_filter(result))

    def _match_filter(self, result: ValidationResult) -> bool:
        """判断单个结果是否匹配当前筛选条件。"""
        if self._current_filter == "all":
            return True
        if self._current_filter == "pass":
            # skipped=True 的结果 (规则因缺数据跳过) 不算"通过" (B-14)
            return result.passed and not result.errored and not result.skipped
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
