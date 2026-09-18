"""主体别名配置编辑器区块测试 (offscreen)。"""

from __future__ import annotations

from pathlib import Path
from typing import cast

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLineEdit, QTableWidgetItem

from fsa.gui.pages.settings_page import SettingsPage
from fsa.gui.widgets.arrow_button import ArrowButton
from fsa.gui.widgets.dropdown_combo import DropdownCombo
from fsa.services.entity_config import EntityConfig, load_entity_configs, save_entity_configs


def _write_sample_config(path: Path) -> None:
    save_entity_configs(
        {
            "杭州公司": EntityConfig(
                entity_id="杭州公司",
                tolerance=0.05,
                industry="construction",
                bilateral_tolerance=0.02,
                aliases=("杭州科技有限公司",),
            ),
        },
        path,
    )


class TestEntityConfigSection:
    """多主体配置区块：加载、编辑、保存、字段保留。"""

    def test_save_preserves_unedited_fields(self, qapp, qtbot, app_state, tmp_path) -> None:
        """修改别名/行业/双边容差后保存，未编辑的 tolerance 等字段不被丢弃。"""
        path = tmp_path / "entity_config.json"
        _write_sample_config(path)

        page = SettingsPage(app_state, entity_config_path=path)
        qtbot.addWidget(page)

        table = page._entity_config_table
        assert table.rowCount() == 1
        cast(QTableWidgetItem, table.item(0, 1)).setText("杭州科技有限公司, 杭州科技")
        combo = cast(DropdownCombo, table.cellWidget(0, 2))
        combo.setCurrentIndex(combo.findData("financial"))
        cast(QLineEdit, table.cellWidget(0, 3)).setText("0.03")

        qtbot.mouseClick(page._entity_config_save_btn, Qt.MouseButton.LeftButton)

        reloaded = load_entity_configs(path)["杭州公司"]
        assert reloaded.aliases == ("杭州科技有限公司", "杭州科技")
        assert reloaded.industry == "financial"
        assert reloaded.bilateral_tolerance == 0.03
        assert reloaded.tolerance == 0.05

    def test_chinese_comma_alias_split(self, qapp, qtbot, app_state, tmp_path) -> None:
        """别名输入兼容中英文逗号，并去空格去空项。"""
        path = tmp_path / "entity_config.json"
        _write_sample_config(path)

        page = SettingsPage(app_state, entity_config_path=path)
        qtbot.addWidget(page)

        cast(QTableWidgetItem, page._entity_config_table.item(0, 1)).setText("甲公司，乙公司, , 丙公司")
        qtbot.mouseClick(page._entity_config_save_btn, Qt.MouseButton.LeftButton)

        reloaded = load_entity_configs(path)["杭州公司"]
        assert reloaded.aliases == ("甲公司", "乙公司", "丙公司")

    def test_add_and_delete_row(self, qapp, qtbot, app_state, tmp_path) -> None:
        """新增行并删除行后，表格行数正确变化。"""
        path = tmp_path / "entity_config.json"
        _write_sample_config(path)

        page = SettingsPage(app_state, entity_config_path=path)
        qtbot.addWidget(page)

        table = page._entity_config_table
        buttons = page.findChildren(type(page._entity_config_save_btn))
        add_btn = next(b for b in buttons if b.text() == "新增行")
        del_btn = next(b for b in buttons if b.text() == "删除所选行")

        qtbot.mouseClick(add_btn, Qt.MouseButton.LeftButton)
        assert table.rowCount() == 2

        table.selectRow(1)
        qtbot.mouseClick(del_btn, Qt.MouseButton.LeftButton)
        assert table.rowCount() == 1

    def test_industry_cell_uses_dropdown_combo_with_arrow(
        self, qapp, qtbot, app_state, tmp_path
    ) -> None:
        """行业单元格用 DropdownCombo (自绘箭头), 修复"没有下拉按钮" (2026-09-18)。"""
        path = tmp_path / "entity_config.json"
        _write_sample_config(path)
        page = SettingsPage(app_state, entity_config_path=path)
        qtbot.addWidget(page)

        combo = page._entity_config_table.cellWidget(0, 2)
        assert isinstance(combo, DropdownCombo), "行业下拉必须是 DropdownCombo"
        assert combo.findChild(ArrowButton) is not None, "自绘箭头按钮存在"

    def test_industry_dropdown_short_button_full_menu(
        self, qapp, qtbot, app_state, tmp_path
    ) -> None:
        """按钮显示短名、菜单显示全称 (下拉内容完整)。"""
        path = tmp_path / "entity_config.json"
        _write_sample_config(path)
        page = SettingsPage(app_state, entity_config_path=path)
        qtbot.addWidget(page)

        combo = cast(DropdownCombo, page._entity_config_table.cellWidget(0, 2))
        button_text = {data: text for text, data, _ in combo._items}
        menu_text = {data: menu for _, data, menu in combo._items}
        assert button_text["general"] == "通用"
        assert menu_text["general"] == "通用（默认）"
        assert button_text["cyclical"] == "周期性"
        assert menu_text["cyclical"] == "周期性行业（钢铁/化工/航运等）"

    def test_table_in_layout_and_rows_fit_cell_widgets(
        self, qapp, qtbot, app_state, tmp_path
    ) -> None:
        """表格在布局中可见, 且行高容纳单元格控件 (2026-09-18 穿越行下沿修复)。"""
        path = tmp_path / "entity_config.json"
        _write_sample_config(path)
        page = SettingsPage(app_state, entity_config_path=path)
        qtbot.addWidget(page)
        page.resize(1000, 700)
        page.show()
        qtbot.wait(50)
        table = page._entity_config_table
        assert table.isVisible(), "表格必须在布局中可见 (防漏加布局回归)"
        combo = table.cellWidget(0, 2)
        edit = table.cellWidget(0, 3)
        assert table.rowHeight(0) >= combo.sizeHint().height(), "行高应容纳下拉控件"
        assert table.rowHeight(0) >= edit.sizeHint().height(), "行高应容纳容差控件"
        assert table.rowHeight(0) >= combo.minimumHeight()
        assert table.rowHeight(0) >= edit.minimumHeight()
