"""设置页面分区构建辅助函数。

从 settings_page.py 中提取，保持主文件 ≤250 行。
"""

from __future__ import annotations

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from fsa.core.version import APP_VERSION
from fsa.gui.app_state import AppState


def _section(title: str) -> tuple[QFrame, QVBoxLayout]:
    """创建设置分区。"""
    frame = QFrame()
    frame.setObjectName("SectionCard")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(24, 20, 24, 20)
    layout.setSpacing(12)

    label = QLabel(title)
    label.setStyleSheet("font-size: 14px; font-weight: 600;")
    layout.addWidget(label)

    return frame, layout


def _control_container(width: int = 200) -> tuple[QWidget, QHBoxLayout]:
    """创建固定宽度的右侧控件容器, 保证所有右侧控件右缘对齐。"""
    container = QWidget()
    container.setFixedWidth(width)
    lay = QHBoxLayout(container)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(4)
    return container, lay


def _row(label_text: str, desc: str = "") -> tuple[QHBoxLayout, QLabel]:
    """创建设置行: 标签 + 描述 + 右侧控件区。"""
    row = QHBoxLayout()
    row.setSpacing(8)

    info = QVBoxLayout()
    info.setSpacing(2)
    label = QLabel(label_text)
    label.setStyleSheet("font-size: 13px; font-weight: 500;")
    info.addWidget(label)
    if desc:
        d = QLabel(desc)
        d.setObjectName("MetaLabel")
        info.addWidget(d)
    row.addLayout(info)
    row.addStretch()

    return row, label


def build_appearance_section(
    page: QWidget,
    settings: QSettings,
    state: AppState,
) -> QFrame:
    """构建外观设置分区。"""
    frame, layout = _section("外观")

    row, _ = _row("主题模式", "选择浅色、深色或跟随系统")

    light_btn = QPushButton("浅色")
    dark_btn = QPushButton("深色")
    auto_btn = QPushButton("跟随系统")
    for btn in [light_btn, dark_btn, auto_btn]:
        btn.setCheckable(True)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedHeight(32)
        btn.setMinimumWidth(96)  # 足够容纳"跟随系统"四字
        btn.setObjectName("FilterTab")

    light_btn.clicked.connect(lambda: page._set_theme("light"))
    dark_btn.clicked.connect(lambda: page._set_theme("dark"))
    auto_btn.clicked.connect(lambda: page._set_theme("auto"))
    row.addWidget(light_btn)
    row.addWidget(dark_btn)
    row.addWidget(auto_btn)
    layout.addLayout(row)

    page._light_btn = light_btn
    page._dark_btn = dark_btn
    page._auto_btn = auto_btn

    return frame


def build_validation_section(
    page: QWidget,
    settings: QSettings,
    state: AppState,
) -> QFrame:
    """构建校验参数分区。"""
    frame, layout = _section("校验参数")

    row1, _ = _row("默认容差 (元)", "平衡类规则的默认容差, 单位: 元 (即时生效)")
    tol_container, tol_lay = _control_container()
    tolerance_input = QLineEdit("0.01")
    tolerance_input.setFixedHeight(32)
    tolerance_input.setObjectName("StyledInput")
    tolerance_input.editingFinished.connect(page._save_tolerance)
    tol_lay.addWidget(tolerance_input)
    row1.addWidget(tol_container)
    layout.addLayout(row1)

    row2, _ = _row("毛利率波动阈值", "同比波动超过此比例触发警告 (默认 30%)")
    thr_container, thr_lay = _control_container()
    threshold_input = QLineEdit("30")
    threshold_input.setFixedHeight(32)
    threshold_input.setObjectName("StyledInput")
    threshold_input.editingFinished.connect(page._save_threshold)
    thr_lay.addWidget(threshold_input)
    pct = QLabel("%")
    pct.setObjectName("MetaLabel")
    thr_lay.addWidget(pct)
    thr_lay.addStretch()
    row2.addWidget(thr_container)
    layout.addLayout(row2)

    page._tolerance_input = tolerance_input
    page._threshold_input = threshold_input

    return frame


def build_storage_section(
    page: QWidget,
    settings: QSettings,
    state: AppState,
) -> QFrame:
    """构建数据存储分区。"""
    frame, layout = _section("数据存储")

    # 数据库位置: 显示真实路径 (只读)
    row1, _ = _row("数据库位置", "SQLite 数据库文件路径 (只读)")
    real_path = str(state._db.path) if getattr(state, "_db", None) else "未初始化"
    db_path = QLabel(real_path)
    db_path.setObjectName("ValueLabel")
    db_path.setMinimumWidth(0)
    db_path.setSizePolicy(
        QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
    )
    db_path.setToolTip(real_path)
    row1.addWidget(db_path)
    layout.addLayout(row1)

    row2, _ = _row("历史记录保留", "自动清理超过此天数的校验记录 (重启生效)")
    days_container, days_lay = _control_container()
    days_input = QLineEdit("90")
    days_input.setFixedHeight(32)
    days_input.setObjectName("StyledInput")
    days_input.editingFinished.connect(page._save_days)
    days_lay.addWidget(days_input)
    days_label = QLabel("天")
    days_label.setObjectName("MetaLabel")
    days_lay.addWidget(days_label)
    days_lay.addStretch()
    row2.addWidget(days_container)
    layout.addLayout(row2)

    page._days_input = days_input

    return frame


def build_about_section(
    page: QWidget,
    settings: QSettings,
    state: AppState,
) -> QFrame:
    """构建关于分区。"""
    frame, layout = _section("关于")

    for label_text, value in [
        ("软件版本", f"{APP_VERSION} (MVP)"),
        ("开源许可", "MIT License"),
            ("规则库版本", "CAS v1.2.0 (37 条规则, 含权益变动表)"),
    ]:
        row, _ = _row(label_text)
        val = QLabel(value)
        val.setObjectName("ValueLabel")
        row.addWidget(val)
        layout.addLayout(row)

    return frame


def build_update_section(
    page: QWidget,
    settings: QSettings,
    state: AppState,
) -> QFrame:
    """构建软件更新分区。"""
    frame, layout = _section("软件更新")

    # 当前版本
    row1, _ = _row("当前版本", "已安装的软件版本")
    ver_label = QLabel(APP_VERSION)
    ver_label.setObjectName("ValueLabel")
    row1.addWidget(ver_label)
    layout.addLayout(row1)

    # 更新清单 URL (可直接编辑/粘贴)
    row2, _ = _row("更新清单地址", "内网 JSON 清单文件的 URL (可直接粘贴编辑)")
    url_input = QLineEdit(
        str(settings.value("update_manifest_url", "http://localhost:8000/version.json"))
    )
    url_input.setObjectName("StyledInput")
    url_input.setPlaceholderText("可直接粘贴内网清单 URL, 如 http://192.168.x.x/version.json")
    url_input.setMinimumWidth(280)
    url_input.editingFinished.connect(page._save_update_url)
    row2.addWidget(url_input)
    layout.addLayout(row2)

    # 检查更新按钮
    row3, _ = _row("检查更新", "点击按钮检查是否有新版本")
    check_btn = QPushButton("检查更新")
    check_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    check_btn.setFixedSize(100, 32)
    check_btn.clicked.connect(page._check_for_update)
    row3.addWidget(check_btn)
    layout.addLayout(row3)

    # 更新状态
    status_label = QLabel("")
    status_label.setObjectName("MetaLabel")
    status_label.setWordWrap(True)
    layout.addWidget(status_label)

    # 下载按钮
    row4 = QHBoxLayout()
    row4.setSpacing(8)
    download_btn = QPushButton("下载更新")
    download_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    download_btn.setFixedSize(100, 32)
    download_btn.setVisible(False)
    download_btn.clicked.connect(page._download_update)
    row4.addWidget(download_btn)
    row4.addStretch()
    layout.addLayout(row4)

    page._update_url_input = url_input
    page._update_check_btn = check_btn
    page._update_status_label = status_label
    page._update_download_btn = download_btn
    page._update_download_url = ""

    return frame


def build_llm_section(
    page: QWidget,
    settings: QSettings,
    state: AppState,
) -> QFrame:
    """构建 AI 助手 (大模型) 配置分区。"""
    frame, layout = _section("AI 助手 (大模型)")

    # provider 类型
    row1, _ = _row("模型类型", "本地 Ollama 或 OpenAI 兼容 API")
    provider_combo = QComboBox()
    provider_combo.addItem("不使用 AI 助手", "")
    provider_combo.addItem("本地 Ollama", "ollama")
    provider_combo.addItem("OpenAI 兼容 API", "openai")
    cur_provider = str(settings.value("llm_provider", ""))
    provider_combo.setCurrentIndex(
        {"": 0, "ollama": 1, "openai": 2}.get(cur_provider, 0)
    )
    provider_combo.currentIndexChanged.connect(
        lambda _: page._save_llm_provider()
    )
    row1.addWidget(provider_combo)
    layout.addLayout(row1)

    # base_url
    row2, _ = _row(
        "服务地址", "Ollama: http://localhost:11434; 公司部署/在线: API base URL"
    )
    base_url_input = QLineEdit(str(settings.value("llm_base_url", "")))
    base_url_input.setObjectName("StyledInput")
    base_url_input.setPlaceholderText("如 http://localhost:11434 或 https://api.xxx.com/v1")
    base_url_input.setMinimumWidth(280)
    base_url_input.editingFinished.connect(page._save_llm_config)
    row2.addWidget(base_url_input)
    layout.addLayout(row2)

    # model
    row3, _ = _row("模型名称", "如 qwen2.5:7b / deepseek-r1 / 公司部署的模型名")
    model_input = QLineEdit(str(settings.value("llm_model", "qwen2.5:7b")))
    model_input.setObjectName("StyledInput")
    model_input.setMinimumWidth(280)
    model_input.editingFinished.connect(page._save_llm_config)
    row3.addWidget(model_input)
    layout.addLayout(row3)

    # api_key
    row4, _ = _row("API 密钥", "OpenAI 兼容 API 需要; Ollama 可留空")
    key_input = QLineEdit(str(settings.value("llm_api_key", "")))
    key_input.setObjectName("StyledInput")
    key_input.setEchoMode(QLineEdit.EchoMode.Password)
    key_input.setMinimumWidth(280)
    key_input.editingFinished.connect(page._save_llm_config)
    row4.addWidget(key_input)
    layout.addLayout(row4)

    # 状态提示
    hint = QLabel("配置后, AI 助手可进行多轮对话式深入分析; 未配置时使用规则化诊断。")
    hint.setObjectName("MetaLabel")
    hint.setWordWrap(True)
    layout.addWidget(hint)

    page._llm_provider_combo = provider_combo
    page._llm_base_url_input = base_url_input
    page._llm_model_input = model_input
    page._llm_api_key_input = key_input

    return frame
