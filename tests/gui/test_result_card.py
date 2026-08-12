"""ResultCard 结果卡片测试。"""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QTableWidget

from fsa.core.models.result import TraceItem, ValidationResult
from fsa.core.models.rule import Severity
from fsa.gui.widgets.result_card import ResultCard


class TestResultCardTrace:
    """测试 trace 表格。"""

    def test_trace_table_populated(self, qapp, qtbot) -> None:
        """trace 数据正确填充到表格。"""
        trace = [
            TraceItem(key="a", name="资产", amount=100.0, row=5, column="期末余额", side="left"),
            TraceItem(key="b", name="负债", amount=60.0, row=10, column="期末余额", side="right"),
        ]
        result = ValidationResult(
            rule_id="R-001",
            rule_name="测试",
            passed=False,
            severity=Severity.ERROR,
            left_value=100.0,
            right_value=90.0,
            diff=10.0,
            tolerance=0.01,
            formula="a == b",
            message="差额超限",
            category="A-表内平衡",
            trace=trace,
        )
        card = ResultCard(result)
        qtbot.addWidget(card)

        table = card.findChild(QTableWidget, "TraceTable")
        assert table is not None
        assert table.rowCount() == 2
        assert table.item(0, 0).text() == "资产"
        assert table.item(0, 2).text() == "左"
        assert table.item(1, 2).text() == "右"
        assert "行5" in table.item(0, 3).text()

    def test_no_trace_no_table(self, qapp, qtbot) -> None:
        """无 trace 时不创建表格。"""
        result = ValidationResult(
            rule_id="R-001",
            rule_name="测试",
            passed=True,
            severity=Severity.ERROR,
            left_value=100.0,
            right_value=100.0,
            diff=0.0,
            tolerance=0.01,
            formula="a == b",
            message="",
            category="A-表内平衡",
            trace=[],
        )
        card = ResultCard(result)
        qtbot.addWidget(card)
        table = card.findChild(QTableWidget, "TraceTable")
        assert table is None

    def test_category_shown_in_header(self, qapp, qtbot) -> None:
        """分类显示在卡片头部。"""
        result = ValidationResult(
            rule_id="R-001",
            rule_name="测试",
            passed=True,
            severity=Severity.ERROR,
            left_value=100.0,
            right_value=100.0,
            diff=0.0,
            tolerance=0.01,
            formula="a == b",
            message="",
            category="A-表内平衡",
            trace=[],
        )
        card = ResultCard(result)
        qtbot.addWidget(card)
        # 头部应包含分类文本的 MetaLabel
        labels = card.findChildren(QLabel)
        texts = [lbl.text() for lbl in labels]
        assert "A-表内平衡" in texts
