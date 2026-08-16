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
        # CAS 知识库外部文档 (Agent 诊断检索用)
        ("resources/knowledge", "resources/knowledge"),
    ],
    hiddenimports=[
        "openpyxl",
        "openpyxl.cell._writer",
        "loguru",
        "simpleeval",
        "pandas",
        "xlrd",
        "pdfplumber",
        "numpy",
        "win32com",
        "win32com.client",
        "pythoncom",
        "pywintypes",
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
        "transformers",
        "onnxruntime",
        "sklearn",
        "matplotlib",
        "jedi",
        "hf_xet",
        "huggingface_hub",
        "tokenizers",
        "IPython",
        "parso",
        "sympy",
        "networkx",
        # 环境泄漏包 (Anaconda 底座经由 pandas 条件导入等路径混入, 应用不使用)
        "scipy",          # pandas.core.arrays.sparse 的条件依赖, 占 67MB
        "scipy.libs",
        "gevent",
        "zmq",
        "pythonnet",
        "ast_serialize",
        "python_calamine",  # pandas 可选 Excel 引擎, 本项目用 openpyxl/xlrd
        # 进一步剔除环境泄漏与可选链路 (经 xref/导入追踪核实非应用所需)
        "pydantic",       # 无任何 app 包导入
        "pydantic_core",
        "html5lib",       # pandas.read_html 可选链
        "bs4",
        "lxml",           # openpyxl 的可选加速器, 缺失时回退 stdlib ElementTree
        "tkinter",
        "_tkinter",
        "setuptools",
        "pkg_resources",
        # 包内测试目录
        "pandas.tests",
        "numpy.tests",
        "openpyxl.tests",
        # PySide6 未使用的 Qt 模块 (排除后其 Qt DLL 不随包分发)
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtWebEngineQuick",
        "PySide6.QtWebView",
        "PySide6.QtWebSockets",
        "PySide6.QtQml",
        "PySide6.QtQuick",
        "PySide6.QtQuick3D",
        "PySide6.QtMultimedia",
        "PySide6.QtCharts",
        "PySide6.QtDataVisualization",
        "PySide6.Qt3DCore",
        "PySide6.Qt3DRender",
        "PySide6.Qt3DInput",
        "PySide6.Qt3DLogic",
        "PySide6.Qt3DAnimation",
        "PySide6.Qt3DExtras",
        "PySide6.QtSql",          # 用标准库 sqlite3, 不经 QtSql
        "PySide6.QtNetwork",      # HTTP 走标准库 urllib
        "PySide6.QtTest",
        "PySide6.QtHelp",
        "PySide6.QtDesigner",
        "PySide6.QtUiTools",
        "PySide6.QtTextToSpeech",
        "PySide6.QtSerialPort",
        "PySide6.QtBluetooth",
        "PySide6.QtNfc",
        "PySide6.QtPositioning",
        "PySide6.QtRemoteObjects",
        "PySide6.QtSensors",
        "PySide6.QtXmlPatterns",
        # 注意保留: QtPrintSupport(打印预览) / QtSvg(qfluentwidgets 图标) / QtOpenGL(Gui 依赖)
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# 体积优化: 按文件名剔除未使用 Qt 模块的原生 DLL 与非中文翻译
# (excludes 只拦 Python 模块, Qt DLL 由 PySide6 hook 独立收集, 需在此过滤)
_QT_BIN_DROP_PREFIXES = (
    "Qt6WebEngine", "Qt6WebView", "Qt6WebSockets", "Qt6Quick", "Qt6Qml",
    "Qt6Pdf", "Qt6Multimedia", "Qt6Charts", "Qt6DataVisualization",
    "Qt6VirtualKeyboard", "Qt6Network", "Qt6Sql", "Qt6Test", "Qt6Help",
    "Qt6Designer", "Qt6UiTools", "Qt6TextToSpeech", "Qt6SerialPort",
    "Qt6Bluetooth", "Qt6Nfc", "Qt6Positioning", "Qt6RemoteObjects",
    "Qt6Sensors", "Qt6XmlPatterns", "Qt63D",
)
# 保留: Qt6Core/Gui/Widgets/PrintSupport/Svg/OpenGL + opengl32sw.dll(无 GPU 机器的回退渲染)
a.binaries = [
    b for b in a.binaries
    if not Path(b[0]).name.startswith(_QT_BIN_DROP_PREFIXES)
]
# 翻译只保留中文 (QFileDialog 等系统对话框的按钮文案)
a.datas = [
    d for d in a.datas
    if not (
        Path(d[0]).as_posix().startswith("PySide6/Qt/translations/")
        and not Path(d[0]).name.startswith(("qt_zh_CN", "qtbase_zh_CN"))
    )
]

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
