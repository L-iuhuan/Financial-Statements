"""导入页进度条显隐测试 (P0-2 / P1-5)。

导入期间显示 IndeterminateProgressBar, 成功/失败/空文件任何退出路径后必须隐藏。
"""

from __future__ import annotations

from fsa.core.exceptions import FSAError
from fsa.core.models.detail import DetailDataset
from fsa.gui.pages.import_page import ImportPage
from tests.gui.helpers import make_report


class TestProgressBarHidden:
    """P0-2: _on_files 任何退出路径都必须隐藏进度条。"""

    def _page(self, app_state) -> ImportPage:
        return ImportPage(app_state)

    def test_hidden_after_successful_import(self, app_state) -> None:
        """导入成功 (识别到报表) 后进度条隐藏。"""
        page = self._page(app_state)
        page._importer.import_file = lambda file_path: [make_report()]
        page._detail_importer.import_file = lambda file_path: DetailDataset(period="2024-12")

        page._on_files(["fake.xlsx"])

        assert page._progress.isHidden()

    def test_hidden_after_all_files_failed(self, app_state) -> None:
        """单文件解析失败 (全部失败) 后进度条隐藏。"""
        page = self._page(app_state)

        def boom(file_path: str) -> list:
            raise FSAError("文件无法解析")

        page._importer.import_file = boom
        page._detail_importer.import_file = lambda file_path: DetailDataset(period="2024-12")

        page._on_files(["broken.xlsx"])

        assert page._progress.isHidden()

    def test_hidden_after_unrecognized_empty_files(self, app_state) -> None:
        """未识别到任何报表/明细数据 (空文件) 后进度条隐藏。"""
        page = self._page(app_state)
        page._importer.import_file = lambda file_path: []
        page._detail_importer.import_file = lambda file_path: DetailDataset(period="2024-12")

        page._on_files(["empty.xlsx"])

        assert page._progress.isHidden()

    def test_hidden_after_missing_file(self, app_state) -> None:
        """文件不存在 (FileNotFoundError) 后进度条隐藏。"""
        page = self._page(app_state)

        def not_found(file_path: str) -> list:
            raise FileNotFoundError(file_path)

        page._importer.import_file = not_found
        page._detail_importer.import_file = lambda file_path: DetailDataset(period="2024-12")

        page._on_files(["nope.xlsx"])

        assert page._progress.isHidden()
