"""语料库回归验证脚本: 对 tests/fixtures/real_reports/ 下全部真实年报执行导入+校验。

用法:
  python scripts/validate_corpus.py                 # 全部公司, 按 manifest 记录的行业参数化
  python scripts/validate_corpus.py --code 600519   # 单家公司

输出: 每家公司 passed/failed/errored/skipped 统计 + 失败/异常规则明细。
判定基线: 全部公司 errored=0 (0 异常); failed 规则逐条人工审查:
  - 记录在 manifest 白名单 (known_real_diffs) 的 → 已知真实差异 (白名单)
  - 未记录的 → 疑似系统缺陷, 需报告
"""
# ruff: noqa: E402 — 独立脚本需先设置 sys.path 再导入项目模块 (与 validate_real_data.py 同约定)

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 确保项目根在 sys.path 中
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from loguru import logger

from fsa.core.engine.registry import RuleRegistry
from fsa.core.importer.importer import ImportService
from fsa.core.models.result import ValidationSummary
from fsa.services.entity_config import EntityConfig
from fsa.services.validation_service import ValidationService

# 屏蔽 loguru 默认输出, 让脚本自身 print 报告更清晰
logger.remove()

_FIXTURES_DIR = _PROJECT_ROOT / "tests" / "fixtures" / "real_reports"
_MANIFEST = _FIXTURES_DIR / "manifest.json"
_RULE_LIBRARY = _PROJECT_ROOT / "cas_gouji_rule_library.json"


def _load_manifest() -> dict:
    """读取 manifest.json。"""
    if not _MANIFEST.exists():
        print(f"❌ manifest 不存在: {_MANIFEST}")
        sys.exit(1)
    return json.loads(_MANIFEST.read_text(encoding="utf-8"))


def _result_file(name: str, year: int) -> Path:
    """计算一家公司报表文件的路径。"""
    return _FIXTURES_DIR / f"{name}_{year}年报_三大报表.xlsx"


def _validate_company(
    service: ValidationService,
    name: str,
    file_path: Path,
    period: str,
    industry: str,
) -> tuple[ValidationSummary | None, str]:
    """对一家公司执行导入+校验。

    Returns:
        (汇总结果, 错误说明); 失败时汇总为 None
    """
    try:
        importer = ImportService(period=period)
        reports = importer.import_file(str(file_path))
    except FileNotFoundError:
        return None, f"文件不存在: {file_path}"
    except Exception as exc:  # 导入层具体异常类型多样, 统一报告 (合规: 非空捕获, 转中文说明)
        return None, f"导入失败: {type(exc).__name__}: {exc}"

    if not reports:
        return None, "未识别到任何报表"

    threshold_vars = EntityConfig(industry=industry).threshold_vars()
    summary = service.validate(reports, period=period, threshold_vars=threshold_vars)
    return summary, ""


def _print_company_header(name: str, industry: str, file_path: Path) -> None:
    """打印公司校验标题。"""
    print(f"\n{'=' * 68}")
    print(f"  校验: {name} (行业: {industry})")
    print(f"  文件: {file_path.name}")
    print(f"{'=' * 68}")


def _print_summary(summary: ValidationSummary) -> None:
    """打印汇总统计。"""
    print(
        f"  结果: 通过 {summary.passed} | 不通过 {summary.failed} | "
        f"异常 {summary.errored} | 跳过 {summary.skipped} (共 {summary.total})"
    )


def _print_failures(
    summary: ValidationSummary,
    whitelist: dict[str, str],
) -> None:
    """打印失败与异常规则明细, 区分白名单真实差异与疑似缺陷。"""
    for result in summary.results:
        if result.passed and not result.errored:
            continue
        if result.errored:
            tag = "疑似系统缺陷" if result.rule_id not in whitelist else "白名单真实差异"
            print(f"  ⚠️ [异常] {result.rule_id} {result.rule_name} ({tag})")
            print(f"      {result.message}")
        else:
            reason = whitelist.get(result.rule_id)
            tag = "待人工审查" if reason is None else "白名单真实差异"
            print(
                f"  ❌ [不通过] {result.rule_id} {result.rule_name} ({tag})"
                f" diff={result.diff:,.2f}"
            )
            print(f"      公式: {result.formula}")
            if reason is not None:
                print(f"      原因: {reason}")


def _collect_rule_results(summary: ValidationSummary) -> dict[str, str]:
    """收集规则 -> 状态 (passed/failed/errored/skipped)。"""
    states: dict[str, str] = {}
    for result in summary.results:
        if result.errored:
            states[result.rule_id] = "errored"
        elif result.skipped:
            states[result.rule_id] = "skipped"
        elif result.passed:
            states[result.rule_id] = "passed"
        else:
            states[result.rule_id] = "failed"
    return states


def _print_financial_comparison(
    service: ValidationService,
    company: dict,
    file_path: Path,
    period: str,
) -> None:
    """对金融类公司对比 general 与 financial 行业阈值下的结果 (LR-DAR-001 等)。"""
    print(f"\n  ▶ 金融行业参数化对比 ({company['name']}):")
    for industry in ("general", "financial"):
        summary, err = _validate_company(
            service, company["name"], file_path, period, industry
        )
        if err:
            print(f"    {industry}: {err}")
            continue
        assert summary is not None
        dar = next(
            (r for r in summary.results if r.rule_id == "LR-DAR-001"), None
        )
        if dar is None:
            dar_desc = "未执行(跳过)"
        elif dar.errored:
            dar_desc = f"异常: {dar.message}"
        elif dar.passed:
            dar_desc = f"通过 (left={dar.left_value:,.2f})"
        else:
            dar_desc = f"不通过 diff={dar.diff:,.4f} (left={dar.left_value:,.4f})"
        print(f"    {industry:>10}: LR-DAR-001 -> {dar_desc}")


def main() -> None:
    """语料库验证主流程。"""
    parser = argparse.ArgumentParser(description="真实年报语料库回归验证")
    parser.add_argument("--code", type=str, default="", help="仅验证指定公司代码")
    args = parser.parse_args()

    manifest = _load_manifest()
    registry = RuleRegistry.from_json(str(_RULE_LIBRARY))
    service = ValidationService(registry)

    results: list[dict] = []
    errored_any = False
    pending_failures: list[tuple[str, str]] = []

    for code, company in manifest.get("companies", {}).items():
        if args.code and code != args.code:
            continue
        name = company["name"]
        year = int(company.get("data_year", 2025))
        industry = company.get("industry", "general")
        file_path = _result_file(name, year)
        period = f"{year}-12"
        whitelist: dict[str, str] = {
            str(item["rule_id"]): str(item.get("reason", ""))
            for item in company.get("known_real_diffs", [])
        }

        _print_company_header(name, industry, file_path)
        if not file_path.exists():
            print(f"  ❌ 文件缺失: {file_path.name}")
            results.append({"name": name, "errored": True, "error": "file missing"})
            continue

        summary, err = _validate_company(service, name, file_path, period, industry)
        if err:
            print(f"  ❌ {err}")
            results.append({"name": name, "errored": True, "error": err})
            errored_any = True
            continue
        assert summary is not None  # 校验成功时必有汇总结果

        _print_summary(summary)
        if summary.errored > 0 or summary.failed > 0:
            _print_failures(summary, whitelist)
        if summary.errored > 0:
            errored_any = True

        for rule_id, state in _collect_rule_results(summary).items():
            if state == "failed" and rule_id not in whitelist:
                pending_failures.append((name, rule_id))

        unwhitelisted = sum(
            1
            for r in summary.results
            if not r.passed and not r.errored and r.rule_id not in whitelist
        )
        results.append(
            {
                "name": name,
                "code": code,
                "industry": industry,
                "passed": summary.passed,
                "failed": summary.failed,
                "errored": summary.errored,
                "skipped": summary.skipped,
                "unwhitelisted_failed": unwhitelisted,
            }
        )

        if company.get("industry") == "financial":
            _print_financial_comparison(service, company, file_path, period)

    # 汇总判定
    print(f"\n{'=' * 68}")
    print("  语料库汇总")
    print(f"{'=' * 68}")
    all_ok = True
    for r in results:
        if "error" in r:
            print(f"  ❌ {r['name']}: {r['error']}")
            all_ok = False
            continue
        unwhitelisted = r.get("unwhitelisted_failed", r["failed"])
        clean = r["errored"] == 0 and unwhitelisted == 0
        status = "✅" if clean else "❌"
        extra = f" (含 {unwhitelisted} 条未白名单失败)" if unwhitelisted else ""
        print(
            f"  {status} {r['name']}({r.get('code', '')}): "
            f"passed={r['passed']}, failed={r['failed']}, "
            f"errored={r['errored']}, skipped={r['skipped']}{extra}"
        )
        if not clean:
            all_ok = False

    if errored_any:
        print("\n  ❌ 存在异常(errored>0), 需排查系统缺陷")
    if pending_failures:
        print("\n  ⚠️ 存在未白名单化的失败规则 (需人工审查真伪):")
        for name, rule_id in pending_failures:
            print(f"      - {name}: {rule_id}")

    if all_ok and not errored_any and not pending_failures:
        print("\n  🎉 全部公司 0 异常, 失败规则均已白名单化, 语料库回归通过")
    else:
        print("\n  ❌ 语料库回归存在未白名单化的失败/异常, 详见上方明细")
    sys.exit(0 if all_ok and not errored_any else 1)


if __name__ == "__main__":
    main()
