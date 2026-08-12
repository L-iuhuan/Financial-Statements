"""验证 Ollama 增强诊断: 构建假失败结果, 分别运行回退路径和 LLM 路径。

用法: python scripts/verify_ollama.py
"""

from __future__ import annotations

import io
import json
import sys
from unittest.mock import MagicMock, patch

from fsa.agent.diagnosis import DiagnosisEngine
from fsa.agent.ollama_client import OllamaClient
from fsa.core.models.result import TraceItem, ValidationResult
from fsa.core.models.rule import Severity


def _make_result() -> ValidationResult:
    """创建测试用的失败 ValidationResult（BS-BAL-001, 差额 10,000）。"""
    return ValidationResult(
        rule_id="BS-BAL-001",
        rule_name="资产=负债+所有者权益",
        passed=False,
        severity=Severity.ERROR,
        left_value=1000000.0,
        right_value=990000.0,
        diff=10000.0,
        tolerance=0.01,
        formula="asset_total == liability_total + equity_total",
        message="差额超出容差",
        category="A-表内平衡",
        trace=[
            TraceItem(
                key="asset_total", name="资产总计", amount=1000000.0,
                row=35, column="期末余额", side="left",
            ),
            TraceItem(
                key="liability_total", name="负债合计", amount=600000.0,
                row=20, column="期末余额", side="right",
            ),
            TraceItem(
                key="equity_total", name="所有者权益合计", amount=390000.0,
                row=30, column="期末余额", side="right",
            ),
        ],
    )


def main() -> None:
    # Windows 控制台默认 GBK, 强制 UTF-8
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

    result = _make_result()
    engine = DiagnosisEngine()

    # ── 路径 1: 无 Ollama 客户端（回退到规则化诊断）──
    print("=" * 60)
    print("路径 1: 无 Ollama 客户端（规则化回退）")
    print("=" * 60)
    diagnosis_fallback = engine.diagnose_with_llm(result, client=None)
    diagnosis_rule = engine.diagnose(result)
    assert diagnosis_fallback == diagnosis_rule, (
        "无客户端时 diagnose_with_llm 应与 diagnose 输出一致"
    )
    print(diagnosis_fallback)
    print()
    print("✅ 回退路径验证通过: 输出与规则化诊断一致。")

    # ── 路径 2: 模拟 Ollama 可用（LLM 路径）──
    print()
    print("=" * 60)
    print("路径 2: 模拟 Ollama 可用（LLM 诊断）")
    print("=" * 60)
    llm_text = (
        "经分析，资产总计（1,000,000.00元）与负债合计（600,000.00元）"
        "加所有者权益合计（390,000.00元）之和不符，差额为10,000.00元。\n\n"
        "可能原因：\n"
        "1. 所有者权益类科目取数不完整，可能遗漏了未分配利润或资本公积的变动。\n"
        "2. 负债类科目漏记了10,000元的短期借款或应付账款。\n"
        "3. 资产类科目可能存在重复计算。\n\n"
        "建议：逐一核对资产负债表各科目明细账，确认期末余额是否正确。"
    )

    # 模拟 Ollama 响应
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=False)
    mock_response.read.return_value = json.dumps(
        {"response": llm_text}
    ).encode("utf-8")

    with patch("fsa.agent.ollama_client.urlopen", return_value=mock_response):
        mock_client = OllamaClient()
        # 模拟 is_available 返回 True
        with patch.object(mock_client, "is_available", return_value=True):
            diagnosis_llm = engine.diagnose_with_llm(
                result, client=mock_client
            )

    print(diagnosis_llm)
    print()
    assert diagnosis_llm == llm_text, "LLM 路径应返回模型生成的文本"
    assert "10,000" in diagnosis_llm or "10000" in diagnosis_llm.replace(",", ""), (
        "LLM 诊断应包含差额信息"
    )
    print("✅ LLM 路径验证通过: 返回了模拟的 LLM 诊断文本。")

    # ── 总结 ──
    print()
    print("=" * 60)
    print("验证总结")
    print("=" * 60)
    print("✅ 回退路径: 无 Ollama 时回到规则化诊断（确定性）")
    print("✅ LLM 路径: Ollama 可用时使用 LLM 增强诊断")
    print("✅ 所有路径均无异常，Ollama 增强诊断功能正常。")
    print()
    print("注意: 实际环境中 Ollama 服务未安装，应用将自动使用规则化诊断。")
    print("      安装 Ollama 并拉取模型后，系统将自动切换为 LLM 增强诊断。")


if __name__ == "__main__":
    main()