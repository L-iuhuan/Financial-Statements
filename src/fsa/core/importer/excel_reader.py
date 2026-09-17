"""Excel/CSV 文件读取器: 支持 .xlsx/.xlsm (openpyxl)、.xls (pandas+xlrd) 与 .csv。

CSV 编码自动探测 UTF-8(含 BOM) 与 GBK。

统一转换为 RawSheetData，并为导入框架提供通用能力:
- 自动定位表头行（兼容标题行、合并单元格、无"项目"列的场景）
- 捕获连续的多行表头（header_rows），供 SCE 等多级表头使用
- 数据行以列标题为键，额外包含 "_row" 键（源文件行号，从 1 开始）
"""

from __future__ import annotations

import csv
import os
import re
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Protocol, cast
from zipfile import BadZipFile

import openpyxl
from loguru import logger
from openpyxl.worksheet.worksheet import Worksheet

from fsa.core.exceptions import FSAError

_NAME_HEADER_CANDIDATES = ("项目", "项目名称", "科目", "科目名称")
_AMOUNT_HEADER_KEYWORDS = (
    "期末余额",
    "年初余额",
    "本期金额",
    "上期金额",
    "期末数",
    "年初数",
    "本期数",
    "上期数",
    "金额",
    "余额",
    "发生额",
)
_MAX_SCAN_ROWS = 15
_MAX_HEADER_LAYERS = 4
# 超过该字节数的 .xlsx/.xlsm 优先用 read_only 流式读取, 降低大文件内存峰值
_LARGE_FILE_THRESHOLD = 5 * 1024 * 1024

try:
    import xlrd

    _XLRD_ERRORS: tuple[type[Exception], ...] = (xlrd.biffh.XLRDError,)
except ImportError:
    _XLRD_ERRORS = ()

# 常规读取失败类型: 缺依赖 (ImportError, 如 .xls 缺 xlrd/pandas)、
# 加密/损坏文件 (BadZipFile/XLRDError) 等统一回退到 Excel COM 读取
_NATIVE_READ_ERRORS = (
    BadZipFile,
    OSError,
    ValueError,
    KeyError,
    TypeError,
    ImportError,
) + _XLRD_ERRORS


@dataclass
class RawSheetData:
    """一个工作表的原始数据。

    Attributes:
        name: 工作表名称
        headers: 主表头行（第一层表头）
        header_rows: 连续的多层表头（至少 1 行），供矩阵式报表使用
        rows: 数据行列表，每行是 dict，键为 headers 中的列标题，
              额外包含 "_row" 键（源文件行号，从 1 开始）
    """

    name: str
    headers: list[str] = field(default_factory=list)
    header_rows: list[list[str]] = field(default_factory=list)
    rows: list[dict[str, object]] = field(default_factory=list)


def read_excel(
    file_path: str,
    use_com: bool = False,
    com_session: ExcelComSession | None = None,
) -> dict[str, RawSheetData]:
    """读取 Excel 文件，返回所有工作表的原始数据。

    Args:
        file_path: Excel 文件路径（.xlsx 或 .xls）
        use_com: 强制使用 Excel COM 读取（默认为 False，常规读取失败时自动回退）
        com_session: 批量导入时复用的 Excel COM 会话 (延迟启动);
            传入后 COM 回退经会话共享单个 Excel 进程, 避免每文件 5-40s 启动开销。
            会话必须在调用线程内创建/使用/关闭 (COM 线程亲和性)。

    Returns:
        字典，键为工作表名称，值为 RawSheetData

    Raises:
        FileNotFoundError: 文件不存在
        FSAError: 常规读取与 Excel COM 读取均失败
    """
    path = str(file_path)
    if use_com:
        if com_session is not None:
            return com_session.read_file(path)
        return read_excel_com(path)

    try:
        return _read_native(path)
    except FileNotFoundError:
        raise
    except _NATIVE_READ_ERRORS as error:
        logger.warning(f"常规方式读取失败（{error}），尝试用 Excel COM 打开: {path}")
        try:
            if com_session is not None:
                return com_session.read_file(path)
            return read_excel_com(path)
        except FSAError as com_error:
            raise FSAError(f"文件「{path}」常规解析失败（{error}），Excel COM 打开也失败: {com_error}") from error


class _ExcelAppProtocol(Protocol):
    """Excel COM 应用对象的最小类型表面 (仅本项目用到的成员)。"""

    Visible: bool
    DisplayAlerts: bool
    AskToUpdateLinks: bool
    Workbooks: object

    def Quit(self) -> None: ...


def _snapshot_excel_pids() -> set[int]:
    """快照当前 EXCEL.EXE 进程 PID 集合 (tasklist 解析, 不引入 psutil)。"""
    import subprocess

    try:
        completed = subprocess.run(  # noqa: S603 - 固定命令与参数
            ["tasklist", "/FI", "IMAGENAME eq EXCEL.EXE", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            timeout=15,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError):
        return set()
    return _parse_tasklist_pids(completed.stdout)


def _parse_tasklist_pids(output: str) -> set[int]:
    """从 tasklist CSV 输出解析 PID 列 (与进程枚举解耦, 便于单测)。"""
    pids: set[int] = set()
    for line in output.splitlines():
        parts = [part.strip().strip('"') for part in line.split(",")]
        if len(parts) >= 2 and parts[1].isdigit():
            pids.add(int(parts[1]))
    return pids


def _visible_excel_pids() -> set[int]:
    """带可见窗口的 EXCEL.EXE 进程 PID 集合 (用户正在使用的实例)。"""
    try:
        import win32gui
        import win32process
    except ImportError:
        return set()
    visible_pids: set[int] = set()

    def _collect(hwnd: int, _: object) -> None:
        if win32gui.IsWindowVisible(hwnd):
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            visible_pids.add(pid)

    try:
        win32gui.EnumWindows(_collect, None)
    except Exception:  # noqa: BLE001 - 窗口枚举失败按"无可见 Excel"保守处理
        return set()
    return visible_pids


def cleanup_invisible_excel() -> int:
    """结束所有不可见的 EXCEL.EXE 实例 (自动化残留僵尸), 返回清理数。

    僵尸成因: COM 会话 Quit 失败时残留的隐藏实例会阻塞后续所有自动化调用
    (表现为属性/方法全部拒绝, 2026-09-17 "全部失败"根因; 实测: 保留用户
    可见 Excel 不动、仅清理不可见僵尸即恢复正常)。用户正常打开的 Excel
    必有可见窗口 (含最小化), 不在清理范围内。
    """
    all_pids = _snapshot_excel_pids()
    if not all_pids:
        return 0
    invisible = all_pids - _visible_excel_pids()
    if not invisible:
        return 0
    killed = _kill_pids(invisible)
    if killed:
        logger.info(f"已清理 {killed} 个阻塞的不可见 Excel 残留实例")
    return killed


def _kill_pids(pids: set[int]) -> int:
    """强制结束指定 PID 的进程 (任务管理器的编程等价), 返回成功数。"""
    import subprocess

    killed = 0
    for pid in pids:
        try:
            completed = subprocess.run(  # noqa: S603 - 参数为已校验的整数 PID
                ["taskkill", "/PID", str(pid), "/F"],
                capture_output=True,
                timeout=15,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if completed.returncode == 0:
                killed += 1
        except (OSError, subprocess.SubprocessError):
            continue
    return killed


class ExcelComSession:
    """延迟启动的 Excel COM 批量读取会话 (DLP 加密环境批量导入提速)。

    单文件 COM 回退每文件都 DispatchEx 新建 Excel 进程 (5-40s/个);
    会话在首个需要 COM 的文件时才启动 Excel, 之后所有文件复用同一进程,
    批量导入 N 个加密文件的总开销从 N 次启动降为 1 次。

    线程亲和性: COM 单元线程模型要求在同一线程创建/使用/销毁,
    调用方必须在同一 (worker) 线程内使用 with 块。
    """

    def __init__(self) -> None:
        self._excel: _ExcelAppProtocol | None = None
        self._pythoncom: ModuleType | None = None
        self._co_initialized = False
        # 首次 DispatchEx 之前的 EXCEL.EXE 快照 (None = 本会话从未启动过 Excel):
        # 用于识别并清理本会话自己产生的不可见残留实例, 绝不触碰用户可见 Excel
        self._pid_snapshot: set[int] | None = None

    def __enter__(self) -> ExcelComSession:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def _ensure_started(self) -> _ExcelAppProtocol:
        """首次需要时启动 Excel 进程 (延迟启动, 无 COM 需求的批次零开销)。"""
        if self._excel is None:
            try:
                import win32com.client
            except ImportError as error:
                raise FSAError("未安装 pywin32，无法使用 Excel COM 读取加密文件") from error
            # 与 _read_excel_com_sync 相同的 pythoncom 初始化模式 (异常收窄为
            # com_error/OSError, 禁止宽 catch)
            try:
                import pythoncom as _pythoncom
            except ImportError:
                _pythoncom = None
            self._pythoncom = _pythoncom
            self._co_initialized = False
            if _pythoncom is not None:
                com_error = getattr(_pythoncom, "com_error", OSError)
                try:
                    _pythoncom.CoInitialize()
                    self._co_initialized = True
                except (com_error, OSError):
                    self._co_initialized = False
            if self._pid_snapshot is None:
                # 首次启动前的 EXCEL.EXE 快照: 之后用于识别「本会话新增的
                # 不可见残留实例」并清理 (绝不触碰用户可见 Excel)
                self._pid_snapshot = _snapshot_excel_pids()
            try:
                excel_obj = cast(
                    "_ExcelAppProtocol",
                    win32com.client.DispatchEx("Excel.Application"),
                )
            except Exception as error:
                raise FSAError(f"无法启动 Excel 进程: {error}") from error
            # 属性配置"先配置后提交 + 尽力而为": Excel 启动繁忙时属性写入会被
            # dynamic dispatch 拒绝 (AttributeError), 属瞬态噪声而非致命错误;
            # 此前在此处硬失败会把残缺实例提交进会话, 毒化整批导入
            # (2026-09-17 "每一个导入都失败"回归根因)
            for prop in ("Visible", "DisplayAlerts", "AskToUpdateLinks"):
                try:
                    setattr(excel_obj, prop, False)
                except Exception as error:  # noqa: BLE001 - COM 属性写入异常类型不统一, 配置属尽力而为
                    logger.warning(f"Excel COM 属性 {prop} 设置失败 (忽略继续): {error}")
            self._excel = excel_obj
        return self._excel

    def read_file(
        self,
        file_path: str,
        progress_cb: Callable[[int, int], None] | None = None,
    ) -> dict[str, RawSheetData]:
        """用共享 Excel 进程读取一个文件 (自动化被阻塞时自愈重试)。

        重试策略 (2026-09-17 实测调优):
        1. 首次失败: 丢弃坏实例 + 清理本会话产生的不可见残留, 换新实例重试;
        2. 仍失败: 常见根因是环境中残留的不可见 Excel 僵尸 (含其他会话遗留)
           阻塞 COM, 自动清理全部不可见残留后做最后一次重试;
        3. 仍失败: 抛中文业务异常, 单文件失败不毒化批次其余文件。
        """
        try:
            excel = self._ensure_started()
            return _read_workbook_sheets(excel, str(file_path), progress_cb)
        except FSAError as error:
            self._reset_broken(str(error))
            excel = self._ensure_started()
            try:
                return _read_workbook_sheets(excel, str(file_path), progress_cb)
            except FSAError as retry_error:
                killed = cleanup_invisible_excel()
                if not killed:
                    raise retry_error from error
                logger.info(f"清理 {killed} 个残留 Excel 实例后进行最后一次重试")
                self._excel = None
                excel = self._ensure_started()
                return _read_workbook_sheets(excel, str(file_path), progress_cb)

    def _reset_broken(self, cause: str) -> None:
        """丢弃疑似死亡的共享 Excel 引用, 并清理本会话产生的不可见残留实例。"""
        logger.warning(f"共享 Excel 进程疑似不可用, 将重启新实例重试: {cause}")
        if self._excel is not None:
            try:
                self._excel.Quit()
            except Exception as error:  # noqa: BLE001 - 坏引用的 Quit 允许失败
                logger.debug(f"丢弃不可用 Excel 引用时 Quit 失败 (忽略): {error}")
                self._cleanup_own_zombies()
            self._excel = None

    def _cleanup_own_zombies(self) -> None:
        """结束本会话产生的不可见 Excel 残留实例 (绝不触碰用户可见窗口)。

        Quit 失败时坏实例会变成不可见僵尸进程阻塞后续 COM 调用,
        只清理「快照之后新增且无可见窗口」的实例, 保证不误杀用户 Excel。
        """
        if self._pid_snapshot is None:
            return
        try:
            new_pids = _snapshot_excel_pids() - self._pid_snapshot
            if not new_pids:
                return
            own_zombies = new_pids - _visible_excel_pids()
            if own_zombies:
                killed = _kill_pids(own_zombies)
                if killed:
                    logger.info(f"已清理 {killed} 个残留的不可见 Excel 实例")
        except Exception as error:  # noqa: BLE001 - 清理失败不影响主流程
            logger.debug(f"清理残留 Excel 实例失败 (忽略): {error}")

    def close(self) -> None:
        """关闭共享 Excel 进程并回收 COM 线程资源 (幂等, 未启动时为空操作)。"""
        if self._excel is not None:
            try:
                self._excel.Quit()
            except Exception as error:  # noqa: BLE001 - 关闭阶段异常不掩盖业务结果
                logger.warning(f"关闭共享 Excel 进程时出现异常 (可忽略): {error}")
                # Quit 失败会留下不可见僵尸阻塞后续所有自动化, 立即清理
                self._cleanup_own_zombies()
            self._excel = None
        if self._pythoncom is not None and self._co_initialized:
            self._pythoncom.CoUninitialize()
            self._co_initialized = False


def _read_workbook_sheets(
    excel: _ExcelAppProtocol,
    file_path: str,
    progress_cb: Callable[[int, int], None] | None,
) -> dict[str, RawSheetData]:
    """在已启动的 Excel 实例上打开并读取一个工作簿 (单文件与会话共用)。"""
    try:
        workbook = excel.Workbooks.Open(file_path, UpdateLinks=0, ReadOnly=True, AddToMru=False)  # type: ignore[union-attr]
    except Exception as error:
        raise FSAError(f"Excel 无法打开文件「{file_path}」: {error}") from error

    result: dict[str, RawSheetData] = {}
    try:
        try:
            sheet_count = workbook.Worksheets.Count
            if progress_cb is not None:
                progress_cb(0, sheet_count)
            for completed, sheet in enumerate(workbook.Worksheets, 1):
                used_range = sheet.UsedRange
                # UsedRange 的左上角不保证是 A1 (工作表顶部可能有空行被裁掉):
                # UsedRange.Value 返回的矩阵以 UsedRange 首行为第 0 行, 需把
                # 起始行偏移 (UsedRange.Row - 1) 传回, 否则 _row 源行号整体偏小,
                # 追溯定位会指向错误的 Excel 行 (P3)。
                row_offset = int(used_range.Row) - 1
                matrix = _com_range_to_matrix(used_range.Value)
                result[sheet.Name] = _matrix_to_raw(sheet.Name, matrix, row_offset=row_offset)
                if progress_cb is not None:
                    progress_cb(completed, sheet_count)
        except Exception as error:
            # COM 异常类型不统一 (pywintypes.com_error 等), 统一转为中文业务异常;
            # 会话模式下无守护线程兜底, 此处不包装会让裸 com_error 逃逸到 GUI 层
            raise FSAError(f"Excel COM 读取工作表失败「{file_path}」: {error}") from error
    finally:
        try:
            workbook.Close(SaveChanges=False)
        except Exception as error:  # noqa: BLE001 - Excel 进程异常后 Close 可能失败, 不掩盖读取结果
            logger.warning(f"关闭工作簿失败 (可忽略): {file_path}: {error}")
    logger.info(f"Excel COM 读取完成，共 {len(result)} 个工作表")
    return result


def _read_native(path: str) -> dict[str, RawSheetData]:
    """用 openpyxl / pandas+xlrd 常规读取 Excel 文件。

    .xlsx/.xlsm 大文件 (>5MB) 优先 read_only 流式读取; 流式读取失败
    (某些加密/兼容性文件) 时回落普通模式, 再由 read_excel 的 COM 回退兜底。
    """
    suffix = Path(path).suffix.lower()
    if suffix == ".csv":
        return _read_csv(path)
    if suffix == ".xls":
        return _read_xls(path)
    # .xlsx / .xlsm 均由 openpyxl 读取 (含宏文件的数据部分)
    try:
        size = os.path.getsize(path)
    except OSError as e:
        raise FileNotFoundError(f"无法打开文件「{path}」: {e}") from e
    if size >= _LARGE_FILE_THRESHOLD:
        try:
            return _read_openpyxl(path, read_only=True)
        except (OSError, ValueError, KeyError, TypeError) as e:
            logger.warning(f"大文件流式读取失败, 回落普通模式: {path} ({e})")
    return _read_openpyxl(path, read_only=False)


def _read_openpyxl(path: str, read_only: bool) -> dict[str, RawSheetData]:
    """openpyxl 读取 .xlsx/.xlsm, 支持 read_only 流式模式。"""
    logger.info(f"正在读取 Excel 文件: {path} (read_only={read_only})")
    try:
        wb = openpyxl.load_workbook(path, data_only=True, read_only=read_only)
    except FileNotFoundError:
        raise
    except OSError as e:
        raise FileNotFoundError(f"无法打开文件「{path}」: {e}") from e

    result: dict[str, RawSheetData] = {}
    for sheet_name in wb.sheetnames:
        matrix = _sheet_to_matrix(wb[sheet_name])
        raw = _matrix_to_raw(sheet_name, matrix)
        result[sheet_name] = raw
        logger.debug(f"  工作表「{sheet_name}」: {len(raw.rows)} 行数据")

    wb.close()
    logger.info(f"读取完成，共 {len(result)} 个工作表")
    return result


def _sheet_to_matrix(worksheet: Worksheet) -> list[list[object]]:
    """将 openpyxl 工作表转换为二维矩阵（行优先）。

    使用 iter_rows(values_only=True) 批量读取, 避免逐单元格 cell() 调用;
    大工作表下性能可提升一个数量级。
    """
    return [list(row) for row in worksheet.iter_rows(values_only=True)]


def _read_xls(path: str) -> dict[str, RawSheetData]:
    """通过 pandas + xlrd 读取旧版 .xls 文件。"""
    try:
        import pandas as pd
    except ImportError as e:
        raise ImportError("读取 .xls 需要安装 pandas 与 xlrd") from e

    logger.info(f"正在读取 .xls 文件: {path}")
    try:
        sheets = pd.read_excel(path, sheet_name=None, header=None, dtype=object, engine="xlrd")
    except OSError as e:
        raise FileNotFoundError(f"无法打开文件「{path}」: {e}") from e

    result: dict[str, RawSheetData] = {}
    for sheet_name, frame in sheets.items():
        matrix = [[cell for cell in row] for row in frame.values.tolist()]
        raw = _matrix_to_raw(sheet_name, matrix)
        result[sheet_name] = raw
        logger.debug(f"  工作表「{sheet_name}」: {len(raw.rows)} 行数据")

    logger.info(f".xls 读取完成，共 {len(result)} 个工作表")
    return result


def _read_csv(path: str) -> dict[str, RawSheetData]:
    """读取 CSV 文件 (UTF-8/GBK 编码探测), 转换为单工作表 RawSheetData。"""
    text = _read_csv_text(path)
    rows = list(csv.reader(text.splitlines(), skipinitialspace=True))
    if not rows:
        raise FSAError(f"CSV 文件「{path}」为空")
    matrix: list[list[object]] = [[cell if cell != "" else None for cell in row] for row in rows]
    # 空值统一为 None, 与 Excel 读取路径行为一致
    sheet_name = Path(path).stem
    raw = _matrix_to_raw(sheet_name, matrix)
    logger.info(f"CSV 读取完成: 工作表「{sheet_name}」, {len(raw.rows)} 行数据")
    return {sheet_name: raw}


def _read_csv_text(path: str) -> str:
    """按 UTF-8(含 BOM)/GBK 顺序探测 CSV 文本编码。"""
    try:
        data = Path(path).read_bytes()
    except OSError as e:
        raise FileNotFoundError(f"无法打开文件「{path}」: {e}") from e
    for encoding in ("utf-8-sig", "gbk", "utf-8"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise FSAError(f"CSV 文件「{path}」编码无法识别 (已尝试 UTF-8/GBK)")


def _matrix_to_raw(
    name: str, matrix: list[list[object]], row_offset: int = 0
) -> RawSheetData:
    """从二维矩阵构建 RawSheetData（openpyxl 与 pandas 路径共用）。

    row_offset: 矩阵第 0 行在源文件中的实际行号 - 1（COM UsedRange 偏移），
        用于把 `_row` 还原为源文件 1-based 行号。
    """
    if not matrix:
        return RawSheetData(name=name, headers=[], header_rows=[], rows=[])
    header_idx = _find_header_row(matrix)
    header_rows = _capture_header_rows(matrix, header_idx)
    headers = _uniquify(_merged_headers(header_rows))
    rows = _build_rows(matrix, headers, header_idx + len(header_rows), row_offset)
    return RawSheetData(name=name, headers=headers, header_rows=header_rows, rows=rows)


def _merged_headers(header_rows: list[list[str]]) -> list[str]:
    """把多层表头按列纵向合并为单层列名。

    例如:
        行1: 项目 | 期末余额 | 年初余额
        行2:      | 2024年   | 2023年
    合并为:  项目 | 期末余额2024年 | 年初余额2023年

    这样后续"候选词包含匹配"仍能命中"期末余额/年初余额"等标准列名,
    同时合并单元格留下的空位 (仅左上角有值) 也能取到下层标签。
    只有一层表头时与原有 _to_header_list 行为一致。
    """
    if not header_rows:
        return []
    column_count = max((len(row) for row in header_rows), default=0)
    headers: list[str] = []
    for col_idx in range(column_count):
        parts: list[str] = []
        for row in header_rows:
            if col_idx >= len(row):
                continue
            label = str(row[col_idx]).strip() if row[col_idx] is not None else ""
            if label:
                parts.append(label)
        headers.append("".join(parts) if parts else f"列{col_idx + 1}")
    return headers


def _find_header_row(matrix: list[list[object]]) -> int:
    """在矩阵前若干行中定位表头行。

    优先返回含"项目/科目"类单元格的行；若不存在（如资产负债表的
    "资 产 | 行次 | 期末余额 | 年初余额"表头），则回退到含金额列
    关键词的行；仍找不到时返回第 1 行。
    """
    for row_idx in range(min(_MAX_SCAN_ROWS, len(matrix))):
        normalized = [_normalize_cell(cell) for cell in matrix[row_idx]]
        if any(value in _NAME_HEADER_CANDIDATES for value in normalized if value):
            return row_idx

    for row_idx in range(min(_MAX_SCAN_ROWS, len(matrix))):
        joined = "".join(_normalize_cell(cell) for cell in matrix[row_idx])
        if any(keyword in joined for keyword in _AMOUNT_HEADER_KEYWORDS):
            return row_idx

    return 0


def _capture_header_rows(matrix: list[list[object]], header_idx: int) -> list[list[str]]:
    """捕获从表头行开始的连续多层表头。

    子表头行判定: 首列为空且行内存在非空标签（如权益变动表的
    "股本/资本公积"层与"优先股/永续债"层）。遇到首列非空的行
    （数据行）即停止。
    """
    header_rows = [_to_header_list(matrix[header_idx], fill_empty=False)]
    for offset in range(1, _MAX_HEADER_LAYERS):
        row_idx = header_idx + offset
        if row_idx >= len(matrix):
            break
        cells = matrix[row_idx]
        if _contains_number(cells):
            break
        first = _normalize_cell(cells[0]) if cells else ""
        if first:
            break
        if not any(_normalize_cell(cell) for cell in cells):
            break
        header_rows.append(_to_header_list(cells, fill_empty=False))
    return header_rows


def _contains_number(cells: list[object]) -> bool:
    """判断一行是否包含数值（数据行特征，用于停止多层表头捕获）。"""
    return any(isinstance(cell, (int, float)) and not isinstance(cell, bool) for cell in cells)


def _build_rows(
    matrix: list[list[object]],
    headers: list[str],
    start_idx: int,
    row_offset: int = 0,
) -> list[dict[str, object]]:
    """从表头之后开始，将矩阵行转换为以列标题为键的字典列表。

    row_offset 为矩阵相对源文件的行偏移 (COM UsedRange 起始行 - 1)。
    """
    rows: list[dict[str, object]] = []
    for row_idx in range(start_idx, len(matrix)):
        cells = matrix[row_idx]
        row_data: dict[str, object] = {"_row": row_idx + 1 + row_offset}
        has_value = False
        for col_idx, header in enumerate(headers):
            value = cells[col_idx] if col_idx < len(cells) else None
            if value is not None:
                has_value = True
            row_data[header] = value
        if has_value:
            rows.append(row_data)
    return rows


def _to_header_list(cells: Sequence[object], fill_empty: bool) -> list[str]:
    """将一行单元格转换为列标题列表。

    Args:
        cells: 一行单元格
        fill_empty: 空单元格是否用「列N」占位（headers 需要，多层表头标签不需要）
    """
    headers: list[str] = []
    for col_idx, cell in enumerate(cells, 1):
        if cell is None or str(cell).strip() == "":
            headers.append(f"列{col_idx}" if fill_empty else "")
        else:
            headers.append(str(cell))
    return headers


def _uniquify(headers: list[str]) -> list[str]:
    """为重复的列标题追加序号后缀，避免按列名建 dict 时互相覆盖。

    例如资产负债表的左右两栏都叫「期末余额」，处理后变为
    「期末余额」与「期末余额#2」。
    """
    counts: dict[str, int] = {}
    result: list[str] = []
    for header in headers:
        count = counts.get(header, 0) + 1
        counts[header] = count
        result.append(header if count == 1 else f"{header}#{count}")
    return result


def _normalize_cell(value: object) -> str:
    """去除单元格文本中所有空白（含全角空格），用于表头匹配。"""
    if value is None:
        return ""
    return re.sub(r"\s+", "", str(value))


def read_excel_com(
    file_path: str,
    timeout: float | None = 60.0,
    progress_cb: Callable[[int, int], None] | None = None,
) -> dict[str, RawSheetData]:
    """通过 Excel COM（pywin32）读取 Excel 文件。

    适用于透明加密环境（如 DLP）：openpyxl/xlrd 看到的是密文，
    而 Excel 本体被加密客户端信任，可透明解密。

    COM 调用是阻塞式的, 这里放到独立 daemon 线程执行并用 join(timeout)
    施加软超时: 超时后本函数立即返回错误, 后台线程会在 Excel 响应后自行
    关闭进程 (Python 无法强杀线程, 这是 Windows COM 场景的务实取舍)。

    Args:
        file_path: Excel 文件路径（.xlsx / .xls / .xlsm）
        timeout: 超时秒数; None 表示不限时
        progress_cb: 进度回调 (已完成工作表数, 工作表总数)

    Returns:
        字典，键为工作表名称，值为 RawSheetData

    Raises:
        FSAError: 未安装 pywin32、无法启动 Excel、文件无法打开或超时
    """
    try:
        import win32com.client  # noqa: F401 - 仅探测依赖是否可用
    except ImportError as error:
        raise FSAError("未安装 pywin32，无法使用 Excel COM 读取加密文件") from error

    box: dict[str, object] = {}

    def work() -> None:
        try:
            box["data"] = _read_excel_com_sync(str(file_path), progress_cb)
        except Exception as exc:
            box["error"] = exc

    thread = threading.Thread(target=work, daemon=True, name="excel-com-reader")
    thread.start()
    thread.join(timeout)
    if thread.is_alive():
        raise FSAError("Excel COM 读取超时，请关闭占用中的 Excel 窗口后重试")
    err = box.get("error")
    if err is not None:
        if not isinstance(err, BaseException):
            raise FSAError(f"Excel COM 读取失败: {err}")
        if isinstance(err, FSAError):
            raise err
        raise FSAError(f"Excel COM 读取失败: {err}") from err
    return cast("dict[str, RawSheetData]", box["data"])


def _read_excel_com_sync(
    file_path: str,
    progress_cb: Callable[[int, int], None] | None = None,
) -> dict[str, RawSheetData]:
    """在调用线程内执行 Excel COM 读取 (不得直接调用, 经 read_excel_com 包装)。"""
    try:
        import win32com.client
    except ImportError as error:
        raise FSAError("未安装 pywin32，无法使用 Excel COM 读取加密文件") from error

    pythoncom: ModuleType | None
    co_initialized = False
    try:
        import pythoncom as _pythoncom

        pythoncom = _pythoncom
    except ImportError:
        pythoncom = None
    if pythoncom is not None:
        # pywin32 存根不含 com_error 属性, 经 getattr 取回退 OSError
        com_error = getattr(pythoncom, "com_error", OSError)
        try:
            pythoncom.CoInitialize()
            co_initialized = True
        except (com_error, OSError):
            co_initialized = False

    path = str(file_path)
    excel = None
    try:
        try:
            excel = win32com.client.DispatchEx("Excel.Application")
        except Exception as error:
            # 防御性兜底: pywintypes.com_error 等 COM 异常类型不统一,
            # 且不同 Excel 版本差异大, 统一转为中文业务异常 (见 7.1 DLP)
            raise FSAError(f"无法启动 Excel 进程: {error}") from error
        excel.Visible = False
        excel.DisplayAlerts = False
        excel.AskToUpdateLinks = False
        try:
            workbook = excel.Workbooks.Open(path, UpdateLinks=0, ReadOnly=True, AddToMru=False)
        except Exception as error:  # COM 异常类型不统一，统一转为业务异常
            raise FSAError(f"Excel 无法打开文件「{path}」: {error}") from error

        result: dict[str, RawSheetData] = {}
        try:
            sheet_count = workbook.Worksheets.Count
            if progress_cb is not None:
                progress_cb(0, sheet_count)
            for completed, sheet in enumerate(workbook.Worksheets, 1):
                used_range = sheet.UsedRange
                # UsedRange 的左上角不保证是 A1 (工作表顶部可能有空行被裁掉):
                # UsedRange.Value 返回的矩阵以 UsedRange 首行为第 0 行, 需把
                # 起始行偏移 (UsedRange.Row - 1) 传回, 否则 _row 源行号整体偏小,
                # 追溯定位会指向错误的 Excel 行 (P3)。
                row_offset = int(used_range.Row) - 1
                matrix = _com_range_to_matrix(used_range.Value)
                result[sheet.Name] = _matrix_to_raw(sheet.Name, matrix, row_offset=row_offset)
                if progress_cb is not None:
                    progress_cb(completed, sheet_count)
        finally:
            workbook.Close(SaveChanges=False)
        logger.info(f"Excel COM 读取完成，共 {len(result)} 个工作表")
        return result
    finally:
        if excel is not None:
            excel.Quit()
        if pythoncom is not None and co_initialized:
            pythoncom.CoUninitialize()


def _com_range_to_matrix(value: object) -> list[list[object]]:
    """将 Excel COM Range.Value 转换为行优先二维矩阵。"""
    if value is None:
        return []
    if not isinstance(value, (tuple, list)):
        return [[value]]
    matrix: list[list[object]] = []
    for row in value:
        row_values = list(row) if isinstance(row, (tuple, list)) else [row]
        matrix.append(list(row_values))
    return matrix
