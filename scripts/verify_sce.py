"""端到端验证: 含权益变动表工作簿的 SCE 规则激活情况。"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

from fsa.core.importer.importer import ImportService
from fsa.core.engine.registry import RuleRegistry
from fsa.services.validation_service import ValidationService
from fsa.core.resources import resource_path

registry = RuleRegistry.from_json(str(resource_path("cas_gouji_rule_library.json")))
reports = ImportService().import_file(
    "tests/fixtures/real_reports/测试报表_含权益变动表.xlsx"
)
print(f"导入 {len(reports)} 张报表:")
for r in reports:
    print(f"  {r.report_type.value}: {len(r.items)} 项")

summary = ValidationService(registry).validate(reports, "2024-12")
print(f"\n校验: total={summary.total} pass={summary.passed} fail={summary.failed} err={summary.errored} skip={summary.skipped}")

print("\nSCE 规则结果:")
for r in summary.results:
    if r.rule_id.startswith("SCE"):
        status = "通过" if r.passed and not r.skipped else ("跳过" if r.skipped else "不通过")
        print(f"  {r.rule_id:14s} {r.rule_name[:30]:32s} {status}")
        if not r.passed and not r.skipped:
            print(f"      L={r.left_value:,.2f} R={r.right_value:,.2f} diff={r.diff:,.2f}")
