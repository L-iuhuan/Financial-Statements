"""多主体批量校验与双边核对测试。"""

from __future__ import annotations

from pathlib import Path

import openpyxl
import pytest

from fsa.core.engine.registry import RuleRegistry
from fsa.core.exceptions import FSAError
from fsa.core.importer.detail_importer import DetailImporter
from fsa.core.importer.importer import ImportService
from fsa.core.models.detail import (
    DetailDataset,
    InternalCashFlowRow,
    RelatedPartyPurchaseRow,
    SalesDetailRow,
)
from fsa.core.models.report import Report, ReportType
from fsa.core.models.result import ValidationResult
from fsa.services.entity_config import EntityConfig, load_entity_configs
from fsa.services.multi_entity_service import EntityOutcome, MultiEntityService


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


def _write_dar_balance_sheet(
    folder: Path, asset: float = 100.0, liability: float = 88.0
) -> Path:
    """写入指定资产负债率 (liability/asset) 的资产负债表 Excel。"""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "资产负债表"
    headers = ["项目", "行次", "期末余额", "年初余额"]
    for col_idx, header in enumerate(headers, 1):
        ws.cell(row=1, column=col_idx, value=header)
    rows = [
        ("资产总计", 20, asset, asset),
        ("负债合计", 35, liability, liability),
        ("所有者权益合计", 50, asset - liability, asset - liability),
    ]
    for row_idx, (name, row_num, ending, beginning) in enumerate(rows, 2):
        ws.cell(row=row_idx, column=1, value=name)
        ws.cell(row=row_idx, column=2, value=row_num)
        ws.cell(row=row_idx, column=3, value=ending)
        ws.cell(row=row_idx, column=4, value=beginning)
    path = folder / "balance_sheet.xlsx"
    wb.save(str(path))
    return path


def _make_dar_folder(
    tmp_path: Path, name: str, asset: float = 100.0, liability: float = 88.0
) -> Path:
    """创建只含资产负债率 0.88 资产负债表的实体文件夹。"""
    folder = tmp_path / name
    folder.mkdir()
    _write_dar_balance_sheet(folder, asset, liability)
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


class TestBilateralExtension:
    """内部现金流双边核对: 科目对扩展与配置覆写。"""

    def test_investing_pair_matches(self, tmp_path: Path) -> None:
        """投资活动其他收支科目对纳入核对。"""
        folder_a = _make_entity_folder(
            tmp_path, "杭州杰为", "拓尔微", "收到的其他与投资活动的现金", 100.0
        )
        folder_b = _make_entity_folder(
            tmp_path, "拓尔微", "杭州杰为", "支付的其他与投资活动的现金", 100.0
        )
        result = MultiEntityService(_registry()).validate_folders(
            [str(folder_a), str(folder_b)], period="2026-06"
        )
        assert len(result.bilateral) == 1
        assert result.bilateral[0].passed is True
        assert "投资活动" in result.bilateral[0].message

    def test_financing_pair_matches(self, tmp_path: Path) -> None:
        """筹资活动其他收支科目对纳入核对。"""
        folder_a = _make_entity_folder(
            tmp_path, "杭州杰为", "拓尔微", "收到的其他与筹资活动的现金", 200.0
        )
        folder_b = _make_entity_folder(
            tmp_path, "拓尔微", "杭州杰为", "支付的其他与筹资活动的现金", 200.0
        )
        result = MultiEntityService(_registry()).validate_folders(
            [str(folder_a), str(folder_b)], period="2026-06"
        )
        assert len(result.bilateral) == 1
        assert result.bilateral[0].passed is True
        assert "筹资活动" in result.bilateral[0].message

    def test_bilateral_tolerance_override(self, tmp_path: Path) -> None:
        """entity_config.bilateral_tolerance 覆写: 差额 2.0 在容差 5.0 内通过。"""
        folder_a = _make_entity_folder(
            tmp_path, "杭州杰为", "拓尔微", "收到的其他与经营活动的现金", 100.0
        )
        folder_b = _make_entity_folder(
            tmp_path, "拓尔微", "杭州杰为", "支付的其他与经营活动的现金", 98.0
        )
        configs = {
            "杭州杰为": EntityConfig(entity_id="杭州杰为", bilateral_tolerance=5.0),
        }
        result = MultiEntityService(_registry(), configs=configs).validate_folders(
            [str(folder_a), str(folder_b)], period="2026-06"
        )
        assert len(result.bilateral) == 1
        assert result.bilateral[0].passed is True
        assert result.bilateral[0].tolerance == 5.0

    def test_bilateral_pairs_override_effective(self, tmp_path: Path) -> None:
        """entity_config.bilateral_pairs 覆写: 自定义科目对参与核对。"""
        folder_a = _make_entity_folder(
            tmp_path, "甲", "乙", "收到其他与投资活动有关的现金", 100.0
        )
        folder_b = _make_entity_folder(
            tmp_path, "乙", "甲", "支付其他与投资活动有关的现金", 100.0
        )
        configs = {
            "甲": EntityConfig(
                entity_id="甲",
                bilateral_pairs={
                    "收到其他与投资活动有关的现金": "支付其他与投资活动有关的现金"
                },
            )
        }
        result = MultiEntityService(_registry(), configs=configs).validate_folders(
            [str(folder_a), str(folder_b)], period="2026-06"
        )
        assert len(result.bilateral) == 1
        assert result.bilateral[0].passed is True


class TestBilateralAliasMatching:
    """双边核对别名匹配回归: 对方单位=公司全称, 与文件夹名不一致 (2026-09-17)。"""

    def test_alias_matches_company_full_name(self, tmp_path: Path) -> None:
        """配置别名后, 对方单位填公司全称仍能配对成功。"""
        folder_a = _make_entity_folder(
            tmp_path, "10厦门拓尔", "拓尔微电子股份有限公司",
            "收到的其他与经营活动的现金", 100.0,
        )
        folder_b = _make_entity_folder(
            tmp_path, "1西安拓尔微", "厦门拓尔微电子有限公司",
            "支付的其他与经营活动的现金", 100.0,
        )
        configs = {
            "10厦门拓尔": EntityConfig(
                entity_id="10厦门拓尔", aliases=("厦门拓尔微电子有限公司",)
            ),
            "1西安拓尔微": EntityConfig(
                entity_id="1西安拓尔微", aliases=("拓尔微电子股份有限公司",)
            ),
        }
        result = MultiEntityService(_registry(), configs=configs).validate_folders(
            [str(folder_a), str(folder_b)], period="2026-06"
        )
        assert len(result.bilateral) == 1, "别名匹配后应产出双边核对结果"
        assert result.bilateral[0].passed is True
        assert result.bilateral[0].rule_id == "ICF-002"

    def test_without_alias_full_name_does_not_match(self, tmp_path: Path) -> None:
        """无别名配置时公司全称配不上文件夹名 (记录修复前行为, 防回归)。"""
        folder_a = _make_entity_folder(
            tmp_path, "10厦门拓尔", "拓尔微电子股份有限公司",
            "收到的其他与经营活动的现金", 100.0,
        )
        folder_b = _make_entity_folder(
            tmp_path, "1西安拓尔微", "厦门拓尔微电子有限公司",
            "支付的其他与经营活动的现金", 100.0,
        )
        result = MultiEntityService(_registry()).validate_folders(
            [str(folder_a), str(folder_b)], period="2026-06"
        )
        assert len(result.bilateral) == 0

    def test_whitespace_in_counterparty_normalized(self, tmp_path: Path) -> None:
        """对方单位含多余空白时经归一化仍可匹配。"""
        folder_a = _make_entity_folder(
            tmp_path, "甲", "乙 公司", "收到的其他与经营活动的现金", 50.0
        )
        folder_b = _make_entity_folder(
            tmp_path, "乙", "甲公司", "支付的其他与经营活动的现金", 50.0
        )
        configs = {
            "甲": EntityConfig(entity_id="甲", aliases=("甲公司",)),
            "乙": EntityConfig(entity_id="乙", aliases=("乙公司",)),
        }
        result = MultiEntityService(_registry(), configs=configs).validate_folders(
            [str(folder_a), str(folder_b)], period="2026-06"
        )
        assert len(result.bilateral) == 1
        assert result.bilateral[0].passed is True


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

    def test_industry_default_general(self) -> None:
        """industry 默认 general, 阈值与 general 一致。"""
        config = EntityConfig(entity_id="主体A")
        assert config.industry == "general"
        assert config.threshold_vars()["dar_threshold"] == 0.85

    def test_industry_loaded_and_applied(self, tmp_path: Path) -> None:
        """industry 从配置 JSON 加载并映射阈值。"""
        path = tmp_path / "entity_configs.json"
        path.write_text(
            '{"entities": {"银行": {"industry": "financial"}}}',
            encoding="utf-8",
        )
        configs = load_entity_configs(path)
        config = configs["银行"]
        assert config.industry == "financial"
        assert config.threshold_vars()["dar_threshold"] == 0.92

    def test_industry_threshold_vars_mapping(self) -> None:
        """各行业阈值映射抽查。"""
        from fsa.core.engine.thresholds import threshold_vars_for

        assert threshold_vars_for("construction")["ar_to_revenue_threshold"] == 0.60
        assert threshold_vars_for("construction")["sales_cash_ratio_threshold"] == 0.5
        assert threshold_vars_for("retail")["current_ratio_threshold"] == 0.7
        assert threshold_vars_for("cyclical")["gm_yoy_threshold"] == 0.50
        assert threshold_vars_for("high_growth")["yoy_fluctuation_threshold"] == 0.50

    def test_load_entity_configs_parses_new_fields(self, tmp_path: Path) -> None:
        """load_entity_configs 解析新增的科目对/容差字段并透传到 detail 配置。"""
        path = tmp_path / "entity_configs.json"
        path.write_text(
            '{"entities": {"主体A": {'
            '"reclass_pairs": {"应收账款": ["预付款项"]}, '
            '"balance_sheet_accounts": {"accounts_receivable": "应收账款"}, '
            '"margin_tolerance": 0.02, '
            '"bilateral_pairs": {"收到的其他与投资活动的现金": "支付的其他与投资活动的现金"}, '
            '"bilateral_tolerance": 0.05}}}',
            encoding="utf-8",
        )
        configs = load_entity_configs(path)
        config = configs["主体A"]
        assert config.reclass_pairs == {"应收账款": ("预付款项",)}
        assert config.balance_sheet_accounts == {"accounts_receivable": "应收账款"}
        assert config.margin_tolerance == 0.02
        assert config.bilateral_pairs == {
            "收到的其他与投资活动的现金": "支付的其他与投资活动的现金"
        }
        assert config.bilateral_tolerance == 0.05
        detail_config = config.to_detail_config()
        assert detail_config.reclass_pairs == {"应收账款": ("预付款项",)}
        assert detail_config.balance_sheet_accounts == {
            "accounts_receivable": "应收账款"
        }
        assert detail_config.margin_tolerance == 0.02

    def test_save_entity_configs_roundtrip(self, tmp_path: Path) -> None:
        """save_entity_configs -> load_entity_configs 往返无损 (全字段保留)。"""
        from fsa.services.entity_config import save_entity_configs

        configs = {
            "1西安拓尔微": EntityConfig(
                entity_id="1西安拓尔微",
                aliases=("拓尔微电子股份有限公司", "西安拓尔"),
                industry="general",
                bilateral_tolerance=0.05,
            ),
            "10厦门拓尔": EntityConfig(
                entity_id="10厦门拓尔",
                aliases=("厦门拓尔微电子有限公司",),
                industry="retail",
                margin_tolerance=0.02,
            ),
        }
        path = tmp_path / "entity_config.json"
        save_entity_configs(configs, path)

        loaded = load_entity_configs(path)
        assert len(loaded) == 2
        assert loaded["1西安拓尔微"].aliases == ("拓尔微电子股份有限公司", "西安拓尔")
        assert loaded["1西安拓尔微"].bilateral_tolerance == 0.05
        assert loaded["1西安拓尔微"].industry == "general"
        assert loaded["10厦门拓尔"].aliases == ("厦门拓尔微电子有限公司",)
        assert loaded["10厦门拓尔"].industry == "retail"
        assert loaded["10厦门拓尔"].margin_tolerance == 0.02
        assert loaded["10厦门拓尔"].bilateral_tolerance is None

    def test_save_entity_configs_creates_parent_dir(self, tmp_path: Path) -> None:
        """保存路径父目录不存在时自动创建。"""
        from fsa.services.entity_config import save_entity_configs

        path = tmp_path / "deep" / "nested" / "entity_config.json"
        save_entity_configs({"A": EntityConfig(entity_id="A", aliases=("甲公司",))}, path)
        assert path.exists()
        loaded = load_entity_configs(path)
        assert loaded["A"].aliases == ("甲公司",)

    def test_new_fields_default_to_none(self) -> None:
        """新增字段缺省为 None（不改变默认行为）。"""
        config = EntityConfig(entity_id="主体A")
        assert config.reclass_pairs is None
        assert config.balance_sheet_accounts is None
        assert config.margin_tolerance is None
        assert config.bilateral_pairs is None
        assert config.bilateral_tolerance is None
        detail_config = config.to_detail_config()
        assert detail_config.reclass_pairs is None
        assert detail_config.balance_sheet_accounts is None
        assert detail_config.margin_tolerance is None


class TestMultiEntityIndustryThresholds:
    """多主体按行业注入 LR-* 阈值 (实体配置 -> 校验链路穿线)。"""

    @staticmethod
    def _dar_result(summary) -> ValidationResult:
        """从汇总结果中取 LR-DAR-001 结果。"""
        assert summary is not None
        return next(r for r in summary.results if r.rule_id == "LR-DAR-001")

    def test_financial_passes_general_fails(self, tmp_path: Path) -> None:
        """同一份资产负债率 0.88 报表: financial 主体通过, general 主体不通过。"""
        folder_bank = _make_dar_folder(tmp_path, "银行主体")
        folder_company = _make_dar_folder(tmp_path, "一般主体")
        configs = {
            "银行主体": EntityConfig(entity_id="银行主体", industry="financial"),
        }
        result = MultiEntityService(_registry(), configs=configs).validate_folders(
            [str(folder_bank), str(folder_company)], period="2026-06"
        )
        outcomes = {outcome.entity_id: outcome for outcome in result.outcomes}
        assert "银行主体" in outcomes
        assert "一般主体" in outcomes

        bank_dar = self._dar_result(outcomes["银行主体"].summary)
        company_dar = self._dar_result(outcomes["一般主体"].summary)
        assert bank_dar.passed is True   # financial 0.92 >= 0.88
        assert company_dar.passed is False  # general 0.85 < 0.88

    def test_single_entity_default_general_regression(self, tmp_path: Path) -> None:
        """单体校验 (无 entity_config) 走 general 默认阈值: 0.88 不通过。"""
        folder = _make_dar_folder(tmp_path, "默认主体")
        outcome = MultiEntityService(_registry()).validate_folder(
            str(folder), period="2026-06"
        )
        assert outcome.summary is not None
        dar = self._dar_result(outcome.summary)
        assert dar.passed is False


class TestImportOne:
    """_import_one 双轨导入: 读取一次、主表成功后才尝试明细, 明细失败仅调试日志。"""

    @pytest.fixture(autouse=True)
    def _stub_read(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """桩掉 read_excel, 防止测试触发真实 COM 回退 (启动 Excel 耗时数十秒)。"""
        import fsa.services.multi_entity_service as mod

        monkeypatch.setattr(mod, "read_excel", lambda *args, **kwargs: {})

    def test_main_failure_records_single_error_and_skips_detail(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """读取失败: 记录一条错误且不再尝试明细导入（避免重复错误）。"""
        folder = tmp_path / "主体A"
        folder.mkdir()
        (folder / "bad.xlsx").write_text("非报表文件", encoding="utf-8")
        import fsa.services.multi_entity_service as mod

        def _fail_read(*args: object, **kwargs: object) -> dict[str, object]:
            raise FSAError("无法识别报表")

        detail_calls: list[object] = []

        def _spy_detail(self: DetailImporter, data: object) -> DetailDataset:
            detail_calls.append(data)
            return DetailDataset()

        monkeypatch.setattr(mod, "read_excel", _fail_read)
        monkeypatch.setattr(DetailImporter, "import_data", _spy_detail)

        outcome = MultiEntityService(_registry()).validate_folder(
            str(folder), period="2026-06"
        )

        assert len(outcome.errors) == 1
        assert "bad.xlsx" in outcome.errors[0]
        assert detail_calls == []

    def test_detail_failure_only_logged_debug(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """主表导入成功、明细导入失败: 不记录错误（纯主表文件属预期路径）。"""
        folder = tmp_path / "主体B"
        folder.mkdir()
        (folder / "main.xlsx").write_text("主表文件占位", encoding="utf-8")

        def _fail_detail(self: DetailImporter, data: object) -> DetailDataset:
            raise FSAError("非明细文件")

        monkeypatch.setattr(DetailImporter, "import_data", _fail_detail)

        outcome = MultiEntityService(_registry()).validate_folder(
            str(folder), period="2026-06"
        )

        assert outcome.errors == []

    def test_main_success_then_detail_import(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """主表导入成功后继续明细导入, 同一份原始数据供两边复用 (读一次)。"""
        folder = tmp_path / "主体C"
        folder.mkdir()
        (folder / "data.xlsx").write_text("占位", encoding="utf-8")

        captured: dict[str, object] = {}

        def _ok_main(
            self: ImportService, data: object, source_file: str, suffix: str
        ) -> list[Report]:
            captured["main_raw"] = data
            report = Report(
                report_type=ReportType.BALANCE_SHEET,
                period="2026-06",
                source_file=source_file,
                items=[],
            )
            return [report]

        def _spy_detail(self: DetailImporter, data: object) -> DetailDataset:
            captured["detail_raw"] = data
            return DetailDataset()

        monkeypatch.setattr(ImportService, "import_data", _ok_main)
        monkeypatch.setattr(DetailImporter, "import_data", _spy_detail)

        outcome = MultiEntityService(_registry()).validate_folder(
            str(folder), period="2026-06"
        )

        assert outcome.errors == []
        assert len(outcome.reports) == 1
        assert outcome.reports[0].report_type == ReportType.BALANCE_SHEET
        assert (
            captured["main_raw"] is captured["detail_raw"]
        ), "主表与明细应复用同一份原始数据 (读一次)"

    def test_reads_excel_once_per_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """回归 (2026-09-18 性能修复): 每个文件只读一次, 不再主表/明细各读一遍。"""
        folder = tmp_path / "主体D"
        folder.mkdir()
        (folder / "a.xlsx").write_text("占位", encoding="utf-8")
        (folder / "b.xlsx").write_text("占位", encoding="utf-8")
        import fsa.services.multi_entity_service as mod

        read_calls: list[str] = []

        def _count_read(
            file_path: str, com_session: object = None
        ) -> dict[str, object]:
            read_calls.append(file_path)
            return {}

        monkeypatch.setattr(mod, "read_excel", _count_read)

        MultiEntityService(_registry()).validate_folder(str(folder), period="2026-06")

        assert sorted(read_calls) == sorted(
            [str(folder / "a.xlsx"), str(folder / "b.xlsx")]
        ), "每个文件必须只读取一次 (DLP 加密文件 COM 读取成本高)"

    def test_validate_folder_emits_per_file_progress(
        self, tmp_path: Path
    ) -> None:
        """逐文件进度: 消息含 第 i/N 个文件 与文件名 (GUI 状态栏反馈)。"""
        folder = tmp_path / "主体E"
        folder.mkdir()
        (folder / "甲.xlsx").write_text("占位", encoding="utf-8")
        (folder / "乙.xlsx").write_text("占位", encoding="utf-8")

        messages: list[str] = []
        MultiEntityService(_registry()).validate_folder(
            str(folder), period="2026-06", progress_cb=messages.append
        )

        # 注: sorted(iterdir) 按码点排序, 乙(U+4E59) 先于 甲(U+7532) —— 断言顺序无关
        assert len(messages) == 2, "每个文件一条进度消息"
        assert any("1/2" in m for m in messages)
        assert any("2/2" in m for m in messages)
        assert any("甲.xlsx" in m for m in messages)
        assert any("乙.xlsx" in m for m in messages)


def _make_purchase_outcome(
    entity_id: str,
    purchases: list[RelatedPartyPurchaseRow] | None = None,
    sales: list[SalesDetailRow] | None = None,
) -> EntityOutcome:
    """构造仅含附表4/附表5明细的 EntityOutcome（不经过文件导入）。"""
    dataset = DetailDataset(entity=entity_id)
    dataset.related_party_purchases = purchases or []
    dataset.sales_details = sales or []
    return EntityOutcome(entity_id=entity_id, folder="", dataset=dataset)


class TestPurchaseSalesBilateral:
    """跨主体附表4 ↔ 附表5 关联方购销双边核对。"""

    def test_alias_matching_bidirectional_pass(self) -> None:
        """对方单位用公司全称、主体用短名+别名, 双向均匹配通过。"""
        left_purchases = [
            RelatedPartyPurchaseRow(
                buyer="10厦门拓尔",
                counterparty="拓尔微电子股份有限公司",
                payment_nature="货款",
                total_amount=12345.67,
            )
        ]
        right_sales = [
            SalesDetailRow(
                year=2026,
                month=6,
                entity="1西安拓尔微",
                customer="厦门拓尔微电子有限公司",
                revenue_type="销售",
                revenue_amount=12345.67,
                cost_amount=0.0,
            )
        ]
        right_purchases = [
            RelatedPartyPurchaseRow(
                buyer="1西安拓尔微",
                counterparty="厦门拓尔微电子有限公司",
                payment_nature="货款",
                total_amount=10000.0,
            )
        ]
        left_sales = [
            SalesDetailRow(
                year=2026,
                month=6,
                entity="10厦门拓尔",
                customer="拓尔微电子股份有限公司",
                revenue_type="销售",
                revenue_amount=10000.0,
                cost_amount=0.0,
            )
        ]
        left = _make_purchase_outcome(
            "10厦门拓尔", purchases=left_purchases, sales=left_sales
        )
        right = _make_purchase_outcome(
            "1西安拓尔微", purchases=right_purchases, sales=right_sales
        )
        configs = {
            "10厦门拓尔": EntityConfig(
                entity_id="10厦门拓尔", aliases=("厦门拓尔微电子有限公司",)
            ),
            "1西安拓尔微": EntityConfig(
                entity_id="1西安拓尔微", aliases=("拓尔微电子股份有限公司",)
            ),
        }
        service = MultiEntityService(_registry(), configs=configs)
        results = service.check_purchase_sales([left, right])
        assert len(results) == 2
        assert all(r.passed for r in results)
        assert all(r.rule_id == "RPS-001" for r in results)

    def test_amount_mismatch_reports_fail_and_diff(self) -> None:
        """采购与销售金额不一致时产出不通过, diff 数值正确。"""
        left_purchases = [
            RelatedPartyPurchaseRow(
                buyer="A", counterparty="B", payment_nature="货款", total_amount=120.0
            )
        ]
        right_sales = [
            SalesDetailRow(
                year=2026, month=6, entity="B", customer="A",
                revenue_type="销售", revenue_amount=100.0,
                cost_amount=0.0,
            )
        ]
        left = _make_purchase_outcome("A", purchases=left_purchases)
        right = _make_purchase_outcome("B", sales=right_sales)
        service = MultiEntityService(_registry())
        results = service.check_purchase_sales([left, right])
        assert len(results) == 1
        assert results[0].passed is False
        assert results[0].diff == 20.0
        assert "差额 20.00 元" in results[0].message

    def test_no_data_returns_empty(self) -> None:
        """双方都无相关购销明细时不产出结果。"""
        left = _make_purchase_outcome("A")
        right = _make_purchase_outcome("B")
        service = MultiEntityService(_registry())
        results = service.check_purchase_sales([left, right])
        assert results == []

    def test_direction_not_swapped(self) -> None:
        """left采购 vs right销售配成一条, 左右值不串。"""
        left_purchases = [
            RelatedPartyPurchaseRow(
                buyer="A", counterparty="B", payment_nature="货款", total_amount=300.0
            )
        ]
        right_sales = [
            SalesDetailRow(
                year=2026, month=6, entity="B", customer="A",
                revenue_type="销售", revenue_amount=300.0,
                cost_amount=0.0,
            )
        ]
        left = _make_purchase_outcome("A", purchases=left_purchases)
        right = _make_purchase_outcome("B", sales=right_sales)
        service = MultiEntityService(_registry())
        results = service.check_purchase_sales([left, right])
        assert len(results) == 1
        assert results[0].left_value == 300.0
        assert results[0].right_value == 300.0
        assert results[0].passed is True
        assert "A」向「B」采购" in results[0].message
        assert "对方「B」对「A」销售" in results[0].message

    def test_tolerance_override_allows_small_diff(self) -> None:
        """bilateral_tolerance 覆写: 差额 0.5 在容差 1.0 内通过。"""
        left_purchases = [
            RelatedPartyPurchaseRow(
                buyer="A", counterparty="B", payment_nature="货款", total_amount=100.5
            )
        ]
        right_sales = [
            SalesDetailRow(
                year=2026, month=6, entity="B", customer="A",
                revenue_type="销售", revenue_amount=100.0,
                cost_amount=0.0,
            )
        ]
        left = _make_purchase_outcome("A", purchases=left_purchases)
        right = _make_purchase_outcome("B", sales=right_sales)
        configs = {"A": EntityConfig(entity_id="A", bilateral_tolerance=1.0)}
        service = MultiEntityService(_registry(), configs=configs)
        results = service.check_purchase_sales([left, right])
        assert len(results) == 1
        assert results[0].passed is True
        assert results[0].tolerance == 1.0
        assert results[0].diff == 0.5

    def test_missing_sales_table_skips_direction(self) -> None:
        """P1: 卖方整体未提供附表5(销售明细)时跳过, 不把「缺表」当「差额」误报。"""
        left_purchases = [
            RelatedPartyPurchaseRow(
                buyer="A", counterparty="B", payment_nature="货款", total_amount=100.0
            )
        ]
        left = _make_purchase_outcome("A", purchases=left_purchases)
        right = _make_purchase_outcome("B")  # B 无附表5
        service = MultiEntityService(_registry())
        results = service.check_purchase_sales([left, right])
        assert results == []

    def test_missing_purchase_table_skips_direction(self) -> None:
        """P1: 买方整体未提供附表4(采购明细)时跳过, 不把「缺表」当「差额」误报。"""
        right_sales = [
            SalesDetailRow(
                year=2026, month=6, entity="B", customer="A",
                revenue_type="销售", revenue_amount=100.0,
                cost_amount=0.0,
            )
        ]
        left = _make_purchase_outcome("A")  # A 无附表4
        right = _make_purchase_outcome("B", sales=right_sales)
        service = MultiEntityService(_registry())
        results = service.check_purchase_sales([left, right])
        assert results == []


    def test_single_side_zero_failure_suggests_alias(self) -> None:
        """单边为零的不通过结果提示检查别名配置 (oracle 评审建议)。"""
        left_purchases = [
            RelatedPartyPurchaseRow(
                buyer="A", counterparty="B", payment_nature="货款", total_amount=100.0
            )
        ]
        # B 的附表5 只登记了对其他客户的销售, 对 A 无匹配 (别名缺失)
        right_sales = [
            SalesDetailRow(
                year=2026, month=6, entity="B", customer="其他客户",
                revenue_type="销售", revenue_amount=500.0,
                cost_amount=0.0,
            )
        ]
        left = _make_purchase_outcome("A", purchases=left_purchases)
        right = _make_purchase_outcome("B", sales=right_sales)
        service = MultiEntityService(_registry())
        results = service.check_purchase_sales([left, right])
        assert len(results) == 1
        assert results[0].passed is False
        assert "补充别名" in results[0].message
        assert "【为什么关注】" in results[0].message


def _make_icf_outcome(
    entity_id: str, counterparty: str, amount: float, project: str
) -> EntityOutcome:
    """构造仅含附表6 内部现金流明细一行的 EntityOutcome。"""
    dataset = DetailDataset(entity=entity_id)
    dataset.internal_cash_flows = [
        InternalCashFlowRow(
            month=6,
            entity=entity_id,
            counterparty=counterparty,
            payment_nature="货款",
            project=project,
            amount=amount,
        )
    ]
    return EntityOutcome(entity_id=entity_id, folder="", dataset=dataset)


class TestBilateralMissingTableGuard:
    """P1: 内部现金流双边核对缺表跳过 (2026-09-17)。"""

    def test_missing_icf_table_skips_pair(self) -> None:
        """一方整体未提供附表6 时不产出双边结果 (缺数据 ≠ 差额)。"""
        left = _make_icf_outcome(
            "A", counterparty="B", amount=100.0,
            project="销售商品、提供劳务收到的现金",
        )
        right = EntityOutcome(entity_id="B", folder="", dataset=DetailDataset(entity="B"))
        service = MultiEntityService(_registry())
        results = service.check_bilateral([left, right])
        assert results == []

    def test_both_tables_present_still_checks(self) -> None:
        """双方都有附表6 时正常产出核对结果 (守卫不误伤正常路径)。"""
        left = _make_icf_outcome(
            "A", counterparty="B", amount=100.0,
            project="销售商品、提供劳务收到的现金",
        )
        right = _make_icf_outcome(
            "B", counterparty="A", amount=100.0,
            project="购买商品、接受劳务支付的现金",
        )
        service = MultiEntityService(_registry())
        results = service.check_bilateral([left, right])
        # 仅 A流入↔B流出 一个方向有数据, 产出 1 条通过结果
        assert len(results) == 1
        assert results[0].passed is True
        assert results[0].diff == 0.0

    def test_icf_single_side_zero_failure_suggests_alias(self) -> None:
        """ICF 单边为零的不通过结果提示检查别名配置。"""
        left = _make_icf_outcome(
            "A", counterparty="B", amount=100.0,
            project="销售商品、提供劳务收到的现金",
        )
        # B 的附表6 只登记了对 C 的往来, 对 A 无匹配 (别名缺失)
        right = _make_icf_outcome(
            "B", counterparty="C", amount=500.0,
            project="购买商品、接受劳务支付的现金",
        )
        service = MultiEntityService(_registry())
        results = service.check_bilateral([left, right])
        assert len(results) == 1
        assert results[0].passed is False
        assert "补充别名" in results[0].message


class TestSharedComSession:
    """共享 Excel COM 会话管理 (2026-09-17 "卡死"根因修复)。"""

    def test_close_idempotent(self) -> None:
        """close() 未启动会话时为空操作, 重复调用安全。"""
        service = MultiEntityService(_registry())
        service.close()
        service.close()

    def test_validate_folders_closes_session(self, tmp_path: Path) -> None:
        """validate_folders 结束后自动关闭共享会话。"""
        close_calls: list[int] = []

        class _FakeSession:
            def close(self) -> None:
                close_calls.append(1)

        service = MultiEntityService(_registry())
        service._com_session = _FakeSession()  # type: ignore[assignment]

        folder = tmp_path / "空主体"
        folder.mkdir()
        service.validate_folders([str(folder)], period="2026-06")

        assert close_calls == [1], "validate_folders 结束后应关闭共享会话"
        assert service._com_session is None, "close 后会话引用应清空"

    def test_empty_folder_records_error(self, tmp_path: Path) -> None:
        """空文件夹 (无可导入文件) 记录中文错误提示。"""
        folder = tmp_path / "空主体"
        folder.mkdir()
        service = MultiEntityService(_registry())
        outcome = service.validate_folder(str(folder), period="2026-06")
        assert outcome.errors, "空文件夹应记录错误"
        assert "没有可导入" in outcome.errors[0]

    def test_import_one_passes_shared_session(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_import_one 将共享 COM 会话传给 read_excel, 且每文件只读一次。"""
        folder = tmp_path / "主体A"
        folder.mkdir()
        (folder / "data.xlsx").write_text("占位", encoding="utf-8")
        import fsa.services.multi_entity_service as mod

        sessions: list[object] = []

        def _spy_read(
            file_path: str, com_session: object = None
        ) -> dict[str, object]:
            sessions.append(com_session)
            return {}

        def _stub_detail(self: DetailImporter, data: object) -> DetailDataset:
            return DetailDataset()

        monkeypatch.setattr(mod, "read_excel", _spy_read)
        monkeypatch.setattr(DetailImporter, "import_data", _stub_detail)

        service = MultiEntityService(_registry())
        service.validate_folder(str(folder), period="2026-06")

        assert sessions, "read_excel 应被调用"
        assert sessions[0] is service._com_session, "应传入共享 COM 会话"
        assert len(sessions) == 1, "主表与明细复用同一次读取"
        service.close()
