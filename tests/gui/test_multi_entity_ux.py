"""多主体批量校验对话框 UX 测试。"""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QTableWidget

from fsa.core.models.result import ValidationResult, ValidationSummary
from fsa.core.models.rule import Severity
from fsa.gui.widgets.multi_entity_dialog import (
    EntityDetailDialog,
    MultiEntityResultDialog,
)
from fsa.services.multi_entity_service import EntityOutcome, MultiEntityResult
from tests.gui.helpers import make_result, make_summary


def _make_multi_result() -> MultiEntityResult:
    """构造两个主体, 各含通过/不通过/异常各一条的批量结果。"""
    outcomes = [
        EntityOutcome(
            entity_id="甲公司",
            folder="D:/data/甲公司",
            summary=make_summary(
                [
                    make_result("A-001", passed=True, severity=Severity.ERROR),
                    make_result("B-001", passed=False, severity=Severity.ERROR, diff=1.0),
                    make_result("C-001", passed=False, errored=True, severity=Severity.ERROR),
                ]
            ),
        ),
        EntityOutcome(
            entity_id="乙公司",
            folder="D:/data/乙公司",
            summary=make_summary(
                [
                    make_result("A-002", passed=True, severity=Severity.ERROR),
                    make_result("B-002", passed=False, severity=Severity.ERROR, diff=2.0),
                    make_result("C-002", passed=False, errored=True, severity=Severity.ERROR),
                ]
            ),
        ),
    ]
    return MultiEntityResult(
        outcomes=outcomes,
        combined=make_summary([make_result()]),
        bilateral=[],
    )


class TestMultiEntityDialogTotals:
    """头部合计应逐主体相加, 而非使用 result.combined 的去重值。"""

    def test_header_shows_sum_of_entities(self, qapp, qtbot) -> None:
        """两主体各 3 条结果, 通过/不通过/异常均为 2。"""
        dialog = MultiEntityResultDialog(_make_multi_result())
        qtbot.addWidget(dialog)

        labels = dialog.findChildren(QLabel)
        header = next(
            label for label in labels if "合计（全部主体）" in label.text()
        )
        assert "共 6 条校验结果" in header.text()
        assert "通过 2" in header.text()
        assert "不通过 2" in header.text()
        assert "异常 2" in header.text()

        subtitles = [label.text() for label in labels]
        assert any("合计 = 各主体校验结果之和" in text for text in subtitles)

    def test_no_successful_entity_shows_plain_message(self, qapp, qtbot) -> None:
        """所有主体 summary 为空时显示无成功完成提示。"""
        result = MultiEntityResult(
            outcomes=[
                EntityOutcome(
                    entity_id="A", folder="fA", summary=None, errors=["读取失败"]
                )
            ]
        )
        dialog = MultiEntityResultDialog(result)
        qtbot.addWidget(dialog)

        labels = dialog.findChildren(QLabel)
        assert any("没有主体成功完成校验" in label.text() for label in labels)

    def test_dialog_is_non_modal_by_default(self, qapp, qtbot) -> None:
        """对话框以 show() 打开, 不阻塞主窗口。"""
        dialog = MultiEntityResultDialog(_make_multi_result())
        qtbot.addWidget(dialog)

        dialog.show()
        assert dialog.isVisible()
        assert not dialog.isModal()


class TestEntityTableCompleteness:
    """主体表 7 列 (含跳过), 头部数字完整 (2026-09-18 目验修复)。"""

    def test_entity_table_has_seven_columns(self, qapp, qtbot) -> None:
        """列: 主体/报表数/通过/不通过/异常/跳过/导入错误。"""
        outcome = EntityOutcome(
            entity_id="甲公司",
            folder="fA",
            summary=make_summary([make_result()]),
        )
        dialog = MultiEntityResultDialog(MultiEntityResult(outcomes=[outcome]))
        qtbot.addWidget(dialog)
        table = dialog.findChild(QTableWidget)
        assert table is not None
        assert table.columnCount() == 7

    def test_header_includes_skipped_count(self, qapp, qtbot) -> None:
        """含跳过结果时头部显示 跳过 N（缺数据）, 数字加总完整。"""
        skipped = ValidationResult(
            rule_id="S-001", rule_name="缺数据规则", passed=True,
            severity=Severity.ERROR, left_value=0.0, right_value=0.0,
            diff=0.0, tolerance=0.01, formula="", message="跳过", skipped=True,
        )
        summary = ValidationSummary(
            period="2026-05", total=2, passed=1, failed=0, errored=0,
            skipped=1, results=[make_result("A-001", passed=True), skipped],
        )
        dialog = MultiEntityResultDialog(
            MultiEntityResult(
                outcomes=[EntityOutcome(entity_id="甲", folder="f", summary=summary)]
            )
        )
        qtbot.addWidget(dialog)
        header = next(
            label for label in dialog.findChildren(QLabel)
            if "合计（全部主体）" in label.text()
        )
        assert "跳过 1（缺数据）" in header.text()


class TestEntityDetailDrillDown:
    """双击主体行下钻未通过明细 (问题回看 + 不通过原因)。"""

    def test_double_click_opens_detail_with_non_passed(self, qapp, qtbot) -> None:
        """双击主体行 → 打开明细对话框, 只列非通过项。"""
        summary = make_summary(
            [
                make_result("A-001", passed=True),
                make_result("B-001", passed=False, diff=1.0),
                make_result("C-001", passed=False, errored=True),
            ]
        )
        outcome = EntityOutcome(entity_id="甲公司", folder="fA", summary=summary)
        dialog = MultiEntityResultDialog(MultiEntityResult(outcomes=[outcome]))
        qtbot.addWidget(dialog)

        entity_table = dialog.findChild(QTableWidget)
        assert entity_table is not None
        entity_table.cellDoubleClicked.emit(0, 0)

        details = dialog.findChildren(EntityDetailDialog)
        assert details, "双击应打开主体明细对话框"
        detail_tables = details[0].findChildren(QTableWidget)
        assert detail_tables, "明细对话框应含明细表"
        assert detail_tables[0].rowCount() == 2, "只列非通过项 (B-001 与 C-001)"

    def test_all_passed_shows_empty_hint(self, qapp, qtbot) -> None:
        """全部通过的主体显示无问题提示。"""
        outcome = EntityOutcome(
            entity_id="乙公司",
            folder="fB",
            summary=make_summary([make_result("A-001", passed=True)]),
        )
        dialog = EntityDetailDialog(outcome)
        qtbot.addWidget(dialog)
        labels = [label.text() for label in dialog.findChildren(QLabel)]
        assert any("无未通过项" in text for text in labels)


class TestLastMultiResultButton:
    """「上次批量结果」按钮: 完成后可见, 点击可重开结果 (问题回看)。"""

    def test_button_hidden_until_first_finish(
        self, qapp, qtbot, app_state, monkeypatch
    ) -> None:
        from fsa.gui.pages.import_page import ImportPage

        page = ImportPage(app_state)
        qtbot.addWidget(page)
        assert page._last_multi_btn.isHidden(), "初始隐藏"

        result = MultiEntityResult(
            outcomes=[
                EntityOutcome(
                    entity_id="A",
                    folder="fA",
                    summary=make_summary([make_result()]),
                )
            ]
        )
        monkeypatch.setattr(page, "_persist_multi_entity_results", lambda payload: 1)
        page._on_multi_entity_finished(result)

        assert not page._last_multi_btn.isHidden(), "完成后可见"
        assert page._last_multi_result is result

        page._on_view_last_multi_result()  # 重开不崩溃
        page._last_multi_result = None
        page._on_view_last_multi_result()  # 无结果时也不崩溃


class TestProgressElapsedSuffix:
    """进度消息带已用时长后缀 (大文件读取 50s+ 期间仍有活动反馈)。"""

    def test_progress_message_shows_elapsed(self, qapp, qtbot, app_state) -> None:
        from fsa.gui.pages.import_page import ImportPage

        page = ImportPage(app_state)
        qtbot.addWidget(page)
        page._set_progress_message("正在导入文件")
        text = page._import_status_label.text()
        assert text.startswith("正在导入文件")
        assert "已用" in text, "应带已用时长后缀"
