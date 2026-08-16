"""应用性能基准: 导入+校验 / 主题切换 / 历史加载与搜索。

用法:
    QT_QPA_PLATFORM=offscreen python scripts/benchmark_app.py [历史条数]
仅用于发布前人工检查, 不进入默认 pytest (慢用例由 tests/ 覆盖)。
"""

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from fsa.core.engine.registry import RuleRegistry
from fsa.core.importer.importer import ImportService
from fsa.core.models.result import ValidationSummary
from fsa.gui.app_state import AppState
from fsa.gui.main_window import MainWindow
from fsa.gui.pages.history_page import HistoryPage
from fsa.services.validation_service import ValidationService

_ROOT = Path(__file__).resolve().parents[1]


def _generate_listed_corpus() -> Path:
    spec = importlib.util.spec_from_file_location(
        "generate_listed_corpus",
        _ROOT / "tests" / "fixtures" / "generate_listed_corpus.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    path = Path(tempfile.mkdtemp(prefix="fsa-bench-")) / "listed.xlsx"
    module.generate(path)
    return path


def bench_import_validate(rounds: int = 5) -> tuple[float, float]:
    path = _generate_listed_corpus()
    registry = RuleRegistry.from_json("cas_gouji_rule_library.json")
    start = time.perf_counter()
    reports = ImportService(period="2024-12").import_file(str(path))
    for _ in range(rounds):
        ValidationService(registry).validate(reports, "2024-12")
    elapsed = time.perf_counter() - start
    return elapsed, rounds


def bench_theme_switch(app: QApplication, rounds: int = 20) -> float:
    state = AppState()
    window = MainWindow(state, initial_dark=False, theme_mode="light")
    window.show()
    app.processEvents()

    # 预加载真实数据态: 导入 + 校验 + 回填结果, 使主题切换覆盖结果卡/汇总卡/表格
    path = _generate_listed_corpus()
    registry = RuleRegistry.from_json("cas_gouji_rule_library.json")
    reports = ImportService(period="2024-12").import_file(str(path))
    summary = ValidationService(registry).validate(reports, "2024-12")
    state.set_results(summary, persist=False)
    app.processEvents()

    start = time.perf_counter()
    for _ in range(rounds):
        window._toggle_theme()
        app.processEvents()
    elapsed = time.perf_counter() - start
    window.close()
    return elapsed


def bench_history(count: int = 200) -> tuple[float, float]:
    app = QApplication.instance() or QApplication(sys.argv)
    state = AppState()
    repo = state.history_repo
    if repo is not None:
        repo.delete_all()
        start_seed = time.perf_counter()
        for index in range(count):
            repo.save(
                ValidationSummary(
                    period=f"2024-{index % 12 + 1:02d}",
                    total=1,
                    passed=1,
                    failed=0,
                    errored=0,
                    skipped=0,
                    results=[],
                )
            )
        seed_elapsed = time.perf_counter() - start_seed
    else:
        seed_elapsed = 0.0
    page = HistoryPage(state)
    page.show()
    app.processEvents()
    start = time.perf_counter()
    page._load_history()
    page._search_input.setText("不通过")
    app.processEvents()
    elapsed = time.perf_counter() - start
    page.close()
    return seed_elapsed, elapsed


def main() -> int:
    history_count = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    app = QApplication(sys.argv)
    import_elapsed, rounds = bench_import_validate()
    print(f"导入+{rounds} 轮校验: {import_elapsed:.2f}s ({import_elapsed / rounds:.3f}s/轮)")
    theme_elapsed = bench_theme_switch(app)
    print(f"主题切换 20 次: {theme_elapsed:.2f}s ({theme_elapsed / 20 * 1000:.0f}ms/次)")
    seed_elapsed, history_elapsed = bench_history(history_count)
    print(f"写入 {history_count} 条历史: {seed_elapsed:.2f}s")
    print(f"历史加载+搜索: {history_elapsed:.2f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
