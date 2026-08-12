"""生成应用 Logo: 盾牌 + 对勾 (校验/可信主题), 藏青蓝品牌色。

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

# 品牌深青玉 (与 theme.py brand_600 一致)
TEAL = "#0e7a6c"
TEAL_DARK = "#0b5a50"
TEAL_LIGHT = "#3aa495"
LIGHT = "#f0faf8"

# 精致几何标记: 天平/勾稽平衡意象
# 圆形底盘 + 内部抽象天平 (两盘平衡 = 勾稽平衡)
_SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" width="256" height="256">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="{TEAL_LIGHT}"/>
      <stop offset="0.5" stop-color="{TEAL}"/>
      <stop offset="1" stop-color="{TEAL_DARK}"/>
    </linearGradient>
    <linearGradient id="mark" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#ffffff"/>
      <stop offset="1" stop-color="{LIGHT}"/>
    </linearGradient>
  </defs>
  <!-- 圆角方形底, 柔和渐变 -->
  <rect x="10" y="10" width="236" height="236" rx="56" fill="url(#bg)"/>
  <!-- 顶部高光, 增加立体感 -->
  <rect x="10" y="10" width="236" height="118" rx="56" fill="#ffffff" opacity="0.08"/>

  <!-- 天平: 立柱 + 横梁 + 两盘 (勾稽平衡意象), 实心白色描边清晰 -->
  <g stroke="#ffffff" stroke-width="15" fill="none" stroke-linecap="round" stroke-linejoin="round">
    <!-- 横梁 -->
    <line x1="72" y1="100" x2="184" y2="100"/>
    <!-- 立柱 -->
    <line x1="128" y1="100" x2="128" y2="172"/>
    <!-- 底座 -->
    <line x1="100" y1="186" x2="156" y2="186"/>
  </g>
  <!-- 两盘 (左盘/右盘), 实心 -->
  <path d="M72 100 L52 142 Q72 156 92 142 Z" fill="#ffffff"/>
  <path d="M184 100 L164 142 Q184 156 204 142 Z" fill="#ffffff"/>
  <!-- 立柱顶珠 -->
  <circle cx="128" cy="92" r="10" fill="#ffffff"/>
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
