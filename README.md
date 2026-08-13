# 财务报表勾稽关系自动校验系统

> 离线、开源、CAS 专用、确定性规则驱动的财务报表勾稽校验桌面软件

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![PySide6](https://img.shields.io/badge/GUI-PySide6-green.svg)](https://doc.qt.io/qtforpython-6/)

## 项目简介

一款 Windows 桌面端软件，用于自动校验企业财务报表的科目准确性与勾稽关系平衡性。用户将财务报表（Excel/PDF）导入后，软件自动识别报表类型、提取科目数据、执行勾稽校验，并生成差异报告。

### 解决的问题

目前没有一款"离线、开源、CAS 专用、确定性规则驱动、可审计可溯源、面向非上市中小企业自有 Excel 报表"的 Windows 桌面勾稽校验工具。本项目填补此空位。

## 核心功能

- **数据导入**: 拖拽导入 Excel (.xlsx/.xls)，V1 支持 PDF
- **智能识别**: 自动识别资产负债表/利润表/现金流量表等报表类型
- **科目标准化**: CAS 标准科目字典 + 别名映射，统一不同企业的科目名称
- **勾稽校验**: 37 条 CAS 规则（v1.2.0），覆盖表内平衡/表间勾稽/逻辑合理性
- **差异追溯**: 点击差异查看公式、涉及科目、原始行列定位
- **审计底稿**: 导出带公式的 Excel 审计底稿，可人工复核
- **报表自动生成** (V1.5): 从余额表+序时账自动生成三大报表 + 审计底稿
- **Agent 诊断** (V1): 本地 Ollama LLM 智能诊断差异根因
- **自动更新** (V1.0): 内网发布，启动时检查新版本，一键更新

## 技术栈

| 层 | 技术 | 理由 |
|---|---|---|
| GUI | PySide6 + qfluentwidgets | LGPL免费、原生pandas、Fluent Design现代UI |
| 数据处理 | pandas + openpyxl | 财务数据处理标准 |
| PDF (V1) | Camelot + pdfplumber | MIT兼容、合并单元格/多级表头 |
| 规则引擎 | 自研 AST DSL (simpleeval) | 安全求值、支持算术+容差 |
| 存储 | SQLite (WAL) | 4MB数据量无需服务器 |
| Agent (V1) | Ollama 本地 LLM | 财务数据敏感，必须离线 |

## 快速开始

```bash
# 安装依赖
pip install -e ".[dev]"

# 启动应用
python -m fsa
```

## 文档

- [设计文档](design.md) - 完整调研与设计 (6项任务)
- [项目结构与开发计划](project_structure.md) - 目录结构、模块接口、分阶段计划
- [开发日志](DEV_LOG.md) - 开发过程记录
- [CAS 勾稽规则库](cas_gouji_rule_library.json) - 37 条规则（v1.2.0）

## 开发路线

| 阶段 | 时间 | 目标 |
|---|---|---|
| **MVP** | 6-8 周 | Excel 勾稽校验 + Inno Setup 安装器 |
| **V1.0** | 4-6 周 | PDF + Agent + 自动更新 + 权益变动表 |
| **V1.5** | 4-6 周 | 报表自动生成 (余额表/序时账->三大报表) + 配置完善 |
| **V2.0** | 8-12 周 | ML PDF + 合并报表 + IFRS + 间接法现金流量表 |

## 许可证

MIT License - 见 [LICENSE](LICENSE)

## 贡献

欢迎提交 Issue 和 PR。请阅读 [设计文档](design.md) 了解架构。
