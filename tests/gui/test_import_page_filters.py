"""ImportPage 筛选逻辑测试。"""

from __future__ import annotations

import pytest

from fsa.core.models.rule import Severity
from fsa.gui.pages.import_page import ImportPage
from tests.gui.helpers import make_result, make_summary


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

    def test_error_severity_matches_error_filter(self, page) -> None:
        result = make_result(passed=False, severity=Severity.ERROR)
        page._current_filter = "error"
        assert page._match_filter(result) is True

    def test_warning_severity_matches_warning_filter(self, page) -> None:
        result = make_result(passed=False, severity=Severity.WARNING)
        page._current_filter = "warning"
        assert page._match_filter(result) is True

    def test_info_severity_matches_warning_filter(self, page) -> None:
        result = make_result(passed=False, severity=Severity.INFO)
        page._current_filter = "warning"
        assert page._match_filter(result) is True

    def test_passed_does_not_match_error_filter(self, page) -> None:
        result = make_result(passed=True, severity=Severity.ERROR)
        page._current_filter = "error"
        assert page._match_filter(result) is False

    def test_errored_matches_error_filter(self, page) -> None:
        result = make_result(passed=False, errored=True, severity=Severity.ERROR)
        page._current_filter = "error"
        assert page._match_filter(result) is True

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

    def test_summary_counts(self, app_state) -> None:
        """测试 _update_results 后的汇总计数。"""
        page = ImportPage(app_state)
        results = [
            make_result("A-001", passed=True, severity=Severity.ERROR),
            make_result("B-001", passed=False, severity=Severity.ERROR, diff=1.0),
            make_result("C-001", passed=False, severity=Severity.WARNING, diff=2.0),
            make_result("D-001", passed=False, errored=True, severity=Severity.ERROR),
        ]
        app_state.set_results(make_summary(results))

        assert page._card_pass._value.text() == "1"
        assert page._card_error._value.text() == "2"
        assert page._card_warn._value.text() == "1"
        assert page._card_total._value.text() == "4"
