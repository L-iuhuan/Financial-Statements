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
import threading
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_OUTPUT_DIR = _PROJECT_ROOT / "resources" / "knowledge"
_DEFAULT_OCRFLOW_EXE = Path("C:/Software/OCRFlow/OCRFlow.exe")
_DEFAULT_MCP_JS = Path("C:/Software/OCRFlow/resources/app.asar.unpacked/dist-electron/mcp-server.js")


def _to_windows_path(path: Path) -> str:
    """WSL 路径 -> Windows 路径; Windows 原生路径原样返回。"""
    text = str(path.resolve())
    if text.startswith("/mnt/") and len(text) > 6:
        drive = text[5].upper()
        return f"{drive}:\\" + text[6:].replace("/", "\\")
    return str(path)


def _to_local_path(path: Path) -> Path:
    """Windows 路径 (C:\\...) -> WSL 本地路径 (/mnt/c/...), 其余原样。

    WSL 下 os.path.exists("C:\\...") 恒为 False, 必须转换后再检查。
    """
    text = str(path)
    if sys.platform.startswith("linux") and len(text) >= 3 and text[1] == ":":
        return Path("/mnt/" + text[0].lower() + "/" + text[3:].replace("\\", "/"))
    return path


class _McpClient:
    """最小 MCP stdio 客户端, 只用于调用 parse_documents。

    每次 JSON-RPC 调用由 watchdog 线程施加超时: 超时后杀死 MCP 进程,
    避免 OCRFlow 卡死导致脚本永久挂起。
    """

    def __init__(
        self,
        mcp_js: Path,
        ocrflow_exe: Path,
        timeout: float = 600.0,
    ) -> None:
        self._timeout = timeout
        env = os.environ.copy()
        if sys.platform.startswith("linux"):
            # WSL 下让 node 能通过 PATH 找到 OCRFlow 可执行文件;
            # C:\\... 路径需转换为 /mnt/c/... 才能被 exec 执行
            local_exe = _to_local_path(ocrflow_exe)
            if local_exe.exists():
                wrapper_dir = Path(tempfile.mkdtemp(prefix="ocrflow-bin-"))
                wrapper = wrapper_dir / "OCRFlow"
                wrapper.write_text(
                    f'#!/bin/sh\nexec "{local_exe.as_posix()}" "$@"\n',
                    encoding="utf-8",
                )
                wrapper.chmod(0o755)
                env["PATH"] = f"{wrapper_dir}:{env.get('PATH', '')}"
            else:
                print(
                    f"[warn] WSL 下未找到 OCRFlow 可执行文件: {local_exe}",
                    file=sys.stderr,
                )
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

    def _call(
        self,
        method: str,
        params: dict[str, object],
        timeout: float | None = None,
    ) -> dict[str, object]:
        req = {"jsonrpc": "2.0", "id": self._next_id, "method": method, "params": params}
        self._next_id += 1
        effective_timeout = timeout or self._timeout

        def kill() -> None:
            with contextlib.suppress(OSError):
                self._proc.kill()

        watchdog = threading.Timer(effective_timeout, kill)
        watchdog.daemon = True
        watchdog.start()
        try:
            self._proc.stdin.write(json.dumps(req) + "\n")  # type: ignore[union-attr]
            self._proc.stdin.flush()  # type: ignore[union-attr]
            while True:
                line = self._proc.stdout.readline()  # type: ignore[union-attr]
                if not line:
                    raise RuntimeError(
                        "OCRFlow MCP server exited unexpectedly (可能未安装 OCRFlow 或 mcp-server 路径错误)"
                    )
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if payload.get("id") == req["id"]:
                    if payload.get("error"):
                        raise RuntimeError(f"OCRFlow MCP 调用 {method} 失败: {payload['error']}")
                    return payload
        finally:
            watchdog.cancel()

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
        try:
            self._proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            with contextlib.suppress(OSError):
                self._proc.kill()


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
    parser.add_argument(
        "--timeout",
        type=float,
        default=600.0,
        help="单次 MCP 调用超时秒数 (默认 600)",
    )
    args = parser.parse_args()

    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ocrflow_exe = Path(args.ocrflow_exe)
    mcp_js = Path(args.mcp_js)
    local_ocrflow = _to_local_path(ocrflow_exe)
    local_mcp_js = _to_local_path(mcp_js)
    if not local_ocrflow.exists() and not ocrflow_exe.exists():
        print(f"未找到 OCRFlow.exe: {ocrflow_exe} (本地检查: {local_ocrflow})", file=sys.stderr)
        sys.exit(2)
    if not local_mcp_js.exists() and not mcp_js.exists():
        print(f"未找到 mcp-server.js: {mcp_js} (本地检查: {local_mcp_js})", file=sys.stderr)
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
    client = _McpClient(mcp_js, ocrflow_exe, timeout=args.timeout)
    try:
        summary = client.parse_documents(ocr_paths, output_win)
    finally:
        client.close()
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
