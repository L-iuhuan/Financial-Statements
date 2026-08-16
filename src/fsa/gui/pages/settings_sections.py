"""设置页面分区构建辅助函数。

从 settings_page.py 中提取，保持主文件 ≤250 行。
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import SwitchButton

from fsa.core.edition import get_edition_config
from fsa.core.resources import resource_path
from fsa.core.version import APP_VERSION
from fsa.gui.app_state import AppState
from fsa.gui.widgets.dropdown_combo import DropdownCombo

if TYPE_CHECKING:
    from fsa.gui.pages.settings_page import SettingsPage

_RULES_FILE = resource_path("cas_gouji_rule_library.json")


def _rule_library_label(state: AppState) -> str:
    """规则库版本与条数动态读取，用于「关于」分区展示。

    版本从规则库 JSON 读取；条数从 AppState.registry 读取
    (与当前实际加载的规则一致, 含自定义规则)。
    规则库不可读时版本省略；无 registry 时降级不显示条数 (P6 中文文案)。
    """
    version = ""
    try:
        data = json.loads(_RULES_FILE.read_text(encoding="utf-8"))
        version = str(data["ruleLibrary"].get("version", "")).strip()
    except (OSError, ValueError, KeyError, TypeError):
        version = ""
    registry = state.registry
    count = registry.count() if registry is not None else None

    label = f"CAS v{version}" if version else "CAS 规则库"
    if count is not None:
        label += f" ({count} 条规则)"
    return label


def _section(title: str) -> tuple[QFrame, QVBoxLayout]:
    """创建设置分区。"""
    frame = QFrame()
    frame.setObjectName("SectionCard")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(24, 20, 24, 20)
    layout.setSpacing(12)

    label = QLabel(title)
    label.setObjectName("SectionTitle")
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
    label.setObjectName("PageTitle")
    label.setStyleSheet("font-size: 13px;")
    info.addWidget(label)
    if desc:
        d = QLabel(desc)
        d.setObjectName("MetaLabel")
        info.addWidget(d)
    row.addLayout(info)
    row.addStretch()

    return row, label


def build_appearance_section(
    page: SettingsPage,
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


# 行业键 -> 显示名 (键与 core/engine/thresholds.py 的 KNOWN_INDUSTRIES 一一对应)
INDUSTRY_DISPLAY_NAMES: dict[str, str] = {
    "general": "通用（默认）",
    "financial": "金融",
    "real_estate": "房地产",
    "construction": "建筑/工程",
    "retail": "零售",
    "cyclical": "周期性行业（钢铁/化工/航运等）",
    "high_growth": "高增长企业",
}


def build_validation_section(
    page: SettingsPage,
    settings: QSettings,
    state: AppState,
) -> QFrame:
    """构建校验参数分区。"""
    from fsa.core.engine.thresholds import KNOWN_INDUSTRIES

    frame, layout = _section("校验参数")

    row1, _ = _row(
        "行业",
        "影响逻辑合理性规则（资产负债率/毛利率波动等）的提示阈值，默认通用",
    )
    # DropdownCombo: QComboBox 子控件 QSS 在部分 Windows 环境不渲染,
    # 改用按钮+菜单实现 (见 widgets/dropdown_combo.py)
    industry_combo = DropdownCombo()
    for industry in KNOWN_INDUSTRIES:
        industry_combo.addItem(INDUSTRY_DISPLAY_NAMES.get(industry, industry), industry)
    current = str(settings.value("industry", "general"))
    index = industry_combo.findData(current)
    industry_combo.setCurrentIndex(index if index >= 0 else 0)
    industry_combo.currentIndexChanged.connect(lambda _: page._save_industry())
    row1.addWidget(industry_combo)
    layout.addLayout(row1)

    page._industry_combo = industry_combo

    return frame


def build_storage_section(
    page: SettingsPage,
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
    db_path.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
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
    page: SettingsPage,
    settings: QSettings,
    state: AppState,
) -> QFrame:
    """构建关于分区。"""
    frame, layout = _section("关于")

    edition = get_edition_config()
    version_summary = QLabel(f"版本 {APP_VERSION} · {edition.display_name}")
    version_summary.setObjectName("AboutVersionSummary")
    layout.addWidget(version_summary)

    for label_text, value in [
        ("开源协议", "MIT License"),
        ("规则版本", _rule_library_label(state)),
    ]:
        row, _ = _row(label_text)
        val = QLabel(value)
        val.setObjectName("ValueLabel")
        row.addWidget(val)
        layout.addLayout(row)

    problem_btn = QPushButton("导出问题包")
    problem_btn.setObjectName("BtnSecondary")
    problem_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    problem_btn.setToolTip("打包日志/数据库/诊断信息, 提交给管理员排查问题")
    problem_btn.clicked.connect(page._export_problem_package)
    layout.addWidget(problem_btn)

    return frame


def build_update_section(
    page: SettingsPage,
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

    # 更新清单 URL (可直接编辑/粘贴); 通用版默认 HTTPS, 内部版默认内网/共享盘
    edition = get_edition_config()
    default_url = str(settings.value("update_manifest_url", edition.default_update_url))
    channel_hint = "可填写内网 HTTP/共享盘 UNC 清单地址" if edition.is_internal else "可填写 HTTPS 更新清单地址"
    row2, _ = _row("更新清单地址", channel_hint)
    url_input = QLineEdit(default_url)
    url_input.setObjectName("StyledInput")
    url_input.setPlaceholderText(
        "http://192.168.x.x/version.json 或 \\\\server\\share\\version.json"
        if edition.is_internal
        else "https://updates.example.com/fsa/version.json"
    )
    url_input.setMinimumWidth(280)
    url_input.editingFinished.connect(page._save_update_url)
    row2.addWidget(url_input)
    layout.addLayout(row2)

    # 检查更新按钮
    row3, _ = _row("检查更新", "点击按钮检查是否有新版本")
    check_btn = QPushButton("检查更新")
    check_btn.setObjectName("BtnSecondary")
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
    download_btn.setObjectName("BtnPrimary")
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


def _confirm_remote_risk(parent: QWidget | None) -> bool:
    """远程大模型开关的风险确认弹窗 (P0 离线守卫).

    需勾选「我已知晓风险」后「确认」才可开启;
    未勾选时确认按钮禁用; 取消/关闭弹窗返回 False。
    """
    dialog = QDialog(parent)
    dialog.setWindowTitle("风险确认")
    layout = QVBoxLayout(dialog)

    body = QLabel(
        "开启后可将财务数据发送至远程大模型服务（数据将离开本机）。\n"
        "请确认您了解相关风险，并仅在可信、合规的网络环境中使用。"
    )
    body.setWordWrap(True)
    layout.addWidget(body)

    checkbox = QCheckBox("我已知晓风险")
    layout.addWidget(checkbox)

    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    ok_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
    ok_btn.setText("确认")
    buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
    ok_btn.setEnabled(False)  # 未勾选风险声明前禁止确认
    checkbox.toggled.connect(ok_btn.setEnabled)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)

    if dialog.exec() != QDialog.DialogCode.Accepted:
        return False
    return checkbox.isChecked()


def _on_llm_remote_toggled(
    checked: bool,
    switch: SwitchButton,
    settings: QSettings,
    page: QWidget | None,
) -> None:
    """远程大模型开关处理: 开启需风险确认, 关闭移除确认标记。

    确认弹窗取消/关闭时开关回弹为关, 不写确认标记。
    """
    if checked:
        if not _confirm_remote_risk(page):
            switch.setChecked(False)  # 回弹为关
            return
        settings.setValue("llm_allow_remote_ack", True)
    else:
        settings.remove("llm_allow_remote_ack")
    settings.sync()


def _apply_openai_compat_template(
    provider_combo: DropdownCombo,
    base_url_input: QLineEdit,
    model_input: QLineEdit,
    key_input: QLineEdit,
    page: SettingsPage,
    base_url: str,
    model: str,
) -> None:
    """填入 OpenAI 兼容 API 模板 (密钥留空由用户粘贴)。"""
    provider_combo.setCurrentIndex(2)  # OpenAI 兼容 API
    base_url_input.setText(base_url)
    model_input.setText(model)
    page._save_llm_provider()
    page._save_llm_config()
    key_input.setFocus()


def _apply_deepseek_template(
    provider_combo: DropdownCombo,
    base_url_input: QLineEdit,
    model_input: QLineEdit,
    key_input: QLineEdit,
    page: SettingsPage,
) -> None:
    """填入 DeepSeek OpenAI 兼容配置模板。"""
    _apply_openai_compat_template(
        provider_combo,
        base_url_input,
        model_input,
        key_input,
        page,
        base_url="https://api.deepseek.com",
        model="deepseek-chat",
    )


def _apply_glm_template(
    provider_combo: DropdownCombo,
    base_url_input: QLineEdit,
    model_input: QLineEdit,
    key_input: QLineEdit,
    page: SettingsPage,
) -> None:
    """填入智谱 GLM OpenAI 兼容配置模板 (公司内网部署可自行改地址)。"""
    _apply_openai_compat_template(
        provider_combo,
        base_url_input,
        model_input,
        key_input,
        page,
        base_url="https://open.bigmodel.cn/api/paas/v4",
        model="glm-4-plus",
    )


def build_llm_section(
    page: SettingsPage,
    settings: QSettings,
    state: AppState,
) -> QFrame:
    """构建 AI 助手 (大模型) 配置分区。"""
    frame, layout = _section("AI 助手 (大模型)")

    # provider 类型
    row1, _ = _row("模型类型", "本地 Ollama 或 OpenAI 兼容 API")
    provider_combo = DropdownCombo()
    provider_combo.addItem("不使用 AI 助手", "")
    provider_combo.addItem("本地 Ollama", "ollama")
    provider_combo.addItem("OpenAI 兼容 API", "openai")
    cur_provider = str(settings.value("llm_provider", ""))
    provider_combo.setCurrentIndex({"": 0, "ollama": 1, "openai": 2}.get(cur_provider, 0))
    provider_combo.currentIndexChanged.connect(lambda _: page._save_llm_provider())
    row1.addWidget(provider_combo)
    layout.addLayout(row1)

    # base_url
    row2, _ = _row("服务地址", "Ollama: http://localhost:11434; 公司部署/在线: API base URL")
    base_url_input = QLineEdit(str(settings.value("llm_base_url", "")))
    base_url_input.setObjectName("StyledInput")
    base_url_input.setPlaceholderText("例如 http://localhost:11434 或 https://api.xxx.com/v1")
    base_url_input.setMinimumWidth(280)
    base_url_input.editingFinished.connect(page._save_llm_config)
    row2.addWidget(base_url_input)
    layout.addLayout(row2)

    # model
    row3, _ = _row("模型名称", "如 qwen2.5:7b / deepseek-r1 / 公司部署的模型名")
    model_input = QLineEdit(str(settings.value("llm_model", "")))
    model_input.setObjectName("StyledInput")
    model_input.setPlaceholderText("例如 qwen2.5:7b、GLM-4.7-PF8")
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

    # DeepSeek 快速模板 (只填地址/模型, 密钥与远程风险确认由用户完成)
    template_row = QHBoxLayout()
    template_row.addStretch()
    deepseek_btn = QPushButton("填入 DeepSeek 模板")
    deepseek_btn.setObjectName("TextBtn")
    deepseek_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    deepseek_btn.setToolTip("将模型类型/服务地址/模型名填为 DeepSeek，API 密钥请自行粘贴")
    deepseek_btn.clicked.connect(
        lambda: _apply_deepseek_template(provider_combo, base_url_input, model_input, key_input, page)
    )
    template_row.addWidget(deepseek_btn)
    glm_btn = QPushButton("填入智谱 GLM 模板")
    glm_btn.setObjectName("TextBtn")
    glm_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    glm_btn.setToolTip("将模型类型/服务地址/模型名填为智谱 GLM，API 密钥请自行粘贴")
    glm_btn.clicked.connect(lambda: _apply_glm_template(provider_combo, base_url_input, model_input, key_input, page))
    template_row.addWidget(glm_btn)
    layout.addLayout(template_row)

    # 远程大模型开关 (P0 离线守卫: 财务数据不允许离开本机, 远程需显式确认)
    row5, _ = _row(
        "允许远程大模型服务（云端）",
        "开启后可将财务数据发送至远程大模型服务（数据将离开本机），默认关闭",
    )
    remote_container, remote_lay = _control_container(64)
    remote_switch = SwitchButton()
    remote_switch.setChecked(bool(settings.value("llm_allow_remote_ack", False)))
    remote_switch.checkedChanged.connect(lambda checked: _on_llm_remote_toggled(checked, remote_switch, settings, page))
    remote_lay.addWidget(remote_switch)
    row5.addWidget(remote_container)
    layout.addLayout(row5)

    # 状态提示
    hint = QLabel("配置后, AI 助手可进行多轮对话式深入分析; 未配置时使用规则化诊断。")
    hint.setObjectName("MetaLabel")
    hint.setWordWrap(True)
    layout.addWidget(hint)

    page._llm_provider_combo = provider_combo
    page._llm_base_url_input = base_url_input
    page._llm_model_input = model_input
    page._llm_api_key_input = key_input
    page._llm_remote_switch = remote_switch

    return frame
