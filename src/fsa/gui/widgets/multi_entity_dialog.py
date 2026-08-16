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
        if result.combined is None:
            summary.setText("没有主体成功完成校验")
        else:
            summary.setText(
                f"合并校验: 共 {result.combined.total} 条规则 · "
                f"通过 {result.combined.passed} · "
                f"不通过 {result.combined.failed} · "
                f"异常 {result.combined.errored}"
            )
        layout.addWidget(summary)

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
            bilateral_title = QLabel("内部现金流双边核对")
            bilateral_title.setObjectName("SectionTitle")
            layout.addWidget(bilateral_title)

            bilateral_table = QTableWidget(len(result.bilateral), 4)
            bilateral_table.setHorizontalHeaderLabels(["结果", "方向", "差额", "说明"])
            bilateral_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            bilateral_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
            bilateral_table.horizontalHeader().setStretchLastSection(True)
            for row_idx, item in enumerate(result.bilateral):
                status = "通过" if item.passed else "不通过"
                bilateral_table.setItem(row_idx, 0, QTableWidgetItem(status))
                bilateral_table.setItem(row_idx, 1, QTableWidgetItem(item.rule_name))
                bilateral_table.setItem(row_idx, 2, QTableWidgetItem(f"{item.diff:,.2f}"))
                bilateral_table.setItem(row_idx, 3, QTableWidgetItem(item.message))
            bilateral_table.resizeColumnsToContents()
            layout.addWidget(bilateral_table)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.clicked.connect(self.accept)
        layout.addWidget(buttons)
