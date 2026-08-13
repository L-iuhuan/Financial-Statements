"""多主体批量校验与双边核对测试。"""

from __future__ import annotations

from pathlib import Path

import openpyxl

from fsa.core.engine.registry import RuleRegistry
from fsa.services.entity_config import EntityConfig, load_entity_configs
from fsa.services.multi_entity_service import MultiEntityService


def _write_detail(path: Path, entity: str, counterparty: str, project: str, amount: float) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "内部现金流量明细表"
    headers = ["月份", "统计单位名称", "对方单位名称", "款项性质", "现金流量项目", "发生额"]
    for col_idx, header in enumerate(headers, 1):
        ws.cell(row=1, column=col_idx, value=header)
    row = [1, entity, counterparty, "货款", project, amount]
    for col_idx, value in enumerate(row, 1):
        ws.cell(row=2, column=col_idx, value=value)
    wb.save(str(path))


def _make_entity_folder(
    tmp_path: Path, name: str, counterparty: str, project: str, amount: float
) -> Path:
    folder = tmp_path / name
    folder.mkdir()
    from tests.importer.conftest import make_multi_sheet_excel

    make_multi_sheet_excel(folder)
    _write_detail(folder / "detail.xlsx", name, counterparty, project, amount)
    return folder


def _registry() -> RuleRegistry:
    return RuleRegistry.from_json(
        Path(__file__).resolve().parent.parent.parent / "cas_gouji_rule_library.json"
    )


class TestMultiEntityService:
    """多主体批量校验。"""

    def test_validate_two_entities(self, tmp_path: Path) -> None:
        folder_a = _make_entity_folder(
            tmp_path, "杭州杰为", "拓尔微", "收到的其他与经营活动的现金", 100.0
        )
        folder_b = _make_entity_folder(
            tmp_path, "拓尔微", "杭州杰为", "支付的其他与经营活动的现金", 100.0
        )
        result = MultiEntityService(_registry()).validate_folders(
            [str(folder_a), str(folder_b)], period="2026-06"
        )
        assert len(result.outcomes) == 2
        assert result.combined is not None
        assert result.combined.total > 0
        assert len(result.bilateral) == 1
        assert result.bilateral[0].passed is True

    def test_bilateral_mismatch_reported(self, tmp_path: Path) -> None:
        folder_a = _make_entity_folder(
            tmp_path, "杭州杰为", "拓尔微", "收到的其他与经营活动的现金", 120.0
        )
        folder_b = _make_entity_folder(
            tmp_path, "拓尔微", "杭州杰为", "支付的其他与经营活动的现金", 100.0
        )
        result = MultiEntityService(_registry()).validate_folders(
            [str(folder_a), str(folder_b)], period="2026-06"
        )
        bilateral = next(
            r for r in result.bilateral if r.rule_id == "ICF-002"
        )
        assert bilateral.passed is False
        assert bilateral.diff == 20.0


class TestEntityConfig:
    """主体级口径配置。"""

    def test_load_and_convert_config(self, tmp_path: Path) -> None:
        path = tmp_path / "entity_configs.json"
        path.write_text(
            '{"entities": {"杭州杰为": {"tolerance": 0.05, '
            '"cash_equivalent_codes": ["1002"], '
            '"tb_to_bs_mappings": {"monetary_funds": '
            '{"codes": ["1002"], "side": "debit"}}}}}',
            encoding="utf-8",
        )
        configs = load_entity_configs(path)
        config = configs["杭州杰为"]
        assert config.tolerance == 0.05
        assert config.cash_equivalent_codes == ("1002",)
        detail_config = config.to_detail_config()
        assert detail_config.tolerance == 0.05
        assert detail_config.cash_equivalent_codes == ("1002",)

    def test_default_config_keeps_standard_mappings(self) -> None:
        config = EntityConfig(entity_id="主体A")
        detail_config = config.to_detail_config()
        assert "monetary_funds" in detail_config.tb_to_bs_mappings
