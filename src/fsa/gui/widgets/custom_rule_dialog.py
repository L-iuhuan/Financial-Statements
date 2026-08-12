"""自定义规则新增对话框。

提供表单录入规则的各个字段, 并在保存前用引擎的 ExpressionEvaluator
校验公式合法性 (面向财务用户的中文错误提示)。
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from fsa.core.engine.evaluator import ExpressionEvaluator
from fsa.core.models.rule import ReconciliationRule, Severity, ToleranceType

_CATEGORIES = ["A-表内平衡", "B-表间勾稽", "C-逻辑合理性"]
_STATEMENTS = ["资产负债表", "利润表", "现金流量表", "所有者权益变动表"]
_TOLERANCE_TYPES = [
    ("精确 (exact)", "exact"),
    ("绝对 (absolute)", "absolute"),
    ("相对 (relative)", "relative"),
    ("阈值 (threshold)", "threshold"),
]
_SEVERITIES = [("错误", "error"), ("警告", "warning"), ("提示", "info")]

# 常用公式模板: (显示名, 公式, 说明)
_FORMULA_TEMPLATES = [
    ("选择模板快速填充...", "", ""),
    ("资产=负债+所有者权益", "asset_total == liability_total + equity_total",
     "资产负债表恒等式"),
    ("流动+非流动=资产总计", "current_assets + non_current_assets == asset_total",
     "资产结构平衡"),
    ("流动+非流动=负债合计", "current_liabilities + non_current_liabilities == liability_total",
     "负债结构平衡"),
    ("净利润=利润总额-所得税", "net_profit == total_profit - income_tax_expense",
     "利润表勾稽"),
    ("现金净增加=三活动净额+汇率影响", "net_increase_cash == operating_net + investing_net + financing_net + fx_effect",
     "现金流量表勾稽"),
    ("期末现金=期初+净增加", "ending_cash_equiv == beginning_cash_equiv + net_increase_cash",
     "现金期初期末衔接"),
    ("资产负债率 ≤ 阈值", "liability_total / asset_total <= 0.85",
     "偿债能力 (阈值型)"),
    ("流动比率 ≥ 1", "current_liabilities == 0 or current_assets / current_liabilities >= 1",
     "短期偿债 (阈值型)"),
    ("毛利率在合理区间", "revenue == 0 or ((revenue - operating_cost) / revenue >= 0 and (revenue - operating_cost) / revenue <= 1)",
     "毛利率 0-100% (阈值型)"),
]

# 可用变量对照: (中文科目, 变量名)
_VARIABLE_REFERENCE = [
    ("资产总计", "asset_total"), ("负债合计", "liability_total"),
    ("所有者权益合计", "equity_total"), ("流动资产合计", "current_assets"),
    ("非流动资产合计", "non_current_assets"), ("流动负债合计", "current_liabilities"),
    ("非流动负债合计", "non_current_liabilities"), ("货币资金", "monetary_funds"),
    ("应收账款", "accounts_receivable"), ("存货", "inventory"),
    ("营业收入", "revenue"), ("营业成本", "operating_cost"),
    ("营业利润", "operating_profit"), ("利润总额", "total_profit"),
    ("净利润", "net_profit"), ("所得税费用", "income_tax_expense"),
    ("经营活动现金流净额", "operating_net"), ("投资活动现金流净额", "investing_net"),
    ("筹资活动现金流净额", "financing_net"), ("现金净增加额", "net_increase_cash"),
    ("期末现金余额", "ending_cash_equiv"), ("期初现金余额", "beginning_cash_equiv"),
]


class CustomRuleDialog(QDialog):
    """新增自定义规则的模态对话框。"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("新增自定义规则")
        self.setMinimumWidth(520)
        self.setModal(True)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        form = QFormLayout()
        form.setSpacing(10)

        self._id_input = QLineEdit()
        self._id_input.setPlaceholderText("如 CUST-001 (需唯一)")
        form.addRow("规则编号 *", self._id_input)

        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("如 资产=负债+所有者权益")
        form.addRow("规则名称 *", self._name_input)

        self._category_combo = QComboBox()
        self._category_combo.addItems(_CATEGORIES)
        form.addRow("分类", self._category_combo)

        # 涉及报表 (复选框)
        stmt_row = QHBoxLayout()
        stmt_row.setSpacing(12)
        self._stmt_checks: list[QCheckBox] = []
        for stmt in _STATEMENTS:
            cb = QCheckBox(stmt)
            cb.setChecked(stmt in ("资产负债表", "利润表"))
            self._stmt_checks.append(cb)
            stmt_row.addWidget(cb)
        stmt_row.addStretch()
        form.addRow("涉及报表 *", stmt_row)

        # 公式模板 (降低非专业用户门槛)
        self._template_combo = QComboBox()
        for name, _, _ in _FORMULA_TEMPLATES:
            self._template_combo.addItem(name)
        self._template_combo.currentIndexChanged.connect(self._on_template_selected)
        form.addRow("公式模板", self._template_combo)

        self._formula_input = QPlainTextEdit()
        self._formula_input.setPlaceholderText(
            "从上方模板选择, 或手动输入\n"
            "如 asset_total == liability_total + equity_total"
        )
        self._formula_input.setFixedHeight(70)
        self._formula_input.textChanged.connect(self._update_formula_preview)
        form.addRow("校验公式 *", self._formula_input)

        # 公式中文实时预览 (输入时即时显示含义, 降低理解门槛)
        self._formula_preview = QLabel("")
        self._formula_preview.setObjectName("FormulaPreviewLabel")
        self._formula_preview.setWordWrap(True)
        self._formula_preview.setVisible(False)
        form.addRow("公式含义", self._formula_preview)

        # 可用变量速查 (可折叠)
        self._var_toggle = QPushButton("查看可用变量对照表")
        self._var_toggle.setObjectName("BtnSecondary")
        self._var_toggle.setCheckable(True)
        self._var_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._var_toggle.clicked.connect(self._toggle_var_reference)
        form.addRow("", self._var_toggle)

        self._var_ref = QLabel(self._build_var_reference_text())
        self._var_ref.setObjectName("MetaLabel")
        self._var_ref.setWordWrap(True)
        self._var_ref.setVisible(False)
        form.addRow("", self._var_ref)

        self._tol_type_combo = QComboBox()
        for label, _ in _TOLERANCE_TYPES:
            self._tol_type_combo.addItem(label)
        form.addRow("容差类型", self._tol_type_combo)

        self._tol_input = QLineEdit("0.01")
        form.addRow("容差值", self._tol_input)

        self._sev_combo = QComboBox()
        for label, _ in _SEVERITIES:
            self._sev_combo.addItem(label)
        form.addRow("严重级别", self._sev_combo)

        self._notes_input = QLineEdit()
        self._notes_input.setPlaceholderText("可选备注")
        form.addRow("备注", self._notes_input)

        layout.addLayout(form)

        # 错误提示标签
        self._error_label = QLabel("")
        self._error_label.setObjectName("FormErrorLabel")
        self._error_label.setWordWrap(True)
        self._error_label.setVisible(False)
        layout.addWidget(self._error_label)

        # 按钮行
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("取消")
        cancel_btn.setObjectName("BtnSecondary")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        save_btn = QPushButton("保存")
        save_btn.setObjectName("BtnPrimary")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

    def _on_template_selected(self, index: int) -> None:
        """选择模板后自动填充公式并刷新中文预览。"""
        if index <= 0:
            return  # 第一项是占位提示
        name, formula, _ = _FORMULA_TEMPLATES[index]
        self._formula_input.setPlainText(formula)
        if not self._name_input.text().strip():
            self._name_input.setText(name)
        self._update_formula_preview()

    def _update_formula_preview(self) -> None:
        """根据当前公式实时更新中文含义预览。"""
        from fsa.gui.formula_display import formula_to_chinese
        text = self._formula_input.toPlainText().strip()
        if not text:
            self._formula_preview.setVisible(False)
            return
        self._formula_preview.setText(formula_to_chinese(text))
        self._formula_preview.setVisible(True)

    def _toggle_var_reference(self) -> None:
        """展开/收起变量对照表。"""
        self._var_ref.setVisible(self._var_toggle.isChecked())

    def _build_var_reference_text(self) -> str:
        """构建变量对照表文本 (中文科目 -> 变量名)。"""
        lines = ["常用科目对照 (中文科目 → 公式变量名):"]
        for cn, var in _VARIABLE_REFERENCE:
            lines.append(f"  {cn}  →  {var}")
        lines.append("可用运算符: == (等于)  + - * /  <=  >=  <  >  and  or")
        return "\n".join(lines)

    def _on_save(self) -> None:
        """保存前校验, 通过则 accept。"""
        error = self._validate()
        if error is not None:
            self._error_label.setText(error)
            self._error_label.setVisible(True)
            return
        self._error_label.setVisible(False)
        self.accept()

    def _validate(self) -> str | None:
        """校验表单, 返回中文错误信息或 None。"""
        rule_id = self._id_input.text().strip()
        if not rule_id:
            return "请输入规则编号"
        if any(c in rule_id for c in " \t\n"):
            return "规则编号不能包含空格"

        if not self._name_input.text().strip():
            return "请输入规则名称"

        if not any(cb.isChecked() for cb in self._stmt_checks):
            return "请至少选择一张涉及报表"

        formula = self._formula_input.toPlainText().strip()
        if not formula:
            return "请输入校验公式"
        formula_error = self._validate_formula(formula)
        if formula_error is not None:
            return formula_error

        try:
            tol = float(self._tol_input.text().strip())
            if tol < 0:
                return "容差值不能为负数"
        except ValueError:
            return "容差值必须是数字"

        return None

    def _validate_formula(self, formula: str) -> str | None:
        """用引擎的求值器校验公式可解析性 (语法层面)。

        变量未定义 (NameNotDefined) 属正常 — 运行时才注入数据;
        仅拦截语法错误 (括号不匹配、非法运算符等)。
        等式公式需独立校验左右两侧, 避免一侧 NameNotDefined 掩盖另一侧语法错误。
        """
        try:
            if "==" in formula:
                left, right = ExpressionEvaluator.split_formula(formula)
                for side in (left, right):
                    err = self._check_syntax(side)
                    if err is not None:
                        return err
            else:
                return self._check_syntax(formula, boolean=True)
        except Exception as e:
            return f"公式语法错误: {e}"
        return None

    def _check_syntax(self, expr: str, boolean: bool = False) -> str | None:
        """检查单个表达式语法, 返回错误信息或 None。"""
        try:
            if boolean:
                ExpressionEvaluator.evaluate_boolean(expr, {})
            else:
                ExpressionEvaluator.evaluate(expr, {})
        except Exception as e:
            msg = str(e)
            # 变量未定义 / 求值为 None 属运行期问题, 语法合法
            if "未定义" in msg or "NameNotDefined" in msg or "None" in msg:
                return None
            return f"公式语法错误: {msg}"
        return None

    def build_rule(self) -> ReconciliationRule | None:
        """根据表单构建 ReconciliationRule (仅在 accept 后调用)。"""
        if self._validate() is not None:
            return None
        statements = [
            cb.text() for cb in self._stmt_checks if cb.isChecked()
        ]
        return ReconciliationRule(
            rule_id=self._id_input.text().strip(),
            name=self._name_input.text().strip(),
            category=self._category_combo.currentText(),
            statements=statements,
            formula=self._formula_input.toPlainText().strip(),
            tolerance_type=ToleranceType(
                _TOLERANCE_TYPES[self._tol_type_combo.currentIndex()][1]
            ),
            tolerance=float(self._tol_input.text().strip()),
            severity=Severity(
                _SEVERITIES[self._sev_combo.currentIndex()][1]
            ),
            notes=self._notes_input.text().strip(),
        )
