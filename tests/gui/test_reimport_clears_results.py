"""B1-2: 重新导入新批次报表后旧校验结果必须清空。"""

from __future__ import annotations

from fsa.core.models.detail import DetailDataset
from fsa.gui.pages.import_page import ImportPage
from tests.gui.helpers import make_report, make_result, make_summary


class TestReimportClearsResults:
    """重复导入场景: 旧结果不再残留, 防止旧底稿被误导出。"""

    def test_reimport_clears_previous_results(self, qapp, qtbot, app_state) -> None:
        """已有校验结果时, 新批次导入成功后 results 变为 None。"""
        page = ImportPage(app_state)
        qtbot.addWidget(page)
        app_state.set_results(make_summary([make_result()]), persist=False)
        assert app_state.results is not None

        page._apply_import_result(
            ["test.xlsx"],
            [make_report()],
            DetailDataset(period="2024-12"),
            [],
        )

        assert app_state.results is None

    def test_failed_import_keeps_previous_results(self, qapp, qtbot, app_state) -> None:
        """导入未识别到任何数据时, 不清空已有校验结果。"""
        page = ImportPage(app_state)
        qtbot.addWidget(page)
        app_state.set_results(make_summary([make_result()]), persist=False)

        page._apply_import_result(
            ["bad.xlsx"],
            [],
            DetailDataset(period="2024-12"),
            ["bad.xlsx: 文件不存在"],
        )

        assert app_state.results is not None
