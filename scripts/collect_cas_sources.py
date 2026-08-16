"""收集 CAS 准则公开原文并转为 Markdown 存入 resources/knowledge。

用法:
    python scripts/collect_cas_sources.py            # 下载并转换
    python scripts/collect_cas_sources.py --dry-run  # 只列出任务

说明:
- 仅下载官方/公开法规页面, 不保证网页后续不失效。
- 下载内容仅用于本地知识库检索, 请自行核对原文与更新修订。
- 页面为 HTML 时用标准库转换为纯文本 Markdown。
"""

from __future__ import annotations

import argparse
import html
import re
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_OUTPUT_DIR = _PROJECT_ROOT / "resources" / "knowledge"

_SOURCES: dict[str, str] = {
    "cas_basic_standard_2014": (
        "https://www.casc.org.cn/2018/0815/202818.shtml"
    ),
    "cas30_financial_statement_presentation": (
        "https://m.mof.gov.cn/czxw/202608/t20260805_3994927.htm"
    ),
    "cas31_cash_flow_statement": (
        "https://www.casc.org.cn/2018/0814/202775.shtml"
    ),
    "cas33_consolidated_financial_statements": (
        "http://kjs.mof.gov.cn/zhengcefabu/201402/t20140220_1045206.htm"
    ),
    "cas31_cash_flow_statement_law": (
        "https://law.esnai.cn/mview/22816"
    ),
}


class _TextExtractor(HTMLParser):
    """从 HTML 中提取正文文本, 保留标题/段落/列表结构。"""

    _BLOCK_TAGS = {"p", "div", "br", "h1", "h2", "h3", "h4", "li", "tr"}
    _SKIP_TAGS = {"script", "style", "noscript"}

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._skip_depth = 0
        self._current = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag in self._BLOCK_TAGS:
            self._flush()
            if tag.startswith("h"):
                self._parts.append("\n\n## ")
            else:
                self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if self._skip_depth:
            return
        if tag in self._BLOCK_TAGS:
            self._flush()
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        self._current += data

    def _flush(self) -> None:
        text = re.sub(r"\s+", " ", self._current).strip()
        if text:
            self._parts.append(text)
        self._current = ""

    def text(self) -> str:
        self._flush()
        return "".join(self._parts)


def _fetch(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (knowledge-collector)"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read()
    return raw.decode("utf-8", errors="ignore")


def _to_markdown(html_text: str, source_url: str) -> str:
    parser = _TextExtractor()
    parser.feed(html_text)
    body = html.unescape(parser.text())
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    return (
        f"# 外部知识文档\n\n来源: {source_url}\n\n"
        + "\n\n".join(lines)
        + "\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, url in _SOURCES.items():
        target = _OUTPUT_DIR / f"{name}.md"
        if args.dry_run:
            print(f"[dry-run] {url} -> {target}")
            continue
        try:
            raw_html = _fetch(url)
            text = _to_markdown(raw_html, url)
            target.write_text(text, encoding="utf-8")
            print(f"[ok] {url} -> {target} ({len(text)} chars)")
        except Exception as exc:  # 网络源可能失效, 单条失败不中断
            print(f"[skip] {url}: {exc}")


if __name__ == "__main__":
    main()
