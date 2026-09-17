"""主体选择对话框与 import_page_tasks 接线测试 (offscreen)。"""

from __future__ import annotations

from typing import cast

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QListWidgetItem

from fsa.gui.pages.import_page import ImportPage
from fsa.gui.widgets.entity_select_dialog import EntitySelectDialog


class TestEntitySelectDialog:
    """EntitySelectDialog 自身行为。"""

    def test_defaults_all_checked(self, qapp, qtbot) -> None:
        """默认全部勾选，selected_entities 顺序与入参一致。"""
        dialog = EntitySelectDialog(["A", "B", "C"])
        qtbot.addWidget(dialog)

        assert dialog.selected_entities() == ["A", "B", "C"]

    def test_select_none_disables_ok(self, qapp, qtbot) -> None:
        """全不选后计数为 0，Ok 按钮禁用。"""
        dialog = EntitySelectDialog(["A", "B"])
        qtbot.addWidget(dialog)

        dialog._select_none()

        assert dialog.selected_entities() == []
        assert not dialog._buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled()
        assert "已选 0 / 2 个主体" in dialog._count_label.text()

    def test_select_all_restores_ok(self, qapp, qtbot) -> None:
        """全不选后再全选，Ok 恢复启用。"""
        dialog = EntitySelectDialog(["A", "B"])
        qtbot.addWidget(dialog)

        dialog._select_none()
        dialog._select_all()

        assert dialog.selected_entities() == ["A", "B"]
        assert dialog._buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled()
        assert "已选 2 / 2 个主体" in dialog._count_label.text()

    def test_reject_does_not_crash_selected_entities(self, qapp, qtbot) -> None:
        """取消后仍可调用 selected_entities 不崩溃。"""
        dialog = EntitySelectDialog(["A", "B"])
        qtbot.addWidget(dialog)

        dialog._select_none()
        dialog.reject()

        assert dialog.selected_entities() == []

    def test_uncheck_item_updates_count_and_ok(self, qapp, qtbot) -> None:
        """手动取消勾选一项，计数与 Ok 状态同步。"""
        dialog = EntitySelectDialog(["A", "B"])
        qtbot.addWidget(dialog)

        item = cast(QListWidgetItem, dialog._list.item(0))
        item.setCheckState(Qt.CheckState.Unchecked)

        assert dialog.selected_entities() == ["B"]
        assert dialog._buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled()
        assert "已选 1 / 2 个主体" in dialog._count_label.text()

    def test_descriptions_set_tooltips(self, qapp, qtbot) -> None:
        """descriptions 中的值会设为对应项的 tooltip。"""
        dialog = EntitySelectDialog(["A", "B"], descriptions={"A": "甲公司"})
        qtbot.addWidget(dialog)

        assert dialog._list.item(0).toolTip() == "甲公司"
        assert dialog._list.item(1).toolTip() == ""


class _StubEntitySelectDialog:
    """用于 monkeypatch 的桩对话框。"""

    def __init__(
        self,
        result_code: QDialog.DialogCode,
        selected: list[str],
    ) -> None:
        self.result_code = result_code
        self.selected = selected
        self.captured_entities: list[str] | None = None
        self.captured_descriptions: dict[str, str] | None = None

    def __call__(
        self,
        entities: list[str],
        descriptions: dict[str, str] | None = None,
        parent: object | None = None,
    ) -> _StubEntitySelectDialog:
        self.captured_entities = entities
        self.captured_descriptions = descriptions
        return self

    def exec(self) -> QDialog.DialogCode:
        return self.result_code

    def selected_entities(self) -> list[str]:
        return self.selected


class TestPickEntitiesForMulti:
    """_pick_entities_for_multi 可测辅助方法。"""

    def test_returns_selected_subset_paths(self, qapp, qtbot, app_state, tmp_path, monkeypatch) -> None:
        """勾选子集时返回对应完整路径，顺序与勾选一致。"""
        for name in ("A", "B", "C"):
            (tmp_path / name).mkdir()

        page = ImportPage(app_state)
        qtbot.addWidget(page)

        stub = _StubEntitySelectDialog(QDialog.DialogCode.Accepted, ["B", "A"])
        monkeypatch.setattr(
            "fsa.gui.widgets.entity_select_dialog.EntitySelectDialog",
            stub,
        )

        result = page._pick_entities_for_multi(str(tmp_path))

        assert result == [str(tmp_path / "B"), str(tmp_path / "A")]
        assert stub.captured_entities == ["A", "B", "C"]

    def test_cancel_returns_none(self, qapp, qtbot, app_state, tmp_path, monkeypatch) -> None:
        """对话框取消时返回 None。"""
        for name in ("A", "B"):
            (tmp_path / name).mkdir()

        page = ImportPage(app_state)
        qtbot.addWidget(page)

        stub = _StubEntitySelectDialog(QDialog.DialogCode.Rejected, [])
        monkeypatch.setattr(
            "fsa.gui.widgets.entity_select_dialog.EntitySelectDialog",
            stub,
        )

        assert page._pick_entities_for_multi(str(tmp_path)) is None

    def test_empty_folders_returns_none(self, qapp, qtbot, app_state, tmp_path, monkeypatch) -> None:
        """目录下无子文件夹时返回 None。"""
        page = ImportPage(app_state)
        qtbot.addWidget(page)
        messages: list[tuple[str, str]] = []
        monkeypatch.setattr(page, "_show_info", lambda msg, kind="info": messages.append((msg, kind)))

        assert page._pick_entities_for_multi(str(tmp_path)) is None
        assert ("所选目录下没有主体子文件夹", "warning") in messages

    def test_empty_selection_returns_none(self, qapp, qtbot, app_state, tmp_path, monkeypatch) -> None:
        """用户未勾选任何主体时返回 None。"""
        for name in ("A", "B"):
            (tmp_path / name).mkdir()

        page = ImportPage(app_state)
        qtbot.addWidget(page)

        stub = _StubEntitySelectDialog(QDialog.DialogCode.Accepted, [])
        monkeypatch.setattr(
            "fsa.gui.widgets.entity_select_dialog.EntitySelectDialog",
            stub,
        )

        assert page._pick_entities_for_multi(str(tmp_path)) is None
