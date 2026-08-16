"""使用 OCRFlow MCP 将非 Markdown 资料转成 Markdown 并归入本地知识库。

用法 (Windows PowerShell 推荐):
    python scripts\\ingest_knowledge_ocrflow.py C:\\资料\\CAS31.pdf D:\\资料\\陈版主问答.docx

行为:
- .md/.txt 文件直接复制到 resources/knowledge
- 其他文件交给 OCRFlow MCP 的 parse_documents 工具处理
- OCRFlow 路径默认 C:\\Software\\OCRFlow\\OCRFlow.exe
- 转换结果写入 resources/knowledge, 由 agent/knowledge.py 自动检索
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_OUTPUT_DIR = _PROJECT_ROOT / "resources" / "knowledge"
_DEFAULT_OCRFLOW_EXE = Path("C:/Software/OCRFlow/OCRFlow.exe")
_DEFAULT_MCP_JS = Path(
    "C:/Software/OCRFlow/resources/app.asar.unpacked/dist-electron/mcp-server.js"
)


def _to_windows_path(path: Path) -> str:
    """WSL 路径 -> Windows 路径; Windows 原生路径原样返回。"""
    text = str(path.resolve())
    if text.startswith("/mnt/") and len(text) > 6:
        drive = text[5].upper()
        return f"{drive}:\\" + text[6:].replace("/", "\\")
    return str(path)


class _McpClient:
    """最小 MCP stdio 客户端, 只用于调用 parse_documents。"""

    def __init__(self, mcp_js: Path, ocrflow_exe: Path) -> None:
        env = os.environ.copy()
        if sys.platform.startswith("linux"):
            # WSL 下让 node 能通过 PATH 找到 OCRFlow 可执行文件
            wrapper_dir = Path(tempfile.mkdtemp(prefix="ocrflow-bin-"))
            wrapper = wrapper_dir / "OCRFlow"
            wrapper.write_text(
                f'#!/bin/sh\nexec "{ocrflow_exe.as_posix()}" "$@"\n',
                encoding="utf-8",
            )
            wrapper.chmod(0o755)
            env["PATH"] = f"{wrapper_dir}:{env.get('PATH', '')}"
        self._proc = subprocess.Popen(
            ["node", str(mcp_js)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
        self._next_id = 1
        self._call(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "fsa-knowledge-ingest", "version": "1.0"},
            },
        )

    def _call(self, method: str, params: dict[str, object]) -> dict[str, object]:
        req = {"jsonrpc": "2.0", "id": self._next_id, "method": method, "params": params}
        self._next_id += 1
        self._proc.stdin.write(json.dumps(req) + "\n")  # type: ignore[union-attr]
        self._proc.stdin.flush()  # type: ignore[union-attr]
        while True:
            line = self._proc.stdout.readline()  # type: ignore[union-attr]
            if not line:
                raise RuntimeError("OCRFlow MCP server exited unexpectedly")
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if payload.get("id") == req["id"]:
                return payload

    def parse_documents(self, paths: list[str], output_dir: str) -> dict[str, object]:
        result = self._call(
            "tools/call",
            {
                "name": "parse_documents",
                "arguments": {"paths": paths, "outputDir": output_dir},
            },
        )
        content = result.get("result", {}).get("content", [])
        if content:
            try:
                return json.loads(content[0]["text"])
            except (KeyError, json.JSONDecodeError):
                return {"raw": content}
        return result

    def close(self) -> None:
        with contextlib.suppress(OSError):
            self._proc.terminate()


def _is_text_knowledge(path: Path) -> bool:
    return path.suffix.lower() in (".md", ".txt")


def _copy_text(path: Path) -> Path:
    target = _OUTPUT_DIR / path.name
    shutil.copy2(path, target)
    return target


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", help="文件或文件夹路径")
    parser.add_argument(
        "--ocrflow-exe",
        default=str(_DEFAULT_OCRFLOW_EXE),
        help="OCRFlow.exe 路径",
    )
    parser.add_argument(
        "--mcp-js",
        default=str(_DEFAULT_MCP_JS),
        help="OCRFlow mcp-server.js 路径",
    )
    args = parser.parse_args()

    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ocrflow_exe = Path(args.ocrflow_exe)
    mcp_js = Path(args.mcp_js)
    if not ocrflow_exe.exists():
        print(f"未找到 OCRFlow.exe: {ocrflow_exe}", file=sys.stderr)
        sys.exit(2)
    if not mcp_js.exists():
        print(f"未找到 mcp-server.js: {mcp_js}", file=sys.stderr)
        sys.exit(2)

    files: list[Path] = []
    for raw in args.paths:
        path = Path(raw)
        if path.is_dir():
            files.extend(p for p in path.iterdir() if p.is_file())
        elif path.is_file():
            files.append(path)
        else:
            print(f"[skip] 不存在: {path}", file=sys.stderr)

    text_files = [p for p in files if _is_text_knowledge(p)]
    ocr_files = [p for p in files if not _is_text_knowledge(p)]
    for path in text_files:
        print(f"[copy] {path} -> {_copy_text(path)}")

    if not ocr_files:
        return

    output_win = _to_windows_path(_OUTPUT_DIR)
    ocr_paths = [_to_windows_path(p) for p in ocr_files]
    print(f"[ocr] 使用 OCRFlow 处理 {len(ocr_files)} 个文件")
    client = _McpClient(mcp_js, ocrflow_exe)
    try:
        summary = client.parse_documents(ocr_paths, output_win)
    finally:
        client.close()
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
