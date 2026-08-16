# tests — 测试约定

## OVERVIEW
镜像 src。日常全量 **1419 测试**（收集口径，约 35-60 秒；另有 22 个 `slow` 标记用例——`test_drawer_stress.py` 20 例 + `test_excel_reader_large.py` 2 例——默认跳过，`python -m pytest -m slow` 单独跑）。注意：真实年报已按合规红线移出 git，依赖它的用例在 fixture 缺失时以 skipif 跳过；三个合成测试报表（SCE/PDF）已入库，clone 即可运行对应测试；缺失时同样跳过而非失败，可用 `tests/fixtures/generate_*.py` 重建。GUI 测试自动 offscreen（`tests/gui/conftest.py` 在 import PySide6 前设置 `QT_QPA_PLATFORM=offscreen`），无需环境变量。

## CONFTEST 两种风格（勿混用）

- **工厂函数**（多数）：`tests/conftest.py`、`tests/services/conftest.py`、`tests/importer/conftest.py`——直接 `from tests.conftest import make_balance_sheet` 调用，**不加 `@pytest.fixture`**
- **真 fixture**（少数）：`tests/storage/conftest.py`（tmp SQLite `db`/repo，自动 close）、`tests/gui/conftest.py`（`app_state`、autouse `clear_settings` 隔离 QSettings）、`tests/integration/conftest.py`（生成三表 Excel 的链式 fixture）
- GUI 层工厂在 `tests/gui/helpers.py`（`make_rule`/`make_result`/`make_report`——与根 conftest 的 `make_rule_bs_bal_001` 不同）

## 风格

- 场景类分组：`class TestBSBAL001Boundary` 等 + 每个测试带中文 docstring（场景→期望）
- 命名实况：`test_<scenario>_<expect>`（如 `test_diff_at_tolerance_passes`）；根文档 §4.3 的 `test_<fn>_<scenario>_<expect>` 在老套件中较宽松
- AAA 显式注释仅 storage 套件；其余为隐式 AAA（`make_*` 即 Arrange）
- 断言中文消息片段：`pytest.raises(X, match="必须包含")`；浮点比较用 `pytest.approx`
- 配置：`testpaths=["tests"]`、`pythonpath=["src"]`、`qt_api="pyside6"`；覆盖率 `fail_under=90`（未启用分支覆盖）

## FIXTURES 数据

- `tests/fixtures/real_reports/`：真实年报数据（git 忽略，需手动放置）＋ 合成测试报表（**已入库**：`测试报表_三大报表.pdf`、`测试报表_合并资产负债表.pdf`、`测试报表_含权益变动表.xlsx`，clone 即可运行对应测试）
- 合成 fixture 缺失时对应用例以 skipif 跳过（不报错），用 `tests/fixtures/generate_{realistic,pdf,sce}_report.py` 重建；语料构建见 `scripts/build_real_corpus.py` + `scripts/validate_corpus.py`
- GUI/importer 测试经 `_MOUTAI_FILE` 常量引用真实年报（缺失时跳过）

## 规则测试双层

- `tests/rules/test_rule_library_v11.py`：规则库静态完整性（**42 条**/无重复公式/全部可解析/比率规则除零保护/版本号；`test_exactly_42_rules`）
- `tests/rules/test_bs_bal_001.py`：单规则 E2E 全场景矩阵（唯一一条；其他规则依赖库级测试）

## scripts/ 手动验证（pytest 覆盖不到的）

- `python scripts/validate_real_data.py`——**发布门禁**：真实年报跑全部 42 条规则，0 失败 0 错误，exit 0/1。改规则库或发布前必跑
- `python scripts/verify_<module>.py`——各模块手动验证（agent/pdf_import/sce/export/update/theme/w3 等）
- `python scripts/ux_shots.py`——全页面明暗主题截图到 `ux_shots/`（纯目检）
- `python scripts/update_manifest_whitelist.py`——更新清单白名单维护
