"""知识库检索质量测试: HTML 清洗/切块/去重/来源标注。"""

from __future__ import annotations

import fsa.agent.knowledge as knowledge
from fsa.agent.knowledge import search_knowledge


class TestStripHtml:
    def test_strips_tags_and_script(self) -> None:
        text = "<p>资产<b>=</b>负债 &amp; 权益</p><script>alert('x')</script>"
        result = knowledge._strip_html(text)
        assert "资产=负债 & 权益" in result
        assert "alert" not in result
        assert "<" not in result

    def test_normalizes_whitespace(self) -> None:
        result = knowledge._strip_html("<p>行1</p>\n\n\n\n<p>行2</p>")
        assert "行1" in result and "行2" in result
        assert "行1\n\n行2" in result


class TestChunkText:
    def test_short_text_single_chunk(self) -> None:
        chunks = knowledge._chunk_text("资产负债表平衡。")
        assert chunks == ["资产负债表平衡。"]

    def test_long_paragraph_split_by_sentences_under_limit(self) -> None:
        sentence = "这句话用于测试知识库切块逻辑。" * 100
        chunks = knowledge._chunk_text(sentence)
        assert len(chunks) > 1
        assert all(len(chunk) <= knowledge._CHUNK_MAX_CHARS for chunk in chunks)

    def test_multi_paragraph_kept_together_when_fit(self) -> None:
        chunks = knowledge._chunk_text("第一段。\n\n第二段。")
        assert len(chunks) == 1
        assert "第一段" in chunks[0] and "第二段" in chunks[0]


class TestBuiltinTopicCoverage:
    """内置条目对 42 条规则主题的覆盖 (SCE/LR 主题补齐)。"""

    def test_equity_statement_topic_retrievable(self) -> None:
        """权益变动表主题可检索到内置条目 (覆盖 SCE-* 9 条规则)。"""
        result = search_knowledge("所有者权益变动表 综合收益")
        assert "【内置知识 · 权益变动表" in result
        assert "实收资本" in result

    def test_financial_ratio_topic_retrievable(self) -> None:
        """财务比率主题可检索到内置条目 (覆盖 LR-* 12 条规则)。"""
        result = search_knowledge("速动比率 资产负债率")
        assert "【内置知识 · 财务比率" in result
        assert "分析程序" in result

    def test_fallback_intent_routes_ratio_question(self) -> None:
        """fallback 关键词意图: 毛利率问题路由到财务比率条目。"""
        from fsa.agent.fallback import _try_knowledge

        answer = _try_knowledge("毛利率异常波动说明什么")
        assert answer is not None
        assert "财务比率" in answer

    def test_fallback_intent_routes_sce_question(self) -> None:
        """fallback 关键词意图: 权益变动问题路由到权益变动表条目。"""
        from fsa.agent.fallback import _try_knowledge

        answer = _try_knowledge("权益变动表和资产负债表对不上")
        assert answer is not None
        assert "权益变动表" in answer


class TestSearchQuality:
    def test_deduplicates_identical_chunks(self, monkeypatch) -> None:
        monkeypatch.setattr(knowledge, "_KNOWLEDGE", [])
        monkeypatch.setattr(knowledge, "_rule_knowledge", lambda: [])

        def fake_external() -> list[tuple[str, str]]:
            return [
                ("测试文档#1", "独一无二的检索词xyz 出现在两段相同内容中。"),
                ("测试文档#2", "独一无二的检索词xyz 出现在两段相同内容中。"),
            ]

        monkeypatch.setattr(knowledge, "_external_knowledge", fake_external)
        result = search_knowledge("独一无二的检索词xyz")
        assert result.count("【外部文档 · 测试文档") == 1

    def test_output_limited_to_three_blocks_and_char_cap(self, monkeypatch) -> None:
        monkeypatch.setattr(knowledge, "_KNOWLEDGE", [])
        monkeypatch.setattr(knowledge, "_rule_knowledge", lambda: [])

        def fake_external() -> list[tuple[str, str]]:
            return [(f"文档#{index}", f"超大检索词xyz{index} " + "内容" * 600) for index in range(6)]

        monkeypatch.setattr(knowledge, "_external_knowledge", fake_external)
        result = search_knowledge("超大检索词xyz")
        blocks = [b for b in result.split("\n\n") if b.startswith("【外部文档")]
        assert len(blocks) <= 3
        assert len(result) <= knowledge._SEARCH_OUTPUT_MAX_CHARS + 200
