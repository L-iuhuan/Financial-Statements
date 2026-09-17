"""多主体批量校验结果对话框。"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from fsa.core.models.result import ValidationResult
from fsa.services.multi_entity_service import MultiEntityResult


class MultiEntityResultDialog(QDialog):
    """展示各主体校验结果与内部现金流双边核对结果。"""

    def __init__(
        self,
        result: MultiEntityResult,
        parent: QWidget | None = None,
        saved_count: int | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("多主体批量校验结果")
        self.resize(820, 560)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        summary = QLabel()
        summary.setObjectName("PageTitle")
        summary.setStyleSheet("font-size: 14px;")
        summaries = [o.summary for o in result.outcomes if o.summary is not None]
        if not summaries:
            summary.setText("没有主体成功完成校验")
        else:
            total_results = sum(len(s.results) for s in summaries)
            total_passed = sum(s.passed for s in summaries)
            total_failed = sum(s.failed for s in summaries)
            total_errored = sum(s.errored for s in summaries)
            summary.setText(
                f"合计（全部主体）: 共 {total_results} 条校验结果 · "
                f"通过 {total_passed} · "
                f"不通过 {total_failed} · "
                f"异常 {total_errored}"
            )
        layout.addWidget(summary)

        if summaries:
            subtitle = QLabel("合计 = 各主体校验结果之和")
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

        entity_table = QTableWidget(len(result.outcomes), 5)
        entity_table.setHorizontalHeaderLabels(
            ["主体", "报表数", "通过", "不通过", "异常/错误"]
        )
        entity_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        entity_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        entity_table.horizontalHeader().setStretchLastSection(True)
        for row_idx, outcome in enumerate(result.outcomes):
            if outcome.summary is None:
                passed, failed, errored = 0, 0, len(outcome.errors)
            else:
                passed = outcome.summary.passed
                failed = outcome.summary.failed
                errored = outcome.summary.errored
            entity_table.setItem(row_idx, 0, QTableWidgetItem(outcome.entity_id))
            entity_table.setItem(row_idx, 1, QTableWidgetItem(str(len(outcome.reports))))
            entity_table.setItem(row_idx, 2, QTableWidgetItem(str(passed)))
            entity_table.setItem(row_idx, 3, QTableWidgetItem(str(failed)))
            entity_table.setItem(
                row_idx,
                4,
                QTableWidgetItem(
                    str(errored) if not outcome.errors else "; ".join(outcome.errors[:2])
                ),
            )
        entity_table.resizeColumnsToContents()
        layout.addWidget(entity_table)

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
        layout.addWidget(buttons)


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
    for row_idx, item in enumerate(results):
        status = "通过" if item.passed else ("跳过" if item.skipped else "不通过")
        first_line = item.message.split("\n\n")[0]
        cell = QTableWidgetItem(first_line)
        cell.setToolTip(item.message)
        table.setItem(row_idx, 0, QTableWidgetItem(status))
        table.setItem(row_idx, 1, QTableWidgetItem(f"{item.diff:,.2f}"))
        table.setItem(row_idx, 2, cell)
    table.resizeColumnsToContents()
    table.resizeRowsToContents()
    return table
