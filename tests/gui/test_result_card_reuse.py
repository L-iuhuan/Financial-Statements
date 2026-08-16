"""ResultCard 更新与复用测试 (FIX 2)。

覆盖:
- ResultCard.update_result 刷新所有字段
- _rebuild_cards 相同规则集时复用卡片
- _rebuild_cards 不同规则集时重建卡片
- 复用后筛选可见性保持正确
"""

from __future__ import annotations

from PySide6.QtWidgets import QTableWidget

from fsa.core.models.result import TraceItem, ValidationResult
from fsa.core.models.rule import Severity
from fsa.gui.pages.import_page import ImportPage
from fsa.gui.widgets.result_card import ResultCard
from tests.gui.helpers import make_result, make_summary


class TestResultCardUpdate:
    """ResultCard.update_result 刷新所有展示字段。"""

    def test_update_result_refreshes_status(self, qapp, qtbot) -> None:
        """update_result 后状态标签更新。"""
        result1 = make_result("A-001", passed=True, severity=Severity.ERROR)
        card = ResultCard(result1)
        qtbot.addWidget(card)

        assert card._status_label.text() == "通过"

        result2 = make_result("A-001", passed=False, severity=Severity.ERROR, diff=5.0)
        card.update_result(result2)
        assert card._status_label.text() == "不通过"
        assert card._status == "fail"

    def test_update_result_refreshes_detail_values(self, qapp, qtbot) -> None:
        """update_result 后详情数值更新。"""
        result1 = ValidationResult(
            rule_id="A-001",
            rule_name="测试规则",
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
        card = ResultCard(result1)
        qtbot.addWidget(card)

        result2 = ValidationResult(
            rule_id="A-001",
            rule_name="测试规则",
            passed=False,
            severity=Severity.ERROR,
            left_value=200.0,
            right_value=150.0,
            diff=50.0,
            tolerance=0.05,
            formula="x == y",
            message="差额过大",
            category="A-表内平衡",
            trace=[
                TraceItem(key="a", name="资产", amount=200.0, row=5, column="期末余额", side="left"),
            ],
        )
        card.update_result(result2)

        # 详情应已更新
        assert card._result.diff == 50.0
        assert card._result.tolerance == 0.05
        assert card._result.formula == "x == y"
        assert card._result.message == "差额过大"

    def test_update_result_refreshes_trace_table(self, qapp, qtbot) -> None:
        """update_result 后 trace 表格更新。"""
        result1 = make_result("A-001", passed=True, severity=Severity.ERROR)
        card = ResultCard(result1)
        qtbot.addWidget(card)

        # 无 trace 时无表格
        table1 = card.findChild(QTableWidget, "TraceTable")
        assert table1 is None

        result2 = ValidationResult(
            rule_id="A-001",
            rule_name="测试规则",
            passed=False,
            severity=Severity.ERROR,
            left_value=200.0,
            right_value=150.0,
            diff=50.0,
            tolerance=0.01,
            formula="a == b",
            message="",
            category="A-表内平衡",
            trace=[
                TraceItem(key="a", name="资产", amount=200.0, row=5, column="期末余额", side="left"),
            ],
        )
        card.update_result(result2)

        table2 = card.findChild(QTableWidget, "TraceTable")
        assert table2 is not None
        assert table2.rowCount() == 1
        assert table2.item(0, 0).text() == "资产"

    def test_update_result_resets_expansion(self, qapp, qtbot) -> None:
        """update_result 后展开状态根据 passed 重置。"""
        result_pass = make_result("A-001", passed=True, severity=Severity.ERROR)
        card = ResultCard(result_pass)
        qtbot.addWidget(card)

        # 通过结果默认收起
        assert card._expanded is False
        assert card._detail.isHidden()

        result_fail = make_result("A-001", passed=False, severity=Severity.ERROR, diff=5.0)
        card.update_result(result_fail)
        # 不通过结果默认展开
        assert card._expanded is True
        assert not card._detail.isHidden()

    def test_update_result_preserves_signal_connections(self, qapp, qtbot) -> None:
        """update_result 后信号连接保持不变。"""
        result1 = make_result("A-001", passed=False, severity=Severity.ERROR, diff=1.0)
        card = ResultCard(result1)
        qtbot.addWidget(card)

        received: list[str] = []
        card.diagnose_clicked.connect(lambda rid: received.append(rid))

        result2 = make_result("A-001", passed=False, severity=Severity.ERROR, diff=5.0)
        card.update_result(result2)

        card.diagnose_clicked.emit("A-001")
        assert received == ["A-001"]


class TestRebuildCardsReuse:
    """import_page_results._rebuild_cards 卡片复用逻辑。"""

    def _setup_page_with_results(
        self, qapp, app_state, results: list[ValidationResult]
    ) -> ImportPage:
        page = ImportPage(app_state)
        summary = make_summary(results)
        app_state.set_results(summary)
        return page

    def test_rebuild_cards_reuses_when_same_rule_ids(self, qapp, qtbot, app_state) -> None:
        """相同规则集 (相同 rule_id 顺序) 时复用卡片。"""
        results1 = [
            make_result("A-001", passed=True, severity=Severity.ERROR),
            make_result("B-001", passed=False, severity=Severity.WARNING, diff=1.0),
            make_result("C-001", passed=False, severity=Severity.ERROR, diff=2.0),
        ]
        page = ImportPage(app_state)
        qtbot.addWidget(page)
        app_state.set_results(make_summary(results1))

        cards_first = [card for _, card in page._result_cards]
        assert len(cards_first) == 3

        # 相同规则集再次校验
        results2 = [
            make_result("A-001", passed=False, severity=Severity.ERROR, diff=0.5),
            make_result("B-001", passed=True, severity=Severity.WARNING),
            make_result("C-001", passed=False, severity=Severity.ERROR, diff=3.0),
        ]
        app_state.set_results(make_summary(results2))

        cards_second = [card for _, card in page._result_cards]
        assert len(cards_second) == 3

        # 应复用同一批卡片对象
        for i in range(3):
            assert cards_second[i] is cards_first[i], f"卡片 #{i} 应复用"

    def test_rebuild_cards_rebuilds_when_different_rule_ids(self, qapp, qtbot, app_state) -> None:
        """不同规则集时重建卡片。"""
        results1 = [
            make_result("A-001", passed=True, severity=Severity.ERROR),
            make_result("B-001", passed=False, severity=Severity.WARNING, diff=1.0),
        ]
        page = ImportPage(app_state)
        qtbot.addWidget(page)
        app_state.set_results(make_summary(results1))

        cards_first = [card for _, card in page._result_cards]
        assert len(cards_first) == 2

        # 不同规则集
        results2 = [
            make_result("A-001", passed=False, severity=Severity.ERROR, diff=0.5),
            make_result("C-001", passed=True, severity=Severity.ERROR),  # 不同 rule_id
        ]
        app_state.set_results(make_summary(results2))

        cards_second = [card for _, card in page._result_cards]
        assert len(cards_second) == 2

        # 不应复用 (rule_ids 不同)
        assert cards_second[0] is not cards_first[0], "不同 rule_id 应重建"

    def test_rebuild_cards_rebuilds_when_different_count(self, qapp, qtbot, app_state) -> None:
        """不同结果数量时重建卡片。"""
        results1 = [
            make_result("A-001", passed=True, severity=Severity.ERROR),
            make_result("B-001", passed=False, severity=Severity.WARNING, diff=1.0),
        ]
        page = ImportPage(app_state)
        qtbot.addWidget(page)
        app_state.set_results(make_summary(results1))

        cards_first = [card for _, card in page._result_cards]
        assert len(cards_first) == 2

        results2 = [
            make_result("A-001", passed=False, severity=Severity.ERROR, diff=0.5),
        ]
        app_state.set_results(make_summary(results2))

        cards_second = [card for _, card in page._result_cards]
        assert len(cards_second) == 1

        # 不同数量应重建
        assert cards_second[0] is not cards_first[0], "不同数量应重建"

    def test_reuse_preserves_filter_visibility(self, qapp, qtbot, app_state) -> None:
        """复用卡片后筛选可见性保持正确。"""
        results1 = [
            make_result("A-001", passed=True, severity=Severity.ERROR),
            make_result("B-001", passed=False, severity=Severity.WARNING, diff=1.0),
        ]
        page = ImportPage(app_state)
        qtbot.addWidget(page)
        app_state.set_results(make_summary(results1))

        page._current_filter = "pass"
        page._apply_filter()

        visible_ids = [
            r.rule_id for r, card in page._result_cards if not card.isHidden()
        ]
        assert visible_ids == ["A-001"]

        # 相同规则集，update 后筛选仍生效
        results2 = [
            make_result("A-001", passed=False, severity=Severity.ERROR, diff=0.5),
            make_result("B-001", passed=True, severity=Severity.WARNING),
        ]
        app_state.set_results(make_summary(results2))

        visible_ids2 = [
            r.rule_id for r, card in page._result_cards if not card.isHidden()
        ]
        assert visible_ids2 == ["B-001"]  # B-001 现在是 pass
