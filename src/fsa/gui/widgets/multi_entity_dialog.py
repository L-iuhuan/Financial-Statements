"""多主体批量校验结果对话框 (可滚动/可下钻逐主体未通过明细)。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHeaderView,
    QLabel,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from fsa.core.models.result import ValidationResult
from fsa.services.multi_entity_service import EntityOutcome, MultiEntityResult

# 表格高度上限: 超出后表格内部滚动, 防止 16 主体把对话框撑爆
# (2026-09-18 目验: 820x560 固定尺寸下多表挤压导致文字遮挡/数字不全)
_TABLE_MAX_HEIGHT = 280


class MultiEntityResultDialog(QDialog):
    """展示各主体校验结果、未通过明细下钻与双边核对结果 (非模态、可滚动)。"""

    def __init__(
        self,
        result: MultiEntityResult,
        parent: QWidget | None = None,
        saved_count: int | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("多主体批量校验结果")
        self.resize(1000, 680)
        self.setMinimumSize(760, 480)
        self._outcomes = list(result.outcomes)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 16, 20, 12)
        scroll.setWidget(content)
        outer.addWidget(scroll, stretch=1)

        summaries = [o.summary for o in result.outcomes if o.summary is not None]

        summary = QLabel()
        summary.setObjectName("PageTitle")
        summary.setStyleSheet("font-size: 14px;")
        if not summaries:
            summary.setText("没有主体成功完成校验")
        else:
            total_results = sum(len(s.results) for s in summaries)
            total_passed = sum(s.passed for s in summaries)
            total_failed = sum(s.failed for s in summaries)
            total_errored = sum(s.errored for s in summaries)
            total_skipped = sum(s.skipped for s in summaries)
            text = (
                f"合计（全部主体）: 共 {total_results} 条校验结果 · "
                f"通过 {total_passed} · 不通过 {total_failed} · 异常 {total_errored}"
            )
            if total_skipped:
                # 数字完整: 通过+不通过+异常+跳过 = 总数 (2026-09-18 目验"数字不全")
                text += f" · 跳过 {total_skipped}（缺数据）"
            summary.setText(text)
        layout.addWidget(summary)

        if summaries:
            subtitle = QLabel(
                "合计 = 各主体校验结果之和；双击主体行可查看该主体的未通过明细"
            )
            subtitle.setObjectName("MetaLabel")
            layout.addWidget(subtitle)

        # B1-5: 告知用户各主体结果已写入历史记录 (None 表示未尝试/存储不可用)
        if saved_count is not None and saved_count > 0:
            saved_hint = QLabel(f"结果已保存到历史记录（{saved_count} 个主体）")
            saved_hint.setObjectName("MetaLabel")
            layout.addWidget(saved_hint)

        entity_title = QLabel("主体校验结果")
        entity_title.setObjectName("SectionTitle")
        layout.addWidget(entity_title)
        layout.addWidget(self._build_entity_table())

        if result.bilateral:
            bilateral_title = QLabel("内部现金流双边核对（附表6）")
            bilateral_title.setObjectName("SectionTitle")
            layout.addWidget(bilateral_title)
            layout.addWidget(_bilateral_table(result.bilateral))

        if result.purchase_sales:
            ps_title = QLabel("关联方购销双边核对（附表4 ↔ 附表5）")
            ps_title.setObjectName("SectionTitle")
            layout.addWidget(ps_title)
            layout.addWidget(_bilateral_table(result.purchase_sales))

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.clicked.connect(self.accept)
        outer.addWidget(buttons)

    def _build_entity_table(self) -> QTableWidget:
        """主体汇总表: 7 列 (含跳过计数与导入错误), 双击行下钻明细。"""
        table = QTableWidget(len(self._outcomes), 7)
        table.setHorizontalHeaderLabels(
            ["主体", "报表数", "通过", "不通过", "异常", "跳过", "导入错误"]
        )
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        table.setMaximumHeight(_TABLE_MAX_HEIGHT)
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, 6):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        for row, outcome in enumerate(self._outcomes):
            if outcome.summary is None:
                passed = failed = errored = skipped = 0
            else:
                passed = outcome.summary.passed
                failed = outcome.summary.failed
                errored = outcome.summary.errored
                skipped = outcome.summary.skipped
            values = [
                outcome.entity_id,
                str(len(outcome.reports)),
                str(passed),
                str(failed),
                str(errored),
                str(skipped),
                "; ".join(outcome.errors[:2]) if outcome.errors else "",
            ]
            for column, text in enumerate(values):
                item = QTableWidgetItem(text)
                if column == 6 and outcome.errors:
                    item.setToolTip("\n".join(outcome.errors))
                else:
                    item.setToolTip(text)
                if 1 <= column <= 5:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(row, column, item)
        table.cellDoubleClicked.connect(self._open_entity_detail)
        return table

    def _open_entity_detail(self, row: int, _column: int) -> None:
        """双击主体行: 打开该主体的未通过/异常/跳过明细 (问题回看)。"""
        if not 0 <= row < len(self._outcomes):
            return
        EntityDetailDialog(self._outcomes[row], self).show()


class EntityDetailDialog(QDialog):
    """单主体未通过明细 (问题回看 + 不通过原因, 非模态)。"""

    def __init__(
        self, outcome: EntityOutcome, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"「{outcome.entity_id}」校验明细")
        self.resize(880, 560)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        counts = QLabel()
        counts.setObjectName("PageTitle")
        counts.setStyleSheet("font-size: 13px;")
        if outcome.summary is None:
            counts.setText("该主体未完成校验（无汇总结果）")
        else:
            s = outcome.summary
            counts.setText(
                f"共 {len(s.results)} 条 · 通过 {s.passed} · 不通过 {s.failed}"
                f" · 异常 {s.errored} · 跳过 {s.skipped}"
            )
        layout.addWidget(counts)

        if outcome.errors:
            error_label = QLabel("导入错误：\n" + "\n".join(outcome.errors))
            error_label.setObjectName("MetaLabel")
            error_label.setWordWrap(True)
            layout.addWidget(error_label)

        results = outcome.summary.results if outcome.summary is not None else []
        rows = [r for r in results if not r.passed or r.skipped]
        if not rows:
            empty = QLabel("该主体全部规则通过，无未通过项")
            empty.setObjectName("EmptyTitle")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(empty, stretch=1)
        else:
            layout.addWidget(_detail_table(rows), stretch=1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.clicked.connect(self.accept)
        layout.addWidget(buttons)


def _detail_table(rows: list[ValidationResult]) -> QTableWidget:
    """未通过明细表: 结果/规则/说明 (悬停查看完整解读)。"""
    table = QTableWidget(len(rows), 3)
    table.setHorizontalHeaderLabels(["结果", "规则", "说明（悬停查看完整解读）"])
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
    table.setWordWrap(True)
    table.horizontalHeader().setStretchLastSection(True)
    for row_idx, item in enumerate(rows):
        if item.errored:
            status = "异常"
        elif item.skipped:
            status = "跳过"
        else:
            status = "不通过"
        first_line = item.message.split("\n\n")[0]
        desc = QTableWidgetItem(first_line)
        desc.setToolTip(item.message)
        rule = QTableWidgetItem(f"{item.rule_name}（{item.rule_id}）")
        rule.setToolTip(item.rule_id)
        table.setItem(row_idx, 0, QTableWidgetItem(status))
        table.setItem(row_idx, 1, rule)
        table.setItem(row_idx, 2, desc)
    table.resizeColumnsToContents()
    table.resizeRowsToContents()
    return table


def _bilateral_table(results: list[ValidationResult]) -> QTableWidget:
    """构建双边核对结果表: 结论/差额 + 说明首行 (悬停查看完整解读)。

    单元格只显示消息首行 (事实描述, 含双方名称与金额对比), 完整消息
    (含【为什么关注/常见原因/建议】解读) 挂在 tooltip 上, 保持表格紧凑。
    """
    table = QTableWidget(len(results), 3)
    table.setHorizontalHeaderLabels(["结果", "差额（元）", "说明（悬停查看解读）"])
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
    table.horizontalHeader().setStretchLastSection(True)
    table.setWordWrap(True)
    table.setMaximumHeight(_TABLE_MAX_HEIGHT)
    for row_idx, item in enumerate(results):
        status = "通过" if item.passed else ("跳过" if item.skipped else "不通过")
        first_line = item.message.split("\n\n")[0]
        cell = QTableWidgetItem(first_line)
        cell.setToolTip(item.message)
        diff = QTableWidgetItem(f"{item.diff:,.2f}")
        diff.setTextAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        table.setItem(row_idx, 0, QTableWidgetItem(status))
        table.setItem(row_idx, 1, diff)
        table.setItem(row_idx, 2, cell)
    table.resizeColumnsToContents()
    table.resizeRowsToContents()
    return table
