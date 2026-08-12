"""UX 评估: 全页面双主题截图。"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication
from fsa.gui.app_state import AppState
from fsa.gui.main_window import MainWindow
from fsa.gui.theme import get_qss

app = QApplication(sys.argv)
app.setStyleSheet(get_qss(False))
state = AppState()
state.load_registry()
window = MainWindow(state)
window.resize(1280, 800)
window.show()

# 导入+校验, 获得有数据的状态
window._import_page._on_file("tests/fixtures/real_reports/贵州茅台_2023年报_三大报表.xlsx")
window._import_page.trigger_validate()
app.processEvents()

os.makedirs("ux_shots", exist_ok=True)
pages = [("navImport","import"),("navAudit","audit"),("navRules","rules"),("navHistory","history"),("navSettings","settings")]

# 浅色主题全页面
for nav, name in pages:
    window._on_nav(nav)
    app.processEvents()
    window.repaint()
    window.grab().save(f"ux_shots/light_{name}.png")
print("light pages done")

# AI 抽屉打开 (浅色)
window._on_nav("navImport")
window._open_drawer()
app.processEvents()
window.repaint()
window.grab().save("ux_shots/light_agent_open.png")
window._close_drawer()

# 展开一个不通过卡片 (如果有) - 茅台全通过, 展开第一个卡片看详情
ip = window._import_page
if ip._cards_layout.count() > 0:
    first = ip._cards_layout.itemAt(0).widget()
    if first and hasattr(first, 'toggle_expanded'):
        if not first._expanded:
            first.toggle_expanded()
        app.processEvents()
        window.repaint()
        window.grab().save("ux_shots/light_card_expanded.png")

# 深色主题全页面
window._toggle_theme()
app.processEvents()
for nav, name in pages:
    window._on_nav(nav)
    app.processEvents()
    window.repaint()
    window.grab().save(f"ux_shots/dark_{name}.png")
print("dark pages done")

# 深色 AI 抽屉
window._on_nav("navImport")
window._open_drawer()
app.processEvents()
window.repaint()
window.grab().save("ux_shots/dark_agent_open.png")

print("UX shots saved to ux_shots/")
app.quit()
