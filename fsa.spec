# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec: 财务报表勾稽校验系统打包配置。

构建: python -m PyInstaller --noconfirm fsa.spec
产物: dist/fsa/fsa.exe (onedir 模式)
"""

from pathlib import Path

block_cipher = None

# 项目根目录 (spec 文件所在目录)
_ROOT = Path.cwd()

a = Analysis(
    ["src/fsa/__main__.py"],
    pathex=["src"],
    binaries=[],
    datas=[
        # 规则库 JSON 必须打包进 bundle 根目录
        # (resource_path 在冻结模式下从 sys._MEIPASS / exe 目录查找)
        ("cas_gouji_rule_library.json", "."),
        # 应用图标资源
        ("resources/logo_32.png", "resources"),
        ("resources/logo_256.png", "resources"),
    ],
    hiddenimports=[
        "openpyxl",
        "openpyxl.cell._writer",
        "loguru",
        "simpleeval",
        "qfluentwidgets",
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "PySide6.QtPrintSupport",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 排除测试与开发依赖, 减小体积
        "pytest",
        "pytestqt",
        "camelot",
        "pdfplumber",
        "pandas",
        "numpy",
        # 排除 PyInstaller 误解析进来的无关包 (应用不使用)
        "yt_dlp",
        "websockets",
        "requests",
        "urllib3",
        "mutagen",
        "brotli",
        "certifi",
        "secretstorage",
        "curl_cffi",
        "Cryptodome",
        # 排除误拉入的 ML/科学计算重包 (应用不使用, 占体积大头)
        "torch",
        "torchvision",
        "cv2",
        "pyarrow",
        "av",
        "scipy",
        "transformers",
        "onnxruntime",
        "sklearn",
        "matplotlib",
        "jedi",
        "PIL",
        "hf_xet",
        "huggingface_hub",
        "tokenizers",
        "IPython",
        "parso",
        "sympy",
        "networkx",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="fsa",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # 不用 UPX 压缩, 避免误报/兼容性问题
    console=False,  # 无控制台窗口 (GUI 应用)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="resources/app.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="fsa",
)
