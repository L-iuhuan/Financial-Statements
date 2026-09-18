"""DropdownCombo 组件测试: menu_text 支持与选择行为 (2026-09-18)。"""

from __future__ import annotations

from fsa.gui.widgets.dropdown_combo import DropdownCombo


class TestDropdownComboMenuText:
    """按钮短名 / 菜单全称的双文本支持。"""

    def test_menu_text_defaults_to_text(self, qapp, qtbot) -> None:
        """未指定 menu_text 时菜单文本与按钮一致。"""
        combo = DropdownCombo()
        qtbot.addWidget(combo)
        combo.addItem("甲", "a")
        assert combo._items[0] == ("甲", "a", "甲")

    def test_menu_text_overrides_menu_only(self, qapp, qtbot) -> None:
        """menu_text 只影响菜单展示, 查找/取值仍正常。"""
        combo = DropdownCombo()
        qtbot.addWidget(combo)
        combo.addItem("甲", "a", menu_text="甲（全称）")
        assert combo._items[0][2] == "甲（全称）"
        assert combo.findData("a") == 0
        assert combo.currentData() == "a"

    def test_select_updates_button_and_emits(self, qapp, qtbot) -> None:
        """_select 更新按钮文本、当前项并发信号。"""
        combo = DropdownCombo()
        qtbot.addWidget(combo)
        combo.addItem("甲", "a")
        combo.addItem("乙", "b")
        seen: list[int] = []
        combo.currentIndexChanged.connect(seen.append)
        combo._select(1)
        assert combo.currentIndex() == 1
        assert combo.currentData() == "b"
        assert combo._button.text() == "乙"
        assert seen == [1]
