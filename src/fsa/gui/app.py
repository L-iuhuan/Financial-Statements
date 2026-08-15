"""应用入口: 创建 QApplication, 加载规则, 显示主窗口。

启动方式:
    python -m fsa
"""

from __future__ import annotations

import os
import sys
import threading
from types import TracebackType

from loguru import logger
from PySide6.QtCore import QObject, QSettings, Qt, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication
from qfluentwidgets import InfoBar, InfoBarPosition

from fsa.core.version import APP_VERSION
from fsa.gui.app_state import AppState
from fsa.gui.main_window import MainWindow
from fsa.gui.theme import apply_theme, get_qss
from fsa.updater.updater import UpdateError, Updater


def _is_system_dark() -> bool:
    """检测系统是否为暗色模式。"""
    try:
        from PySide6.QtGui import QGuiApplication
        style_hints = QGuiApplication.styleHints()
        if hasattr(style_hints, "colorScheme"):
            return style_hints.colorScheme() == Qt.ColorScheme.Dark
    except (RuntimeError, AttributeError) as e:
        # 防御性兜底: QGuiApplication 未就绪或缺 colorScheme 时无法判定,
        # 一律按亮色处理, 不影响启动 (仅记录调试日志)
        logger.debug(f"系统暗色模式检测失败, 按亮色处理: {e}")
    return False


def _get_startup_theme() -> tuple[bool, str]:
    """返回启动时应使用的主题 (dark?, mode)。"""
    settings = QSettings("FSA", "FinancialAudit")
    mode = str(settings.value("theme_mode", "light"))
    if mode == "auto":
        return _is_system_dark(), mode
    return mode == "dark", mode


class _UpdateCheckBridge(QObject):
    """后台更新检查结果回传桥 (worker 线程 -> GUI 线程)。"""

    finished = Signal(str, str)  # (status, detail); status: update / error / latest


def _schedule_startup_update_check(window: MainWindow, settings: QSettings) -> None:
    """启动后延迟执行一次更新检查, 不阻塞主窗口。

    仅在设置了更新清单地址时检查; 发现新版本以 InfoBar 提示,
    检查失败只记录日志, 不打扰用户。
    """
    url = str(settings.value("update_manifest_url", "")).strip()
    if not url:
        return

    bridge = _UpdateCheckBridge(window)
    # 挂到主窗口上, 防止桥对象被 GC; finished 信号在 GUI 线程处理
    window._startup_update_bridge = bridge

    def run() -> None:
        try:
            info = Updater(
                manifest_url=url, current_version=APP_VERSION, timeout=5.0
            ).check_for_update()
        except UpdateError as e:
            logger.warning(f"启动更新检查失败: {e}")
            bridge.finished.emit("error", str(e))
            return
        if info.has_update:
            bridge.finished.emit(
                "update",
                f"发现新版本 {info.latest_version}，请前往「系统设置 → 软件更新」下载。",
            )
        else:
            bridge.finished.emit("latest", "已是最新版本")

    def on_finished(status: str, detail: str) -> None:
        if status == "update":
            InfoBar.info(
                "发现新版本",
                detail,
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=6000,
                parent=window,
            )
        elif status == "error":
            logger.debug(f"启动更新检查未完成: {detail}")

    bridge.finished.connect(on_finished)

    def start_worker() -> None:
        threading.Thread(target=run, daemon=True).start()

    QTimer.singleShot(1200, start_worker)


def main() -> None:
    """启动财务报表勾稽校验系统。"""

    def exception_hook(
        exctype: type[BaseException], value: BaseException, tb: TracebackType | None
    ) -> None:
        logger.error(f"未处理异常: {value}", exc_info=(exctype, value, tb))
        sys.__excepthook__(exctype, value, tb)

    sys.excepthook = exception_hook

    # 高 DPI: Qt6 默认启用缩放。RoundPreferFloor 将分数缩放因子向下取整到整数倍,
    # 避免 125%/150% 等分数缩放时 Qt 用次像素插值渲染, 导致字体发虚/粗细不一。
    # 副作用: 界面元素可能略小于系统预期, 但对财务数据表格的可读性更有利。
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.RoundPreferFloor
    )

    app = QApplication(sys.argv)
    app.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
    # 全局 UI 字体与 theme.py 保持一致: Microsoft YaHei UI 为主族,
    # 像素尺寸统一, 垂直 hinting + 抗锯齿优先, 减轻横竖笔画粗细不均问题。
    font = QFont("Microsoft YaHei UI")
    font.setPixelSize(13)
    font.setWeight(QFont.Weight.Normal)
    font.setHintingPreference(QFont.HintingPreference.PreferVerticalHinting)
    font.setStyleStrategy(
        QFont.StyleStrategy.PreferAntialias | QFont.StyleStrategy.PreferQuality
    )
    app.setFont(font)

    dark, mode = _get_startup_theme()
    apply_theme(dark=dark)
    app.setStyleSheet(get_qss(dark))

    state = AppState()
    ok, msg = state.load_registry()
    if not ok:
        logger.warning(f"规则库加载失败: {msg}")

    # 加载存储的默认容差
    import contextlib
    settings = QSettings("FSA", "FinancialAudit")
    tol_str = str(settings.value("default_tolerance", "0.01"))
    with contextlib.suppress(ValueError):
        state.set_default_tolerance(float(tol_str))

    window = MainWindow(state, initial_dark=dark, theme_mode=mode)
    window.show()

    # 启动后异步检查更新 (设置了内网更新清单地址时才执行)
    _schedule_startup_update_check(window, settings)

    # 规则库加载失败: 主窗口就绪后再提示用户 (中文, 可感知)
    if not ok:
        InfoBar.error(
            "规则库加载失败",
            f"勾稽规则库未能加载，校验功能可能不可用，请重新安装或联系管理员。\n{msg}",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=8000,
            parent=window,
        )

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
