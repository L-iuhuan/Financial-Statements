"""sanitize_llm_input 输入消毒测试 (P1)。

覆盖: strip / 控制字符去除 / 空白折叠 / 超长截断 / 非 str 转换 / 边界。
"""

from __future__ import annotations

from fsa.agent.sanitize import sanitize_llm_input


class TestSanitizeLlmInput:
    def test_strips_whitespace(self) -> None:
        assert sanitize_llm_input("  x  ") == "x"

    def test_removes_control_chars(self) -> None:
        assert sanitize_llm_input("a\x00b\x1bc\x08d") == "abcd"

    def test_keeps_then_collapses_newline_tab(self) -> None:
        """\\n 与 \\t 是合法空白, 去除控制字符阶段保留, 随后被折叠为单个空格。"""
        assert sanitize_llm_input("a\n\tb") == "a b"

    def test_collapses_consecutive_whitespace(self) -> None:
        assert sanitize_llm_input("a   b\n\n c \t d") == "a b c d"

    def test_truncates_long_input(self) -> None:
        text = sanitize_llm_input("x" * 300)
        assert text.endswith("…(截断)")
        assert len(text) == 200 + len("…(截断)")

    def test_truncation_honors_max_len(self) -> None:
        text = sanitize_llm_input("a" * 10, max_len=5)
        assert text == "aaaaa…(截断)"

    def test_short_input_untouched(self) -> None:
        assert sanitize_llm_input("资产总计") == "资产总计"

    def test_non_str_input_converted(self) -> None:
        assert sanitize_llm_input(123.45) == "123.45"
        assert sanitize_llm_input(42) == "42"

    def test_empty_string_returns_empty(self) -> None:
        assert sanitize_llm_input("") == ""

    def test_deterministic(self) -> None:
        raw = "  A\x00x   b \n  c  "
        assert sanitize_llm_input(raw) == sanitize_llm_input(raw)
