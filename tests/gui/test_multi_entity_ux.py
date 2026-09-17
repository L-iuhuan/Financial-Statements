"""多主体批量校验对话框 UX 测试。"""

from __future__ import annotations

from PySide6.QtWidgets import QLabel

from fsa.core.models.rule import Severity
from fsa.gui.widgets.multi_entity_dialog import MultiEntityResultDialog
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
