"""amount_parser 模块测试: 统一金额解析工具。

测试内容: 千分位、括号负数、占位符、科学计数法、空值、普通数字。
"""

from __future__ import annotations

import pytest

from fsa.core.importer.amount_parser import detect_amount_unit, parse_amount, to_yuan


class TestParseAmountThousandSeparator:
    """测试千分位逗号与空格剔除。"""

    def test_parse_thousands_with_comma(self) -> None:
        assert parse_amount("1,000,000.50") == 1000000.50

    def test_parse_thousands_with_comma_no_decimal(self) -> None:
        assert parse_amount("1,291,800") == 1291800.0

    def test_parse_with_spaces_removed(self) -> None:
        assert parse_amount("1 000 000.50") == 1000000.50

    def test_parse_with_fullwidth_comma(self) -> None:
        assert parse_amount("1，291，800") == 1291800.0


class TestParseAmountNegativeParenthesis:
    """测试括号负数。"""

    def test_parse_parenthesized_negative(self) -> None:
        assert parse_amount("(1,291,800.12)") == -1291800.12

    def test_parse_parenthesized_negative_fullwidth(self) -> None:
        assert parse_amount("（1,291,800.12）") == -1291800.12

    def test_parse_plain_negative(self) -> None:
        assert parse_amount("-5000") == -5000.0


class TestParseAmountPlaceholder:
    """测试占位符 (表示无数据) 转为 0.0。"""

    @pytest.mark.parametrize("placeholder", ["-", "—", "--", "－", "–", "−"])
    def test_placeholder_returns_zero(self, placeholder: str) -> None:
        assert parse_amount(placeholder) == 0.0


class TestParseAmountScientific:
    """测试科学计数法。"""

    def test_parse_scientific_notation(self) -> None:
        assert parse_amount("1.5e6") == 1500000.0

    def test_parse_scientific_notation_large(self) -> None:
        assert parse_amount("1e15") == 1e15


class TestParseAmountEmpty:
    """测试空单元格 (None / 纯空白) 返回 None，不制造虚假的 0。"""

    def test_parse_none_returns_none(self) -> None:
        assert parse_amount(None) is None

    def test_parse_empty_string_returns_none(self) -> None:
        assert parse_amount("") is None

    def test_parse_whitespace_only_returns_none(self) -> None:
        assert parse_amount("   ") is None

    def test_parse_fullwidth_whitespace_only_returns_none(self) -> None:
        assert parse_amount("　　") is None

    def test_parse_nan_returns_none(self) -> None:
        assert parse_amount(float("nan")) is None


class TestParseAmountPlainNumber:
    """测试普通 float 与 int。"""

    def test_parse_float(self) -> None:
        assert parse_amount(123.45) == 123.45

    def test_parse_int(self) -> None:
        assert parse_amount(42) == 42.0

    def test_parse_float_string(self) -> None:
        assert parse_amount("123.45") == 123.45

    def test_parse_bool_returns_none(self) -> None:
        assert parse_amount(True) is None

    def test_parse_unparsable_returns_none(self) -> None:
        assert parse_amount("abc") is None

    def test_parse_zero(self) -> None:
        assert parse_amount(0) == 0.0
        assert parse_amount("0") == 0.0


class TestAmountUnitDetection:
    """金额单位识别与换算测试。"""

    def test_detect_wan_yuan(self) -> None:
        assert detect_amount_unit("期末余额(万元)") == "万元"

    def test_detect_qian_yuan(self) -> None:
        assert detect_amount_unit("本期金额（千元）") == "千元"

    def test_detect_yuan_with_context(self) -> None:
        assert detect_amount_unit("金额单位：元") == "元"

    def test_plain_header_has_no_unit(self) -> None:
        assert detect_amount_unit("期末余额") is None

    def test_to_yuan_conversions(self) -> None:
        assert to_yuan(1.0, "万元") == 10000.0
        assert to_yuan(1.0, "千元") == 1000.0
        assert to_yuan(1.0, "亿元") == 100000000.0
        assert to_yuan(1.0, None) == 1.0
