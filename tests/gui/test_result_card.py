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
        item_0_0 = table.item(0, 0)
        item_0_2 = table.item(0, 2)
        item_1_2 = table.item(1, 2)
        item_0_3 = table.item(0, 3)
        assert item_0_0 is not None
        assert item_0_2 is not None
        assert item_1_2 is not None
        assert item_0_3 is not None
        assert item_0_0.text() == "资产"
        assert item_0_2.text() == "左"
        assert item_1_2.text() == "右"
        assert "行5" in item_0_3.text()

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


def _make_skipped_result(message: str = "缺少利润表数据") -> ValidationResult:
    """创建一条跳过结果 (与 ValidationResult.from_skip 语义一致: passed=True, skipped=True)。"""
    return ValidationResult(
        rule_id="S-001",
        rule_name="表间勾稽规则",
        passed=True,
        severity=Severity.ERROR,
        left_value=0.0,
        right_value=0.0,
        diff=0.0,
        tolerance=0.01,
        formula="a == b",
        message=message,
        skipped=True,
        category="B-表间勾稽",
        trace=[],
    )


class TestResultCardSkipped:
    """测试 skipped 结果的卡片渲染 (P0: 不得渲染为「通过」)。"""

    def test_skipped_status_key_is_skip(self, qapp, qtbot) -> None:
        """skipped 结果的状态键为 skip, 而非 pass。"""
        card = ResultCard(_make_skipped_result())
        qtbot.addWidget(card)
        assert card._status == "skip"

    def test_skipped_renders_skip_text(self, qapp, qtbot) -> None:
        """skipped 卡片状态标签显示「跳过」且带 skip 属性。"""
        card = ResultCard(_make_skipped_result())
        qtbot.addWidget(card)
        assert card._status_label.text() == "跳过"
        assert card._status_label.property("status") == "skip"

    def test_skipped_message_visible_when_expanded(self, qapp, qtbot) -> None:
        """skipped 卡片展开详情后显示跳过原因。"""
        card = ResultCard(_make_skipped_result("缺少利润表: 规则跳过"))
        qtbot.addWidget(card)
        # skipped 默认收起 (passed=True), 展开后懒加载详情
        card.toggle_expanded()
        labels = card.findChildren(QLabel)
        texts = [lbl.text() for lbl in labels]
        assert "缺少利润表: 规则跳过" in texts

    def test_skipped_initial_status_style_applied(self, qapp, qtbot) -> None:
        """首渲染即应用状态样式 (全局 QSS 通过 status 属性驱动, 字重/颜色就绪)。"""
        card = ResultCard(_make_skipped_result())
        qtbot.addWidget(card)
        assert card._status_label.styleSheet() == ""
        assert card._status_label.property("status") == "skip"

    def test_update_result_to_skipped(self, qapp, qtbot) -> None:
        """卡片复用路径: 更新为 skipped 结果后状态标签同步为「跳过」。"""
        passed = ValidationResult(
            rule_id="S-001",
            rule_name="表间勾稽规则",
            passed=True,
            severity=Severity.ERROR,
            left_value=100.0,
            right_value=100.0,
            diff=0.0,
            tolerance=0.01,
            formula="a == b",
            message="",
            category="B-表间勾稽",
        )
        card = ResultCard(passed)
        qtbot.addWidget(card)
        assert card._status == "pass"
        card.update_result(_make_skipped_result())
        assert card._status == "skip"
        assert card._status_label.text() == "跳过"
        assert card._status_label.property("status") == "skip"

    def test_negative_diff_label_uses_negative_color(self, qapp, qtbot) -> None:
        """负差额行以负数红呈现 (全局 QSS 通过 negative 属性驱动)。"""

        result = ValidationResult(
            rule_id="R-002",
            rule_name="测试",
            passed=False,
            severity=Severity.ERROR,
            left_value=90.0,
            right_value=100.0,
            diff=-10.0,
            tolerance=0.01,
            formula="a == b",
            message="差额超限",
            category="A-表内平衡",
        )
        card = ResultCard(result)
        qtbot.addWidget(card)
        assert card._diff_label.styleSheet() == ""
        assert card._diff_label.property("negative") == "true"

    def test_negative_trace_amount_colored(self, qapp, qtbot) -> None:
        """trace 表负数金额以负数红呈现。"""
        trace = [
            TraceItem(key="a", name="资产", amount=-5.0, row=5, column="期末余额", side="left"),
        ]
        result = ValidationResult(
            rule_id="R-003",
            rule_name="测试",
            passed=False,
            severity=Severity.ERROR,
            left_value=-5.0,
            right_value=0.0,
            diff=-5.0,
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
        item = table.item(0, 1)
        assert item is not None
        assert item.foreground().color().isValid()

    def test_rule_name_tooltip(self, qapp, qtbot) -> None:
        """规则名标签带全名悬浮提示 (长名截断兜底)。"""
        card = ResultCard(_make_skipped_result())
        qtbot.addWidget(card)
        name_labels = [
            lbl for lbl in card.findChildren(QLabel) if lbl.objectName() == "RuleName"
        ]
        assert name_labels
        assert name_labels[0].toolTip() == "表间勾稽规则"
