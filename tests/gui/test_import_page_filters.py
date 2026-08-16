"""ImportPage 筛选逻辑测试。"""

from __future__ import annotations

import pytest

from fsa.core.models.result import ValidationResult, ValidationSummary
from fsa.core.models.rule import Severity
from fsa.gui.pages.import_page import ImportPage
from tests.gui.helpers import make_result, make_summary


def _make_skipped_result(rule_id: str = "S-001") -> ValidationResult:
    """创建一条跳过结果 (规则因缺数据跳过: passed=True, skipped=True)。"""
    return ValidationResult(
        rule_id=rule_id,
        rule_name="测试规则",
        passed=True,
        severity=Severity.ERROR,
        left_value=0.0,
        right_value=0.0,
        diff=0.0,
        tolerance=0.01,
        formula="a == b",
        message="跳过",
        skipped=True,
    )


def _make_summary_with_skipped(results: list[ValidationResult]) -> ValidationSummary:
    """构造汇总: total/passed 均排除跳过 (与 validation_service 语义一致)。"""
    skipped = sum(1 for r in results if r.skipped)
    return ValidationSummary(
        period="2024-12",
        total=len(results) - skipped,
        passed=sum(1 for r in results if r.passed and not r.skipped and not r.errored),
        failed=sum(1 for r in results if not r.passed and not r.errored),
        errored=sum(1 for r in results if r.errored),
        skipped=skipped,
        results=results,
    )


class TestMatchFilter:
    """测试 _match_filter 筛选语义。"""

    @pytest.fixture
    def page(self, qapp, app_state):
        return ImportPage(app_state)

    def test_pass_matches_pass_filter(self, page) -> None:
        result = make_result(passed=True, severity=Severity.ERROR)
        page._current_filter = "pass"
        assert page._match_filter(result) is True

    def test_fail_does_not_match_pass_filter(self, page) -> None:
        result = make_result(passed=False, severity=Severity.ERROR)
        page._current_filter = "pass"
        assert page._match_filter(result) is False

    def test_error_severity_matches_fail_filter(self, page) -> None:
        """失败且 severity=ERROR 且非异常 -> 匹配「不通过」。"""
        result = make_result(passed=False, severity=Severity.ERROR)
        page._current_filter = "fail"
        assert page._match_filter(result) is True

    def test_warning_severity_matches_warning_filter(self, page) -> None:
        result = make_result(passed=False, severity=Severity.WARNING)
        page._current_filter = "warning"
        assert page._match_filter(result) is True

    def test_info_severity_matches_warning_filter(self, page) -> None:
        result = make_result(passed=False, severity=Severity.INFO)
        page._current_filter = "warning"
        assert page._match_filter(result) is True

    def test_passed_does_not_match_fail_filter(self, page) -> None:
        result = make_result(passed=True, severity=Severity.ERROR)
        page._current_filter = "fail"
        assert page._match_filter(result) is False

    def test_errored_matches_exception_filter(self, page) -> None:
        """errored 专属「异常」筛选, 不匹配「不通过」。"""
        result = make_result(passed=False, errored=True, severity=Severity.ERROR)
        page._current_filter = "exception"
        assert page._match_filter(result) is True
        page._current_filter = "fail"
        assert page._match_filter(result) is False

    def test_failed_error_does_not_match_exception_filter(self, page) -> None:
        """普通不通过 (非 errored) 不匹配「异常」筛选。"""
        result = make_result(passed=False, severity=Severity.ERROR)
        page._current_filter = "exception"
        assert page._match_filter(result) is False

    def test_all_filter_matches_everything(self, page) -> None:
        for passed, severity, errored in [
            (True, Severity.ERROR, False),
            (False, Severity.WARNING, False),
            (False, Severity.ERROR, True),
        ]:
            result = make_result(passed=passed, severity=severity, errored=errored)
            page._current_filter = "all"
            assert page._match_filter(result) is True

    def test_warning_filter_excludes_error(self, page) -> None:
        result = make_result(passed=False, severity=Severity.ERROR)
        page._current_filter = "warning"
        assert page._match_filter(result) is False

    def test_skipped_matches_skip_filter(self, page) -> None:
        """skipped 结果匹配「跳过」筛选, 不匹配「通过」/「不通过」。"""
        skipped = _make_skipped_result("S-001")
        page._current_filter = "skip"
        assert page._match_filter(skipped) is True
        page._current_filter = "pass"
        assert page._match_filter(skipped) is False
        page._current_filter = "fail"
        assert page._match_filter(skipped) is False

    def test_summary_counts(self, app_state) -> None:
        """测试 _update_results 后的汇总计数 (「不通过」卡不含异常)。"""
        page = ImportPage(app_state)
        results = [
            make_result("A-001", passed=True, severity=Severity.ERROR),
            make_result("B-001", passed=False, severity=Severity.ERROR, diff=1.0),
            make_result("C-001", passed=False, severity=Severity.WARNING, diff=2.0),
            make_result("D-001", passed=False, errored=True, severity=Severity.ERROR),
        ]
        app_state.set_results(make_summary(results))

        assert page._card_pass._value.text() == "1"
        assert page._card_error._value.text() == "1"
        assert page._card_warn._value.text() == "1"
        assert page._card_total._value.text() == "4"
        assert page._card_error._label.text() == "不通过"

    def test_filter_buttons_six_states(self, app_state) -> None:
        """筛选标签栏同步为六态 (全部/不通过/异常/警告/跳过/通过), 旧「错误」态移除。"""
        page = ImportPage(app_state)
        results = [
            make_result("A-001", passed=True, severity=Severity.ERROR),
            make_result("B-001", passed=False, severity=Severity.ERROR, diff=1.0),
            make_result("C-001", passed=False, severity=Severity.WARNING, diff=2.0),
            make_result("D-001", passed=False, errored=True, severity=Severity.ERROR),
            _make_skipped_result("S-001"),
        ]
        app_state.set_results(_make_summary_with_skipped(results))

        assert set(page._filter_buttons) == {
            "all", "fail", "exception", "warning", "skip", "pass",
        }
        # 布局顺序 = 六态定义顺序 (按钮位于 stretch 之前)
        layout = page._filter_section.layout()
        assert layout is not None
        order = []
        for i in range(layout.count()):
            item = layout.itemAt(i)
            assert item is not None
            w = item.widget()
            if w is None:
                continue
            for key, btn in page._filter_buttons.items():
                if btn is w:
                    order.append(key)
        assert order == ["all", "fail", "exception", "warning", "skip", "pass"]
        assert page._filter_buttons["all"].text() == "全部 (5)"
        assert page._filter_buttons["fail"].text() == "不通过 (1)"
        assert page._filter_buttons["exception"].text() == "异常 (1)"
        assert page._filter_buttons["warning"].text() == "警告 (1)"
        assert page._filter_buttons["skip"].text() == "跳过 (1)"
        assert page._filter_buttons["pass"].text() == "通过 (1)"

    def test_stale_error_filter_resets_to_all(self, app_state) -> None:
        """遗留的「error」筛选键在结果刷新时回退为「全部」。"""
        page = ImportPage(app_state)
        page._current_filter = "error"
        app_state.set_results(make_summary([make_result("A-001")]))
        assert page._current_filter == "all"

    def test_skipped_excluded_from_pass_filter(self, page) -> None:
        """B-14: skipped=True 的结果不匹配"通过"筛选, 但匹配"全部"。"""
        skipped = _make_skipped_result("S-001")
        page._current_filter = "pass"
        assert page._match_filter(skipped) is False
        page._current_filter = "all"
        assert page._match_filter(skipped) is True

    def test_counts_all_includes_skipped(self, app_state) -> None:
        """B-14: "全部"计数 = 结果卡片数 (含跳过); "通过"计数排除跳过。"""
        page = ImportPage(app_state)
        results = [
            make_result("A-001", passed=True, severity=Severity.ERROR),
            _make_skipped_result("S-001"),
            make_result("B-001", passed=False, severity=Severity.ERROR, diff=1.0),
        ]
        app_state.set_results(_make_summary_with_skipped(results))

        assert page._filter_buttons["all"].text() == "全部 (3)"
        assert page._filter_buttons["pass"].text() == "通过 (1)"
        assert page._filter_buttons["fail"].text() == "不通过 (1)"
        assert page._filter_buttons["warning"].text() == "警告 (0)"
        assert page._filter_buttons["skip"].text() == "跳过 (1)"
        # 规则总数卡片语义不变: 显示排除跳过的执行规则数
        assert page._card_total._value.text() == "2"
        assert page._card_pass._value.text() == "1"

    def test_all_filter_shows_skipped_cards(self, app_state) -> None:
        """"全部"筛选下, 跳过结果卡片保持可见 (计数一致)。"""
        page = ImportPage(app_state)
        results = [
            _make_skipped_result("S-001"),
            make_result("A-001", passed=True, severity=Severity.ERROR),
        ]
        app_state.set_results(_make_summary_with_skipped(results))

        visible = [
            card._result.rule_id
            for _, card in page._result_cards
            if not card.isHidden()  # 反映 _apply_filter 的 setVisible
        ]
        assert visible == ["S-001", "A-001"]

        page._current_filter = "pass"
        page._apply_filter()
        visible = [
            card._result.rule_id
            for _, card in page._result_cards
            if not card.isHidden()
        ]
        assert visible == ["A-001"]
