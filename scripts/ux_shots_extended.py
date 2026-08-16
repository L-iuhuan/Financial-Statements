"""UX 评估补充: 交互状态截图 (ux_shots.py 未覆盖的状态)。

输出到 ux_shots/, 文件名前缀 ext_。须在项目根目录运行。
覆盖: AI 抽屉空/短回复/长诊断/不可用、自定义规则与多主体/科目清单对话框、
导入页空态与失败提示、审计页空态、历史页有数据、规则页搜索、跳过卡片展开、
「不通过」筛选激活态。
"""

import os
import sys
import tempfile
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtCore import QSettings, QTimer
from PySide6.QtWidgets import QApplication, QDialog

from fsa.core.models.result import ValidationResult, ValidationSummary
from fsa.core.models.rule import Severity
from fsa.gui.app_state import AppState
from fsa.gui.main_window import MainWindow
from fsa.gui.theme import get_qss
from fsa.services.multi_entity_service import EntityOutcome, MultiEntityResult

ROOT = Path(__file__).resolve().parent.parent
MOUTAI = ROOT / "tests" / "fixtures" / "real_reports" / "贵州茅台_2023年报_三大报表.xlsx"
SYNTHETIC = ROOT / "tests" / "fixtures" / "realistic_report.xlsx"
OUT_DIR = "ux_shots"

app = QApplication(sys.argv)
app.setStyleSheet(get_qss(False))

# 快照用户设置, 脚本结束时恢复 (主题/LLM 配置)
settings = QSettings("FSA", "FinancialAudit")
_LLM_KEYS = ["llm_provider", "llm_base_url", "llm_model", "llm_api_key", "llm_allow_remote_ack"]
saved_settings = {key: settings.value(key) for key in ["theme_mode", *_LLM_KEYS]}


def _clear_llm_settings() -> None:
    """清空 LLM 配置, 保证走规则化兜底 (确定性)。"""
    for key in _LLM_KEYS:
        settings.remove(key)
    settings.sync()


_clear_llm_settings()
settings.setValue("theme_mode", "light")

state = AppState()
state.load_registry()
window = MainWindow(state)
window.resize(1280, 800)
window.show()

os.makedirs(OUT_DIR, exist_ok=True)
captured: list[str] = []
skipped_states: list[str] = []


def pump(rounds: int = 3) -> None:
    for _ in range(rounds):
        app.processEvents()


def nonwhite_ratio(path: Path) -> float:
    """采样非纯白像素占比, 用于检测空白截图 (对话框多为浅色底, 体积小属正常)。"""
    from PySide6.QtGui import QImage

    img = QImage(str(path))
    if img.isNull():
        return 0.0
    total = 0
    nonwhite = 0
    for y in range(0, img.height(), 7):
        for x in range(0, img.width(), 7):
            total += 1
            color = img.pixelColor(x, y)
            if not (color.red() > 245 and color.green() > 245 and color.blue() > 245):
                nonwhite += 1
    return nonwhite / total if total else 0.0


def snap(name: str, widget: object | None = None) -> None:
    """截图 (默认整窗) 并校验非空白 (体积 + 非白像素双门槛)。"""
    target = widget if widget is not None else window
    pump()
    target.ensurePolished()  # type: ignore[union-attr]
    target.repaint()  # type: ignore[union-attr]
    pump()
    path = Path(OUT_DIR) / f"ext_{name}.png"
    target.grab().save(str(path))  # type: ignore[union-attr]
    size = path.stat().st_size if path.exists() else 0
    ratio = nonwhite_ratio(path) if path.exists() else 0.0
    ok = path.exists() and size > 1024 and ratio > 0.01
    status = "OK" if ok else "!! 疑似空白"
    print(f"[{status}] {path} ({size / 1024:.0f} KB, 非白像素 {ratio:.0%})")
    if ok:
        captured.append(name)
    else:
        skipped_states.append(f"{name} (截图疑似空白)")


def wait_worker(timeout: float = 30.0) -> bool:
    """循环 processEvents 等待后台 AgentWorker 完成 (超时保护)。"""
    deadline = time.monotonic() + timeout
    while getattr(window, "_active_worker", None) is not None:
        if time.monotonic() > deadline:
            return False
        app.processEvents()
        time.sleep(0.05)
    pump()
    return True


def wait_persist(timeout: float = 15.0) -> None:
    """等待异步历史落库完成。"""
    deadline = time.monotonic() + timeout
    thread = getattr(state, "_persist_thread", None)
    while thread is not None and thread.is_alive():
        if time.monotonic() > deadline:
            print("!! 历史落库等待超时")
            return
        app.processEvents()
        time.sleep(0.05)
        thread = getattr(state, "_persist_thread", None)
    pump()


def clear_infobars() -> None:
    """隐藏残留 InfoBar, 避免串扰后续截图。"""
    from qfluentwidgets import InfoBar

    for bar in window.findChildren(InfoBar):
        bar.hide()
    pump()


def send_message(text: str) -> None:
    drawer = window._agent_drawer
    drawer._input.setPlainText(text)
    drawer._on_send()
    pump()


def make_fake_multi_entity_result() -> MultiEntityResult:
    """构造小型多主体结果 (2 主体成功 + 1 主体失败 + 1 条双边核对)。"""
    summary_a = ValidationSummary(period="2024-12", total=25, passed=23, failed=2, errored=0)
    summary_b = ValidationSummary(period="2024-12", total=25, passed=25, failed=0, errored=0)
    combined = ValidationSummary(period="2024-12", total=50, passed=48, failed=2, errored=1)
    bilateral = [
        ValidationResult(
            rule_id="ME-CF-001",
            rule_name="内部销售收到现金 ↔ 对方采购支付现金",
            passed=False,
            severity=Severity.WARNING,
            left_value=100000.0,
            right_value=95000.0,
            diff=5000.0,
            tolerance=0.01,
            formula="internal_sales_cash == -internal_purchase_cash",
            message="内部现金流双边核对不通过: 差额 5,000.00 元",
            category="B-表间勾稽",
        )
    ]
    return MultiEntityResult(
        outcomes=[
            EntityOutcome(entity_id="母公司", folder="demo/母公司", summary=summary_a),
            EntityOutcome(entity_id="子公司A", folder="demo/子公司A", summary=summary_b),
            EntityOutcome(
                entity_id="子公司B", folder="demo/子公司B",
                errors=["读取失败: 文件已损坏或格式不支持"],
            ),
        ],
        combined=combined,
        bilateral=bilateral,
    )


try:
    # ── 1/8/10. 浅色空状态: 导入页 / 审计页 / AI 抽屉 ──
    window._on_nav("navImport")
    snap("light_import_empty")

    window._on_nav("navAudit")
    snap("light_audit_empty")

    window._on_nav("navImport")
    window._agent_drawer._new_session()  # 新建空会话, 保证可重复执行
    window._open_drawer()
    snap("light_agent_empty")

    # ── 深色空状态 (导入页 / AI 抽屉) ──
    window._toggle_theme()
    time.sleep(0.4)  # 主题过渡遮罩淡出 200ms, 沉淀后再截
    app.processEvents()
    pump()
    snap("dark_agent_empty")
    window._close_drawer()
    pump()
    snap("dark_import_empty")
    window._toggle_theme()  # 回到浅色
    time.sleep(0.4)
    app.processEvents()
    pump()

    # ── 2. agent 短回复 (无 LLM, 规则化兜底, 同步返回) ──
    window._open_drawer()
    send_message("什么是勾稽关系")
    snap("light_agent_short_reply")

    # ── 4. agent 错误/不可用状态 (不可达 LLM 地址, 后台线程兜底) ──
    settings.setValue("llm_base_url", "http://localhost:11434")
    settings.setValue("llm_model", "qwen2.5:7b")
    settings.sync()
    window._llm_client_cache = None
    window._llm_availability = {}
    send_message("如何导出 Excel 底稿")
    if wait_worker(timeout=40.0):
        snap("light_agent_unavailable")
    else:
        skipped_states.append("agent 不可用状态 (后台任务超时)")
    _clear_llm_settings()
    window._llm_client_cache = None
    window._llm_availability = {}
    window._close_drawer()
    pump()

    # ── 5. 自定义规则对话框 (含公式预览区) ──
    from fsa.gui.widgets.custom_rule_dialog import CustomRuleDialog

    rule_dialog = CustomRuleDialog(window)
    rule_dialog._template_combo.setCurrentIndex(1)  # 填模板, 触发公式中文预览
    rule_dialog.resize(620, 720)
    rule_dialog.show()
    pump()
    snap("light_custom_rule_dialog", rule_dialog)
    rule_dialog.close()
    pump()

    # ── 6. 多主体结果对话框 (假数据, 含「结果已保存到历史记录」行) ──
    from fsa.gui.widgets.multi_entity_dialog import MultiEntityResultDialog

    multi_dialog = MultiEntityResultDialog(make_fake_multi_entity_result(), window, saved_count=2)
    multi_dialog.resize(960, 680)
    multi_dialog.show()
    pump()
    snap("light_multi_entity_dialog", multi_dialog)
    multi_dialog.close()
    pump()

    # ── synthetic 数据: 25 条结果 (23 通过 / 2 不通过 / 17 跳过) ──
    ip = window._import_page
    window._on_nav("navImport")
    ip._on_file(str(SYNTHETIC))
    ip.trigger_validate()
    wait_persist()
    clear_infobars()

    # ── 3. agent 长回复 (BS-BAL-004 失败规则的五段式规则诊断) ──
    if state.results is not None and any(
        r.rule_id == "BS-BAL-004" and not r.passed for r in state.results.results
    ):
        window._on_diagnose("BS-BAL-004")
        if wait_worker(timeout=30.0):
            snap("light_agent_long_diagnosis")
        else:
            skipped_states.append("agent 长回复 (诊断后台任务超时)")
        window._agent_drawer._clear_context()
        window._close_drawer()
        pump()
    else:
        skipped_states.append("agent 长回复 (synthetic 数据无 BS-BAL-004 失败结果)")

    # ── 13. 展开的「跳过」卡片 (灰底第四态) ──
    skipped_cards = [
        (r, c) for r, c in ip._result_cards if r.skipped
    ]
    if skipped_cards:
        ip._on_filter("skip")
        result, card = skipped_cards[0]
        if not card._expanded:
            card.toggle_expanded()
        pump()
        status_text = card._status_label.text()
        if status_text != "跳过":
            print(f"!! 跳过卡片状态文案异常: {status_text}")
        snap("light_skip_card_expanded")
        snap("light_skip_card_detail", card)  # 卡片级特写, 便于确认灰底「跳过」第四态
    else:
        skipped_states.append("展开的跳过卡片 (无 skipped 结果)")

    # ── 14. 「不通过」筛选激活态 ──
    ip._on_filter("fail")
    snap("light_filter_fail_active")
    ip._on_filter("all")
    pump()

    # ── 9. 导入失败提示态 (垃圾字节 xlsx -> InfoBar 警告) ──
    garbage = Path(tempfile.gettempdir()) / "fsa_ux_garbage.xlsx"
    garbage.write_bytes(os.urandom(512))
    try:
        ip._on_file(str(garbage))
        pump()
        snap("light_import_failed")
    except Exception as e:  # 导入管线异常不应炸掉截图脚本
        skipped_states.append(f"导入失败提示态 (导入异常: {e})")
    finally:
        garbage.unlink(missing_ok=True)
    clear_infobars()

    # ── 茅台真实年报: 报表卡片 + 第二次历史记录 ──
    ip._on_file(str(MOUTAI))
    pump()

    # ── 7. 科目清单对话框 (报表卡片「查看科目清单」, exec 内定时截图) ──
    from fsa.gui.widgets.report_card import ReportCard

    first_item = ip._cards_grid.itemAt(0)
    card = first_item.widget() if first_item is not None else None
    if isinstance(card, ReportCard):
        dialog_path = Path(OUT_DIR) / "ext_light_items_dialog.png"

        def _grab_items_dialog() -> None:
            for w in app.topLevelWidgets():
                if isinstance(w, QDialog) and w.isVisible() and "科目清单" in w.windowTitle():
                    w.resize(960, 640)
                    app.processEvents()
                    w.ensurePolished()
                    w.repaint()
                    app.processEvents()
                    w.grab().save(str(dialog_path))
                    w.accept()
                    return

        QTimer.singleShot(800, _grab_items_dialog)
        card._detail_btn.click()  # 进入 exec 模态, 定时器截图后关闭
        pump()
        if (
            dialog_path.exists()
            and dialog_path.stat().st_size > 4 * 1024
            and nonwhite_ratio(dialog_path) > 0.05
        ):
            print(
                f"[OK] {dialog_path} ({dialog_path.stat().st_size / 1024:.0f} KB,"
                f" 非白像素 {nonwhite_ratio(dialog_path):.0%})"
            )
            captured.append("light_items_dialog")
        else:
            skipped_states.append("科目清单对话框 (模态截图未生成或疑似空白)")
    else:
        skipped_states.append("科目清单对话框 (无报表卡片)")

    ip.trigger_validate()
    wait_persist()
    clear_infobars()

    # ── 11. 历史页有数据 (首次展示触发加载, 多 pump 几次) ──
    window._on_nav("navHistory")
    pump(6)
    snap("light_history_populated")

    # ── 12. 规则页搜索过滤态 ──
    window._on_nav("navRules")
    rule_page = window._rule_page
    if rule_page is not None:
        rule_page._search.setText("资产")
        pump()
        snap("light_rules_search")
    else:
        skipped_states.append("规则页搜索过滤态 (规则页未创建)")

finally:
    # 恢复用户设置
    for key, value in saved_settings.items():
        if value is None:
            settings.remove(key)
        else:
            settings.setValue(key, value)
    settings.sync()
    state.close()
    app.quit()

print(f"\n完成: {len(captured)} 张截图 -> {OUT_DIR}/")
if skipped_states:
    print("跳过/未能驱动的状态:")
    for item in skipped_states:
        print(f"  - {item}")
