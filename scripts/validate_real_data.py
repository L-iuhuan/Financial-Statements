"""真实数据验证脚本: 对贵州茅台/格力电器 2023 年报执行全部 37 条规则。

用法: python scripts/validate_real_data.py

预期: 茅台和格力均 0 fail, 0 error (skips 可接受)。
双列引擎 (W1) 正在并行构建 — 依赖 _beginning/_ending 变量的规则可能跳过,
这是预期行为。脚本会记录哪些规则在等待引擎。
"""

from __future__ import annotations

import sys
from pathlib import Path

# 确保项目根在 sys.path 中
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fsa.core.engine.registry import RuleRegistry
from fsa.core.importer.importer import ImportService
from fsa.services.validation_service import ValidationService


def validate_company(name: str, file_path: str) -> dict:
    """对一家公司的报表执行校验, 返回统计字典。"""
    print(f"\n{'='*60}")
    print(f"  校验: {name}")
    print(f"  文件: {file_path}")
    print(f"{'='*60}")

    importer = ImportService(period="2023-12")
    try:
        reports = importer.import_file(file_path)
    except FileNotFoundError:
        print(f"  ❌ 文件不存在: {file_path}")
        return {"error": "file not found"}
    except Exception as e:
        print(f"  ❌ 导入失败: {e}")
        return {"error": str(e)}

    print(f"  导入报表: {len(reports)} 张")
    for r in reports:
        print(f"    - {r.report_type.value}: {len(r.items)} 个科目")

    registry = RuleRegistry.from_json("cas_gouji_rule_library.json")
    service = ValidationService(registry)
    summary = service.validate(reports, "2023-12")

    print(f"\n  结果汇总:")
    print(f"    总规则数: {summary.total}")
    print(f"    通过: {summary.passed}")
    print(f"    不通过: {summary.failed}")
    print(f"    异常: {summary.errored}")
    print(f"    跳过: {summary.skipped}")

    # 列出不通过和异常的规则
    if summary.failed > 0:
        print(f"\n  ❌ 不通过 ({summary.failed} 条):")
        for r in summary.results:
            if not r.passed and not r.errored:
                print(f"    [{r.rule_id}] {r.rule_name}: diff={r.diff:.2f}")

    if summary.errored > 0:
        print(f"\n  ⚠️ 异常 ({summary.errored} 条):")
        for r in summary.results:
            if r.errored:
                print(f"    [{r.rule_id}] {r.rule_name}: {r.message}")

    # 列出跳过规则 (区分原因)
    skipped_by_missing_report: list[str] = []
    skipped_by_missing_var: list[str] = []
    for r in summary.results:
        if r.skipped:
            if "跳过 -" in r.message:
                skipped_by_missing_var.append(r.rule_id)
            else:
                skipped_by_missing_report.append(r.rule_id)

    if skipped_by_missing_var:
        print(f"\n  ℹ️ 因缺少变量跳过 ({len(skipped_by_missing_var)} 条):")
        for rid in skipped_by_missing_var:
            r = next(rr for rr in summary.results if rr.rule_id == rid)
            print(f"    [{rid}] {r.rule_name}: {r.message}")

    # 识别等待双列引擎的规则
    dual_column_awaiting: list[str] = []
    for r in summary.results:
        if r.skipped and any(
            suffix in r.message
            for suffix in ["_ending", "_beginning", "cf_notes_"]
        ):
            dual_column_awaiting.append(r.rule_id)

    if dual_column_awaiting:
        print(f"\n  🔧 等待双列引擎 (W1) ({len(dual_column_awaiting)} 条):")
        for rid in dual_column_awaiting:
            r = next(rr for rr in summary.results if rr.rule_id == rid)
            print(f"    [{rid}] {r.rule_name}")

    return {
        "name": name,
        "total": summary.total,
        "passed": summary.passed,
        "failed": summary.failed,
        "errored": summary.errored,
        "skipped": summary.skipped,
        "dual_column_awaiting": dual_column_awaiting,
    }


def main() -> None:
    base = Path(__file__).resolve().parent.parent / "tests/fixtures/real_reports"

    companies = [
        ("贵州茅台", str(base / "贵州茅台_2023年报_三大报表.xlsx")),
        ("格力电器", str(base / "格力电器_2023年报_三大报表.xlsx")),
    ]

    results: list[dict] = []
    for name, path in companies:
        results.append(validate_company(name, path))

    # 最终判定
    print(f"\n{'='*60}")
    print(f"  最终判定")
    print(f"{'='*60}")

    all_ok = True
    for r in results:
        if "error" in r:
            print(f"  ❌ {r['name']}: 导入失败 ({r['error']})")
            all_ok = False
            continue
        status = "✅" if r["failed"] == 0 and r["errored"] == 0 else "❌"
        print(
            f"  {status} {r['name']}: "
            f"passed={r['passed']}, failed={r['failed']}, "
            f"errored={r['errored']}, skipped={r['skipped']}"
        )
        if r["failed"] > 0 or r["errored"] > 0:
            all_ok = False

    if all_ok:
        print("\n  🎉 全部通过: 无 fail, 无 error")
    else:
        print("\n  ❌ 存在不通过或异常, 请检查")

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()