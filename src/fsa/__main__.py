"""模块入口: python -m fsa

支持一个隐藏的 COM 诊断模式 (DLP 加密环境排障):
    fsa.exe --com-probe <excel文件> <结果输出文件>
不启动 GUI, 直接用 ExcelComSession 读取指定文件, 结果写入输出文件。
"""

import sys


def _com_probe(target: str, out_path: str) -> int:
    """无界面 COM 读取诊断: 结果写入文件 (窗口版 exe 无控制台 stdout)。"""
    try:
        from fsa.core.importer.excel_reader import ExcelComSession

        with ExcelComSession() as session:
            data = session.read_file(target)
        result = f"COM-PROBE OK: {len(data)} 个工作表"
        code = 0
    except Exception as error:  # noqa: BLE001 - 诊断模式需要完整异常信息
        import traceback

        result = f"COM-PROBE FAIL: {type(error).__name__}: {error}\n{traceback.format_exc()}"
        code = 1
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(result)
    return code


def main() -> None:
    if len(sys.argv) >= 4 and sys.argv[1] == "--com-probe":
        sys.exit(_com_probe(sys.argv[2], sys.argv[3]))
    from fsa.gui.app import main as gui_main

    gui_main()


if __name__ == "__main__":
    main()
