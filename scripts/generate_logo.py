"""生成应用 Logo: 极简粗体对勾 + 圆角方形底, 钢蓝灰品牌色。

设计原则:
- 1-2 个几何元素: 圆角方形底 + 单一路径粗对勾
- 小尺寸(16-32px)下仍保持强剪影辨识度
- 放弃天平等多细节具象图案

产出:
- resources/logo.svg  (矢量源文件)
- resources/logo_256.png  (窗口/任务栏图标)
- resources/logo_32.png, logo_48.png, logo_64.png
- resources/app.ico  (PyInstaller/安装器图标, 多尺寸)

用法: python scripts/generate_logo.py
"""

from __future__ import annotations

from pathlib import Path

import cairosvg
from PIL import Image

# 品牌钢蓝灰 (与 theme.py brand_600 一致)
TEAL = "#3e5f8f"
TEAL_DARK = "#2e4f77"
TEAL_LIGHT = "#6b8fc5"

# 极简标记: 粗体圆角对勾, 强剪影
_SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" width="256" height="256">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="{TEAL_LIGHT}"/>
      <stop offset="0.5" stop-color="{TEAL}"/>
      <stop offset="1" stop-color="{TEAL_DARK}"/>
    </linearGradient>
  </defs>
  <!-- 圆角方形底: 强剪影 -->
  <rect x="10" y="10" width="236" height="236" rx="56" fill="url(#bg)"/>
  <!-- 粗体对勾: 单一路径, 圆角端点, 小尺寸下仍可辨识 -->
  <path d="M70 132 L116 178 L186 88" stroke="#ffffff" stroke-width="32" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
</svg>
"""

_OUT_DIR = Path(__file__).resolve().parent.parent / "resources"


def main() -> None:
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    svg_path = _OUT_DIR / "logo.svg"
    svg_path.write_text(_SVG, encoding="utf-8")
    print(f"已生成: {svg_path}")

    # SVG -> 多尺寸 PNG
    sizes = [32, 48, 64, 128, 256]
    png_paths: list[Path] = []
    for size in sizes:
        png = _OUT_DIR / f"logo_{size}.png"
        cairosvg.svg2png(
            url=str(svg_path), write_to=str(png),
            output_width=size, output_height=size,
        )
        png_paths.append(png)
        print(f"已生成: {png}")

    # 多尺寸 PNG -> 单个 ICO
    images = [Image.open(p) for p in png_paths]
    ico_path = _OUT_DIR / "app.ico"
    images[0].save(
        str(ico_path), format="ICO",
        sizes=[(32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
        append_images=images[1:],
    )
    print(f"已生成: {ico_path}")


if __name__ == "__main__":
    main()
