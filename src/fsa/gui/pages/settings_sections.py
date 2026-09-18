"""设置页面分区构建辅助函数。

从 settings_page.py 中提取，保持主文件 ≤250 行。
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger
from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QDoubleValidator
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import InfoBar, InfoBarPosition, SwitchButton

from fsa.core.edition import get_edition_config
from fsa.core.engine.thresholds import KNOWN_INDUSTRIES
from fsa.core.resources import resource_path
from fsa.core.version import APP_VERSION
from fsa.gui.app_state import AppState
from fsa.gui.widgets.dropdown_combo import DropdownCombo
from fsa.services.entity_config import (
    DEFAULT_ENTITY_CONFIG_PATH,
    EntityConfig,
    load_default_entity_configs,
    load_entity_configs,
    save_entity_configs,
)

if TYPE_CHECKING:
    from fsa.gui.pages.settings_page import SettingsPage

_RULES_FILE = resource_path("cas_gouji_rule_library.json")


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

    # 「导出问题包」原在关于区, 关于区移除 (2026-09-17) 后由数据存储区收留
    _append_problem_package_button(page, layout)

    return frame


def build_about_section(
    page: SettingsPage,
    settings: QSettings,
    state: AppState,
) -> QFrame:
    """已移除「关于」分区 (2026-09-17 用户决策); 保留空实现避免调用方断裂。"""
    _ = settings, state
    frame = QFrame()
    frame.setObjectName("SettingsSection")
    frame.setVisible(False)
    return frame


def _append_problem_package_button(page: SettingsPage, layout: QVBoxLayout) -> None:
    """「导出问题包」按钮 (原在关于区, 关于区移除后由数据存储区收留)。"""
    problem_btn = QPushButton("导出问题包")
    problem_btn.setObjectName("BtnSecondary")
    problem_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    problem_btn.setToolTip("打包日志/数据库/诊断信息, 提交给管理员排查问题")
    problem_btn.clicked.connect(page._export_problem_package)
    layout.addWidget(problem_btn)


def build_update_section(    page: SettingsPage,
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


_ENTITY_CONFIG_COLUMNS = ["主体标识", "别名（多个用逗号分隔）", "行业", "双边核对容差（元）"]
_ENTITY_CONFIG_INDUSTRIES = [(k, INDUSTRY_DISPLAY_NAMES.get(k, k)) for k in KNOWN_INDUSTRIES]

# 表格内行业下拉用短显示名 (完整名挂 tooltip): 「周期性行业（钢铁/化工/航运等）」
# 这类长名会把下拉 sizeHint 撑到 ~265px, 挤压别名列 (2026-09-18 用户反馈"挤压")
_ENTITY_CONFIG_INDUSTRY_SHORT = {
    "general": "通用",
    "financial": "金融",
    "real_estate": "房地产",
    "construction": "建筑/工程",
    "retail": "零售",
    "cyclical": "周期性",
    "high_growth": "高增长",
}


def _add_entity_row(
    table: QTableWidget,
    entity_id: str = "",
    aliases: str = "",
    industry: str = "general",
    tolerance: float | None = None,
) -> None:
    row = table.rowCount()
    table.insertRow(row)
    for col, text in ((0, entity_id), (1, aliases)):
        item = QTableWidgetItem(text)
        item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable)
        table.setItem(row, col, item)
    # DropdownCombo 替代裸 QComboBox (2026-09-18 用户反馈"没有下拉按钮"):
    # QComboBox 的 ::drop-down/::down-arrow QSS 在部分 Windows 环境不渲染,
    # 本应用统一用按钮+自绘箭头+菜单的 DropdownCombo (见 widgets/dropdown_combo.py)
    combo = DropdownCombo()
    for key, display in _ENTITY_CONFIG_INDUSTRIES:
        short = _ENTITY_CONFIG_INDUSTRY_SHORT.get(key, display)
        combo.addItem(short, key, menu_text=display)
    combo.setMinimumHeight(32)
    combo.setCurrentIndex(max(combo.findData(industry), 0))
    table.setCellWidget(row, 2, combo)
    edit = QLineEdit("" if tolerance is None else str(tolerance))
    edit.setObjectName("StyledInput")
    edit.setPlaceholderText("默认 0.01")
    edit.setMinimumHeight(32)
    edit.setValidator(QDoubleValidator(0.0, 1e12, 6))
    table.setCellWidget(row, 3, edit)
    # 行高按单元格控件实际高度设定: cell widget 不参与 ResizeToContents
    # 行高计算, 控件高于行高会"穿越"行下沿 (2026-09-18 用户反馈);
    # 取 sizeHint 与最小高度较大者 + 8 上下留白, 覆盖任意 DPI 缩放
    table.setRowHeight(
        row,
        max(
            combo.sizeHint().height(),
            combo.minimumHeight(),
            edit.sizeHint().height(),
            edit.minimumHeight(),
        )
        + 8,
    )


def _delete_selected_entity_rows(table: QTableWidget) -> None:
    rows = sorted({idx.row() for idx in table.selectedIndexes()}, reverse=True)
    for row in rows:
        table.removeRow(row)


def _load_entity_configs(table: QTableWidget, config_path: str | Path | None) -> None:
    table.setRowCount(0)
    configs = load_entity_configs(config_path) if config_path else load_default_entity_configs()
    for entity_id, config in configs.items():
        _add_entity_row(table, entity_id, "， ".join(config.aliases), config.industry, config.bilateral_tolerance)
    # 主体标识列按最长内容定宽 (110~220 之间, 字体度量自适应 DPI)
    fm = table.fontMetrics()
    texts = [
        item.text()
        for row in range(table.rowCount())
        if (item := table.item(row, 0)) is not None
    ]
    longest = max(texts, key=fm.horizontalAdvance, default="")
    table.horizontalHeader().resizeSection(
        0, min(220, max(110, fm.horizontalAdvance(longest) + 28))
    )


def _save_entity_configs(page: QWidget, table: QTableWidget, config_path: str | Path | None) -> None:
    base = load_entity_configs(config_path) if config_path else load_default_entity_configs()
    updated: dict[str, EntityConfig] = {}
    for row in range(table.rowCount()):
        id_item = table.item(row, 0)
        entity_id = id_item.text().strip() if id_item else ""
        if not entity_id:
            continue
        old = base.get(entity_id, EntityConfig(entity_id=entity_id))
        alias_item = table.item(row, 1)
        alias_text = alias_item.text() if alias_item else ""
        aliases = tuple(a.strip() for a in alias_text.replace("，", ",").split(",") if a.strip())
        combo = table.cellWidget(row, 2)
        if not isinstance(combo, DropdownCombo):
            continue
        industry = str(combo.currentData())
        edit = table.cellWidget(row, 3)
        if not isinstance(edit, QLineEdit):
            continue
        tol_text = edit.text().strip()
        try:
            bilateral_tolerance = float(tol_text) if tol_text else None
        except ValueError:
            bilateral_tolerance = old.bilateral_tolerance
        updated[entity_id] = replace(old, aliases=aliases, industry=industry, bilateral_tolerance=bilateral_tolerance)
    try:
        save_entity_configs(updated, config_path or DEFAULT_ENTITY_CONFIG_PATH)
    except OSError:
        logger.exception("保存主体配置失败")
        InfoBar.error(
            "保存失败",
            "无法写入主体配置文件，请检查路径后重试。",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=4000,
            parent=page,
        )
        return
    InfoBar.success(
        "已保存",
        "主体配置已保存。",
        orient=Qt.Orientation.Horizontal,
        isClosable=True,
        position=InfoBarPosition.TOP_RIGHT,
        duration=2000,
        parent=page,
    )


def build_entity_config_section(
    page: SettingsPage,
    settings: QSettings,
    state: AppState,
    config_path: str | Path | None = None,
) -> QFrame:
    """构建多主体配置分区。"""
    _ = settings, state
    frame, layout = _section("多主体配置")
    desc = QLabel(
        "主体标识 = 多主体批量校验中各公司子文件夹的名称；"
        "别名 = 该公司在其他公司报表中登记的名称（通常是公司全称），"
        "跨主体购销/现金流双边核对靠它匹配“对方单位”。"
    )
    desc.setObjectName("MetaLabel")
    desc.setWordWrap(True)
    layout.addWidget(desc)

    table = QTableWidget(0, 4)
    table.setObjectName("EntityConfigTable")
    table.setHorizontalHeaderLabels(_ENTITY_CONFIG_COLUMNS)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setAlternatingRowColors(True)
    # 列宽按字体度量计算 (DPI 自适应, 2026-09-18 用户反馈"挤压、混乱"):
    # 别名列 Stretch 吃满剩余宽度; 其余列按内容/表头文本 + 边距定宽,
    # 行业下拉用短显示名 (完整名挂 tooltip) 避免长名撑爆列宽
    header = table.horizontalHeader()
    header.setStretchLastSection(False)
    header.setMinimumSectionSize(96)
    fm = table.fontMetrics()
    industry_w = max(
        fm.horizontalAdvance(_ENTITY_CONFIG_INDUSTRY_SHORT.get(key, display))
        for key, display in _ENTITY_CONFIG_INDUSTRIES
    ) + 56  # 下拉箭头 + 框架边距
    tolerance_w = fm.horizontalAdvance(_ENTITY_CONFIG_COLUMNS[3]) + 20
    header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
    header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
    header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
    header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
    header.resizeSection(2, industry_w)
    header.resizeSection(3, tolerance_w)
    # 行高在 _add_entity_row 中按单元格控件实际高度逐行显式设定:
    # cell widget 不参与 ResizeToContents 行高计算, 控件高于行高会
    # "穿越"行下沿 (2026-09-18 用户反馈); 纵向表头保持默认 Interactive,
    # 避免 ResizeToContents 覆盖显式行高
    # 高度下限保证至少可见 4~5 行; 上限防止主体多时把设置页拉超长
    table.setMinimumHeight(200)
    table.setMaximumHeight(340)
    layout.addWidget(table)

    btn_row = QHBoxLayout()
    add_btn = QPushButton("新增行")
    del_btn = QPushButton("删除所选行")
    save_btn = QPushButton("保存")
    for btn in (add_btn, del_btn, save_btn):
        # 最小高度而非固定: 高 DPI/字体缩放下不裁字 (与全应用口径一致)
        btn.setMinimumHeight(32)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
    add_btn.setObjectName("BtnSecondary")
    del_btn.setObjectName("BtnSecondary")
    save_btn.setObjectName("BtnPrimary")
    add_btn.clicked.connect(lambda: _add_entity_row(table))
    del_btn.clicked.connect(lambda: _delete_selected_entity_rows(table))
    save_btn.clicked.connect(lambda: _save_entity_configs(page, table, config_path))
    btn_row.addWidget(add_btn)
    btn_row.addWidget(del_btn)
    btn_row.addStretch()
    btn_row.addWidget(save_btn)
    layout.addLayout(btn_row)

    path_hint = Path(config_path) if config_path else DEFAULT_ENTITY_CONFIG_PATH
    hint = QLabel(
        f"配置文件位于 {path_hint}，"
        "高级口径（现金等价物科目、余额表映射等）可在该文件中手工调整。"
    )
    hint.setObjectName("MetaLabel")
    hint.setWordWrap(True)
    layout.addWidget(hint)

    page._entity_config_table = table
    page._entity_config_save_btn = save_btn
    page._entity_config_path = config_path
    _load_entity_configs(table, config_path)
    return frame
