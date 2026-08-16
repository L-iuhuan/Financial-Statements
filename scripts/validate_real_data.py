"""真实数据验证脚本 (发布门禁): 对真实年报执行全部规则。

用法:
  python scripts/validate_real_data.py            # 默认: 茅台/格力 (manifest 驱动)
  python scripts/validate_real_data.py --all      # manifest 中全部公司
  python scripts/validate_real_data.py --code 600519

判定: 每家公司 0 异常且 0 条未白名单失败 → exit 0, 否则 exit 1。
manifest known_real_diffs 白名单内的已知真实差异不算失败 (与 validate_corpus.py 同口径)。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 确保项目根在 sys.path 中
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from fsa.core.engine.registry import RuleRegistry  # noqa: E402
from fsa.core.importer.importer import ImportService  # noqa: E402
from fsa.services.entity_config import EntityConfig  # noqa: E402
from fsa.services.validation_service import ValidationService  # noqa: E402

_FIXTURES_DIR = _PROJECT_ROOT / "tests" / "fixtures" / "real_reports"
_MANIFEST = _FIXTURES_DIR / "manifest.json"
_RULE_LIBRARY = _PROJECT_ROOT / "cas_gouji_rule_library.json"
_DEFAULT_CODES = ("600519", "000651")  # 贵州茅台 / 格力电器


def _load_manifest() -> dict:
    """读取 manifest.json。"""
    if not _MANIFEST.exists():
        print(f"❌ manifest 不存在: {_MANIFEST}")
        sys.exit(1)
    return json.loads(_MANIFEST.read_text(encoding="utf-8"))


def _select_companies(manifest: dict, code: str, run_all: bool) -> list[tuple[str, dict]]:
    """按参数从 manifest 选取公司。"""
    companies: dict = manifest.get("companies", {})
    if code:
        if code not in companies:
            print(f"❌ manifest 中无公司代码 {code}")
            sys.exit(1)
        return [(code, companies[code])]
    if run_all:
        return list(companies.items())
    selected = [(c, companies[c]) for c in _DEFAULT_CODES if c in companies]
    if not selected:
        print("❌ manifest 中无默认公司 (600519/000651)")
        sys.exit(1)
    return selected


def validate_company(name: str, file_path: Path, period: str, industry: str) -> dict:
    """对一家公司的报表执行校验, 返回统计字典。"""
    print(f"\n{'=' * 60}")
    print(f"  校验: {name} (行业: {industry})")
    print(f"  文件: {file_path}")
    print(f"{'=' * 60}")

    importer = ImportService(period=period)
    try:
        reports = importer.import_file(str(file_path))
    except FileNotFoundError:
        print(f"  ❌ 文件不存在: {file_path}")
        return {"name": name, "error": f"文件不存在: {file_path}"}
    except Exception as e:  # 导入层异常类型多样, 统一转中文说明
        print(f"  ❌ 导入失败: {type(e).__name__}: {e}")
        return {"name": name, "error": f"导入失败: {type(e).__name__}: {e}"}

    print(f"  导入报表: {len(reports)} 张")
    for r in reports:
        print(f"    - {r.report_type.value}: {len(r.items)} 个科目")

    registry = RuleRegistry.from_json(str(_RULE_LIBRARY))
    service = ValidationService(registry)
    threshold_vars = EntityConfig(industry=industry).threshold_vars()
    summary = service.validate(reports, period, threshold_vars=threshold_vars)

    print("\n  结果汇总:")
    print(f"    总规则数: {summary.total}")
    print(f"    通过: {summary.passed}")
    print(f"    不通过: {summary.failed}")
    print(f"    异常: {summary.errored}")
    print(f"    跳过: {summary.skipped}")

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

    failed_ids = [
        r.rule_id for r in summary.results if not r.passed and not r.errored
    ]
    return {
        "name": name,
        "total": summary.total,
        "passed": summary.passed,
        "failed": summary.failed,
        "errored": summary.errored,
        "skipped": summary.skipped,
        "failed_ids": failed_ids,
    }


def main() -> None:
    """发布门禁主流程。"""
    parser = argparse.ArgumentParser(description="真实数据验证 (发布门禁)")
    parser.add_argument("--code", type=str, default="", help="仅验证指定公司代码")
    parser.add_argument("--all", action="store_true", help="验证 manifest 中全部公司")
    args = parser.parse_args()

    manifest = _load_manifest()
    selected = _select_companies(manifest, args.code, args.all)

    results: list[dict] = []
    whitelists: dict[str, dict[str, str]] = {}
    for _code, company in selected:
        name = company["name"]
        year = int(company.get("data_year", 2025))
        industry = company.get("industry", "general")
        file_path = _FIXTURES_DIR / f"{name}_{year}年报_三大报表.xlsx"
        whitelists[name] = {
            str(item["rule_id"]): str(item.get("reason", ""))
            for item in company.get("known_real_diffs", [])
        }
        results.append(validate_company(name, file_path, f"{year}-12", industry))

    # 最终判定: 0 异常, 且失败规则全部在 manifest 白名单内
    print(f"\n{'=' * 60}")
    print("  最终判定")
    print(f"{'=' * 60}")

    all_ok = True
    for r in results:
        name = r.get("name", "未知公司")
        if "error" in r:
            print(f"  ❌ {name}: {r['error']}")
            all_ok = False
            continue
        whitelist = whitelists.get(name, {})
        unwhitelisted = [rid for rid in r["failed_ids"] if rid not in whitelist]
        clean = r["errored"] == 0 and not unwhitelisted
        status = "✅" if clean else "❌"
        print(
            f"  {status} {name}: "
            f"passed={r['passed']}, failed={r['failed']}, "
            f"errored={r['errored']}, skipped={r['skipped']}"
        )
        for rid in unwhitelisted:
            print(f"      ⚠️ 未白名单失败: {rid}")
        if not clean:
            all_ok = False

    if all_ok:
        print("\n  🎉 全部通过: 0 异常, 失败规则均已白名单化")
    else:
        print("\n  ❌ 存在异常或未白名单化的失败, 请检查")

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
