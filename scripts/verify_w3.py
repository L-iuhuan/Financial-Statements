"""W3 端到端验证: offscreen 启动 GUI，导入真实报表，触发校验，截图断言。"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from pathlib import Path

from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication, QFrame, QTableWidget

from fsa.gui.app_state import AppState
from fsa.gui.main_window import MainWindow
from fsa.gui.theme import get_qss


_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_REPORT_FILE = _PROJECT_ROOT / "tests" / "fixtures" / "real_reports" / "贵州茅台_2023年报_三大报表.xlsx"


def mean_brightness(pixmap) -> float:
    img = pixmap.toImage().convertToFormat(QImage.Format.Format_RGB32)
    w, h = img.width(), img.height()
    if w == 0 or h == 0:
        return 0.0
    total = 0
    count = 0
    for y in range(0, h, 4):
        for x in range(0, w, 4):
            c = img.pixelColor(x, y)
            total += (c.red() + c.green() + c.blue()) / 3
            count += 1
    return total / count if count else 0.0


def find_widgets(parent, cls, object_name: str | None = None):
    """递归查找指定类型和 objectName 的 widget。"""
    results = []
    for child in parent.findChildren(cls):
        if object_name is None or child.objectName() == object_name:
            results.append(child)
    return results


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyleSheet(get_qss(False))

    state = AppState()
    ok, msg = state.load_registry()
    if not ok:
        print(f"规则库加载失败: {msg}")
        return 1

    window = MainWindow(state, initial_dark=False, theme_mode="light")
    window.resize(1280, 800)
    window.show()

    # 1. 导入真实报表
    if not _REPORT_FILE.exists():
        print(f"报表文件不存在: {_REPORT_FILE}")
        return 1

    window._import_page._on_file(str(_REPORT_FILE))
    window.repaint()
    light_import = window.grab()
    light_import.save("verify_w3_light_import.png")
    print(f"Light import brightness: {mean_brightness(light_import):.1f}")

    # 断言: 至少 3 张 ReportCard
    report_cards = find_widgets(window, QFrame, "ReportCard")
    print(f"ReportCards found: {len(report_cards)}")
    assert len(report_cards) >= 3, f"期望至少 3 张 ReportCard，实际 {len(report_cards)}"

    # 2. 触发校验
    window._import_page.trigger_validate()
    window.repaint()
    light_validated = window.grab()
    light_validated.save("verify_w3_light_validated.png")
    print(f"Light validated brightness: {mean_brightness(light_validated):.1f}")

    # 断言: 截图非空
    assert light_validated.width() > 0 and light_validated.height() > 0

    # 3. 切换到规则页截图
    window._on_nav("navRules")
    window.repaint()
    light_rules = window.grab()
    light_rules.save("verify_w3_light_rules.png")
    print(f"Light rules brightness: {mean_brightness(light_rules):.1f}")
    assert light_rules.width() > 0 and light_rules.height() > 0

    # 4. 切换到审计底稿页截图
    window._on_nav("navAudit")
    window.repaint()
    light_audit = window.grab()
    light_audit.save("verify_w3_light_audit.png")
    print(f"Light audit brightness: {mean_brightness(light_audit):.1f}")
    assert light_audit.width() > 0 and light_audit.height() > 0

    # 5. 断言 trace 表格存在 (在 ResultCard 中)
    window._on_nav("navImport")
    window.repaint()
    trace_tables = find_widgets(window, QTableWidget, "TraceTable")
    print(f"TraceTables found: {len(trace_tables)}")
    assert len(trace_tables) > 0, "期望至少 1 个 TraceTable"

    print("\nPASS")
    app.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
