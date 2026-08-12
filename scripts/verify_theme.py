"""深色主题验证: 截图亮度对比。"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage

from fsa.gui.app_state import AppState
from fsa.gui.main_window import MainWindow
from fsa.gui.theme import get_qss


def mean_brightness(pixmap) -> float:
    img = pixmap.toImage().convertToFormat(QImage.Format.Format_RGB32)
    w, h = img.width(), img.height()
    total = 0
    for y in range(0, h, 4):
        for x in range(0, w, 4):
            c = img.pixelColor(x, y)
            total += (c.red() + c.green() + c.blue()) / 3
    return total / ((w // 4) * (h // 4))


app = QApplication(sys.argv)
app.setStyleSheet(get_qss(False))  # 模拟 app.py 真实启动
state = AppState()
state.load_registry()
window = MainWindow(state)
window.resize(1280, 800)
window.show()

window._on_nav("navImport")
window.repaint()
light = window.grab()
light.save("verify_light_import.png")
light_mean = mean_brightness(light)
print(f"Light import mean brightness: {light_mean:.1f}")

window._toggle_theme()
window.repaint()
dark = window.grab()
dark.save("verify_dark_import.png")
dark_mean = mean_brightness(dark)
print(f"Dark import mean brightness: {dark_mean:.1f}")

window._on_nav("navSettings")
window.repaint()
dark_settings = window.grab()
dark_settings.save("verify_dark_settings.png")
ds_mean = mean_brightness(dark_settings)
print(f"Dark settings mean brightness: {ds_mean:.1f}")

ratio = dark_mean / light_mean if light_mean else 1
print(f"\nDark/Light ratio: {ratio:.2%}")
print("PASS" if ratio < 0.6 and ds_mean < 100 else "FAIL (dark theme not applied)")
app.quit()
