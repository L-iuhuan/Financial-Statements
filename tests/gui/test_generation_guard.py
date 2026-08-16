"""B1-1 后台任务代际守卫测试: 重置/取消后迟到的旧结果被丢弃。"""

from __future__ import annotations

import threading

from fsa.core.models.detail import DetailDataset
from fsa.gui.pages.import_page import ImportPage
from tests.gui.helpers import make_report, make_result, make_summary


def _make_import_payload(generation: int) -> dict[str, object]:
    """构造一份后台导入完成载荷。"""
    return {
        "generation": generation,
        "file_paths": ["a.xlsx"],
        "reports": [make_report()],
        "dataset": DetailDataset(period="2024-12"),
        "errors": [],
    }


class TestImportGenerationGuard:
    """后台导入完成回调的代际比对。"""

    def test_stale_import_result_discarded(self, qapp, qtbot, app_state) -> None:
        """重置推进代际后, 旧导入结果不写回 AppState。"""
        page = ImportPage(app_state)
        qtbot.addWidget(page)
        page._import_generation = 3

        page._on_background_import_finished(_make_import_payload(2))

        assert app_state.reports == []

    def test_current_import_result_applied(self, qapp, qtbot, app_state) -> None:
        """代际一致时导入结果正常写回。"""
        page = ImportPage(app_state)
        qtbot.addWidget(page)
        page._import_generation = 3

        page._on_background_import_finished(_make_import_payload(3))

        assert len(app_state.reports) == 1

    def test_stale_import_failure_silent(self, qapp, qtbot, app_state) -> None:
        """过期失败通知只恢复运行状态, 不弹错误。"""
        page = ImportPage(app_state)
        qtbot.addWidget(page)
        page._import_generation = 2
        page._set_import_running(True)

        page._on_background_import_failed("网络错误", generation=1)

        assert page._import_cancel_event is None


class TestValidationGenerationGuard:
    """后台校验完成回调的代际比对。"""

    def test_stale_validation_result_discarded(self, qapp, qtbot, app_state) -> None:
        """重置推进代际后, 旧校验结果不写回 AppState。"""
        page = ImportPage(app_state)
        qtbot.addWidget(page)
        page._validation_generation = 5

        page._on_background_validation_finished(make_summary([make_result()]), generation=4)

        assert app_state.results is None
        assert page._validation_running is False

    def test_current_validation_result_applied(self, qapp, qtbot, app_state) -> None:
        """代际一致时校验结果正常写回。"""
        page = ImportPage(app_state)
        qtbot.addWidget(page)
        page._validation_generation = 5
        summary = make_summary([make_result()])

        page._on_background_validation_finished(summary, generation=5)

        assert app_state.results is summary


class TestMultiGenerationGuard:
    """多主体批量校验完成回调的代际比对。"""

    def test_stale_multi_result_discarded(self, qapp, qtbot, app_state) -> None:
        """重置推进代际后, 旧批量结果不落库不弹窗。"""
        from fsa.services.multi_entity_service import EntityOutcome, MultiEntityResult

        page = ImportPage(app_state)
        qtbot.addWidget(page)
        page._multi_generation = 2
        result = MultiEntityResult(
            outcomes=[EntityOutcome(entity_id="A", folder="fA", summary=make_summary([make_result()]))]
        )

        page._on_multi_entity_finished(result, generation=1)

        assert page._multi_running is False


class TestInvalidateBackgroundTasks:
    """invalidate_background_tasks: 重置入口的代际推进 + 取消请求。"""

    def test_invalidate_bumps_all_generations(self, qapp, qtbot, app_state) -> None:
        """三类任务代际同时推进。"""
        page = ImportPage(app_state)
        qtbot.addWidget(page)
        before = (page._import_generation, page._validation_generation, page._multi_generation)

        page.invalidate_background_tasks()

        assert page._import_generation == before[0] + 1
        assert page._validation_generation == before[1] + 1
        assert page._multi_generation == before[2] + 1

    def test_invalidate_sets_cancel_events(self, qapp, qtbot, app_state) -> None:
        """进行中的任务取消事件被置位。"""
        page = ImportPage(app_state)
        qtbot.addWidget(page)
        page._import_cancel_event = threading.Event()
        page._validation_cancel_event = threading.Event()
        page._multi_cancel_event = threading.Event()

        page.invalidate_background_tasks()

        assert page._import_cancel_event.is_set()
        assert page._validation_cancel_event.is_set()
        assert page._multi_cancel_event.is_set()

    def test_cancel_bumps_generation(self, qapp, qtbot, app_state) -> None:
        """取消按钮路径推进对应任务代际。"""
        page = ImportPage(app_state)
        qtbot.addWidget(page)
        page._validation_cancel_event = threading.Event()
        before = page._validation_generation

        page._cancel_import()

        assert page._validation_generation == before + 1
        assert page._validation_cancel_event.is_set()
