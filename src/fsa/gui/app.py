"""应用入口: 创建 QApplication, 加载规则, 显示主窗口。

启动方式:
    python -m fsa
"""

from __future__ import annotations

import os
import sys

from loguru import logger
from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from fsa.gui.app_state import AppState
from fsa.gui.main_window import MainWindow
from fsa.gui.theme import apply_theme, get_qss


def _is_system_dark() -> bool:
    """检测系统是否为暗色模式。"""
    try:
        from PySide6.QtGui import QGuiApplication
        style_hints = QGuiApplication.styleHints()
        if hasattr(style_hints, "colorScheme"):
            return style_hints.colorScheme() == Qt.ColorScheme.Dark
    except Exception:
        pass
    return False


def _get_startup_theme() -> tuple[bool, str]:
    """返回启动时应使用的主题 (dark?, mode)。"""
    settings = QSettings("FSA", "FinancialAudit")
    mode = str(settings.value("theme_mode", "light"))
    if mode == "auto":
        return _is_system_dark(), mode
    return mode == "dark", mode


def main() -> None:
    """启动财务报表勾稽校验系统。"""

    def exception_hook(exctype, value, tb) -> None:
        logger.error(f"未处理异常: {value}", exc_info=(exctype, value, tb))
        sys.__excepthook__(exctype, value, tb)

    sys.excepthook = exception_hook

    # 高 DPI: Qt6 默认启用缩放，取整策略避免分数缩放导致的字体发虚
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.RoundPreferFloor
    )

    app = QApplication(sys.argv)
    app.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
    font = QFont("Microsoft YaHei UI", 10)
    font.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
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

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
