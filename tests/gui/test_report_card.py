"""ReportCard 科目清单可视化测试 (识别清单与 ReportItem 一一对应)。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QLabel, QPushButton, QTableWidget

from fsa.core.models.report import Report, ReportItem, ReportType
from fsa.gui.widgets.report_card import ReportCard


def _make_report() -> Report:
    return Report(
        report_type=ReportType.BALANCE_SHEET,
        period="2024-12",
        source_file="D:\\财务\\资产负债表.xlsx",
        items=[
            ReportItem(
                key="asset_total",
                name="资产总计",
                amount=1_000_000.0,
                beginning_amount=900_000.0,
                row=35,
                column="期末余额",
            ),
            ReportItem(
                key="monetary_funds",
                name="货币资金",
                amount=200_000.0,
                row=2,
                column="期末余额",
            ),
        ],
        unmapped_names=["其中：受限货币资金"],
    )


class TestReportCardVisibility:
    def test_unmapped_count_visible(self, qapp, qtbot) -> None:
        card = ReportCard(_make_report())
        qtbot.addWidget(card)
        labels = [label.text() for label in card.findChildren(QLabel)]
        assert any("未映射 1 项" in text for text in labels)
        assert card._unmapped_label.toolTip() == "未映射科目: 其中：受限货币资金"

    def test_all_mapped_visible(self, qapp, qtbot) -> None:
        report = _make_report()
        report.unmapped_names = []
        card = ReportCard(report)
        qtbot.addWidget(card)
        labels = [label.text() for label in card.findChildren(QLabel)]
        assert any("科目全部映射" in text for text in labels)


class TestReportCardDetailDialog:
    def test_identified_table_matches_items_one_to_one(self, qapp, qtbot, monkeypatch) -> None:
        card = ReportCard(_make_report())
        qtbot.addWidget(card)
        dialog: list[QDialog] = []
        monkeypatch.setattr(QDialog, "exec", lambda self, d=dialog: (d.append(self), 0)[1])

        button = next(btn for btn in card.findChildren(QPushButton) if btn.text() == "查看科目清单")
        qtbot.mouseClick(button, Qt.MouseButton.LeftButton)

        assert len(dialog) == 1
        tables = dialog[0].findChildren(QTableWidget)
        identified = next(table for table in tables if table.columnCount() == 6)
        unmapped = next(table for table in tables if table.columnCount() == 1)
        assert identified.rowCount() == len(card._report.items)
        assert identified.columnCount() == 6
        values = [
            identified.item(row, col).text()
            for row in range(identified.rowCount())
            for col in range(identified.columnCount())
        ]
        assert "资产总计" in values
        assert "1,000,000.00" in values
        assert "35" in values
        assert "期末余额" in values
        assert unmapped.rowCount() == 1
        assert unmapped.item(0, 0).text() == "其中：受限货币资金"
