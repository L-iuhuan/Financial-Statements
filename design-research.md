# 现代高端软件 UI 设计调研 — 财务报表勾稽校验桌面应用

> 版本: v1.0 | 日期: 2026-08-07
> 目标: 为 PySide6 + qfluentwidgets 的中国财务桌面应用，提炼"高端、现代、专业"的可落地设计规范
> 适用对象: 财务人员（会计/审计），Windows 桌面，数据密集表格 + 校验结果（通过/不通过/差异金额）+ 审计底稿

---

## 0. 调研对象与结论速览

| 产品 | 风格关键词 | 对我们最有价值的点 |
|---|---|---|
| **Linear** | 深色优先、单强调色、克制、工具感 | 中性色阶梯 + 单一强调色的纪律；4px 间距基；表面阶梯代替投影 |
| **Stripe** | 财务、高级、留白、深蓝墨水 | **表格数字用 tabular-nums**；金融数据"密集数据、宽松chrome"的密度哲学 |
| **Raycast** | macOS 原生、表面阶梯、强调色稀缺 | 表面亮度阶梯（6-8 亮度点/级）；强调色 <10% 视图面积 |
| **Notion** | 干净、灵活、暖中性色 | 暖中性色纸感；正文 16px/1.5 行高；3px 极小圆角 |
| **Power BI/Tableau** | 数据可视化、状态色、条件格式 | **状态色 + 第二通道（符号/箭头）**；条件格式数据条 |
| **Windows 11 Fluent 2** | Mica/Acrylic 材质、Segoe UI Variable | **桌面应用的材质与字阶基础**；qfluentwidgets 直接对应 |
| **金蝶/用友** | 商务蓝、白、浅灰 | 中国财务软件的默认基调；红字警示习惯 |

---

## 1. 核心设计策略（最重要的三条）

### 1.1 「克制」是高端感的来源
Linear / Stripe / Raycast / Notion 全部遵循**"单一强调色 + 中性为主"**。真正的高端感来自**表面阶梯 + 细边框 + 留白**，而不是彩色。

> **可落地规则**: 全界面仅 **1 个品牌强调色**。其余全部用中性色（灰/蓝灰）。强调色只用于：主操作按钮、选中态、焦点环、链接。

### 1.2 表面阶梯（Surface Ladder）代替浓投影
Linear / Raycast / Notion 都靠 **2-4 级表面亮度差 + 1px 细边框** 表达层级，而非大投影。

> **可落地规则**: 背景 → 卡片 → 悬浮 → 弹出，每级表面亮度差约 6-8 点。细边框 `1px`。

### 1.3 金融数据必须用「表格数字」(tabular-nums)
Stripe 的精髓：**金额/数字一律启用 `tabular-nums`（等宽数字）**，保证纵向对齐、可快速对比。这是"财务工具感"的关键信号，普通 UI 几乎没人做。

> **可落地规则**: 所有金额列、数字列启用等宽数字特性。qfluentwidgets / Qt 用 `QFont.setStyleHint` 或字体特性。

---

## 2. 色彩体系（含具体 Hex）

### 2.1 品牌强调色（三选一，建议按文化适配）

| 方案 | 强调色 | 适用 | 理由 |
|---|---|---|---|
| **线性靛蓝** (推荐) | `#5E6AD2`（hover `#828FFF`，press `#5E69D1`） | 专业、科技、冷静 | Linear 主色，蓝紫介于"可信"与"现代"之间 |
| 商务蓝 | `#0078D4`（hover `#106EBE`） | Windows 原生、财务主流 | Fluent 默认 / 金蝶用友同基调，用户最熟悉 |
| 金融紫 | `#533AFD`（hover `#665EFD`） | 高端、国际化 | Stripe 主色 |

> **对国内财务用户建议**: 首选**线性靛蓝 `#5E6AD2`** 或其偏蓝变体（如 `#4C6FFF`），既现代又不与"红=赚、绿=亏"冲突。若求最稳妥，用 Fluent `#0078D4`。

### 2.2 中性色（Light 主题 — 建议 MVP 默认）

| 角色 | Hex | 用途 |
|---|---|---|
| 应用背景 | `#F7F8FA` 或 `#F3F4F6` | 主画布（比纯白柔和） |
| 卡片/表面 | `#FFFFFF` | 卡片、面板 |
| 次级表面 | `#F1F3F5` | 分组区、表头背景 |
| 主文字 | `#1A1D21` / `#0F172A` | 标题、正文 |
| 次级文字 | `#5A6472` | 描述、标签 |
| 三级文字 | `#8A93A0` | 占位、辅助信息 |
| 边框 | `#E4E7EB` | 卡片/输入框边线 |
| 边框强调 | `#C8CDD3` | hover 边框 |

### 2.3 中性色（Dark 主题 — 建议 V1 提供）

| 角色 | Hex | 用途 |
|---|---|---|
| 画布 | `#0F1011`（Linear）或 `#1C1C1E`（Raycast） | 主背景（**不用纯黑**） |
| 表面1 | `#141516` | 卡片 |
| 表面2 | `#18191A` | 悬浮 |
| 表面3 | `#1C1C1F` | 弹出 |
| 主文字 | `#F7F8F8` | 标题、正文 |
| 次级文字 | `#D0D6E0` | 描述 |
| 三级文字 | `#8A8F98` | 占位 |
| 边框 | `#2A2E33` | 面板分隔 |

### 2.4 语义色 — ⚠️ 中国财务红绿反转（关键差异化）

**两套语义必须分开设计：**

**(A) 校验状态色**（error/warning/pass/info）— 用西方习惯，因为"校验失败"是错误语义：

| 语义 | Light Hex | 用途 |
|---|---|---|
| 错误 Error | `#D13438`（背景 `#FDECEC`） | 平衡破坏、不通过 |
| 警告 Warning | `#D97706` / `#C89000`（背景 `#FFF7E6`） | 可能有问题 |
| 通过 Pass | `#107C10` / `#16A34A`（背景 `#EFFAF0`） | 校验通过 |
| 信息 Info | `#0078D4`（背景 `#EAF4FF`） | 建议提示 |

**(B) 金额盈亏色** — ⚠️ **必须遵循中国惯例（红涨/红赚、绿跌/绿亏）**：

| 盈亏 | Hex | 说明 |
|---|---|---|
| 盈利/正数 | `#C0392B` / `#D93025`（**红**） | 中国财务：红=赚 |
| 亏损/负数 | `#1E8E3E` / `#0A7D33`（**绿**） | 中国财务：绿=亏 |
| 中性/零 | 主题文字色 | |

> **为何必须区分两套**：校验状态（error=红）与金额盈亏（盈利=红）是**不同维度**。前者是"操作/流程状态"，后者是"财务数值含义"。若混用会造成严重误导——一个"不通过的盈利项"颜色会冲突。建议：**金额列内的数字用盈亏色，规则卡片的状态徽章用校验状态色**，两者物理分离。

> **⚠️ 无障碍强制**：红绿色盲约影响 8% 男性。**盈亏必须同时用第二通道**：`+/-` 符号、上/下箭头 `▲▼`、或括号 `( )` 表示负数。颜色不能是唯一信息通道（Power BI/Tableau 及 colorarchive 指南均强条）。

### 2.5 状态色深色主题适配

| 语义 | Dark Hex |
|---|---|
| 错误 | `#E5484D` |
| 警告 | `#F5A623` / `#FFB020` |
| 通过 | `#4CB782` / `#30A46C` |
| 信息 | `#56A6FF` |

---

## 3. 字体体系（Typography）

### 3.1 中西文字体栈（Windows）

> **关键原则**：桌面应用**优先用系统字体**，不打包 CJK 字体（巨大且慢）。Windows 系统自带 Microsoft YaHei。

```css
/* 中西文混合字体栈 — Windows 桌面 */
font-family:
  "Segoe UI Variable",       /* 拉丁 + 数字（Fluent 2 首选） */
  "Microsoft YaHei UI",      /* 中文字体（Win8.1+） */
  "Microsoft YaHei",         /* 兜底 */
  "Segoe UI",
  sans-serif;

/* 数字/金额专用 — 启用等宽数字 */
font-variant-numeric: tabular-nums;  /* CSS */
```

**Qt/qfluentwidgets 中实现**：
```python
from PySide6.QtGui import QFont
f = QFont("Microsoft YaHei UI")
f.setPointSize(9)  # 见下方字号
# tabular-nums: Qt 通过 setStyleStrategy 或字体特性实现（见备注）
```

**字体栈参考**（微软 Fluent 2 + 阿里 Clarity design 规范）：
```
西文: Segoe UI / Segoe UI Variable
中文: Microsoft YaHei UI (Windows) / PingFang SC (macOS) / Noto Sans CJK SC (Android/开源)
```

> 补充：若想"更高级"的字体，可考虑 **HarmonyOS Sans**（免费、现代）、**MiSans**（小米免费）、**阿里巴巴普惠体 Alibaba PuHuiTi**（免费商用）。但这些需要打包子集字体，MVP 不建议。

### 3.2 字号阶梯（Fluent 2 桌面 + 现代产品折衷）

| 层级 | 字号 | 行高 | 字重 | 用途 |
|---|---|---|---|---|
| 大标题 | 20-24px | 28-32px | 600 | 页面标题、主看板数字 |
| 标题 | 18px | 24px | 600 | 区块标题 |
| 子标题 | 15-16px | 20-24px | 500-600 | 卡片标题、侧边栏项 |
| 正文 | 14px | 20px | 400 | 主要界面文字（桌面密度） |
| 小字 | 13px | 18px | 400 | 元数据、描述 |
| 辅助 | 12px | 16px | 400 | 占位、脚注、徽章 |
| 表格数字 | 13-14px | 20px | 400 (tnum) | 金额、数据单元格 |

> **说明**：Web 产品（Linear/Stripe）正文常用 16px，但**桌面数据密集应用（Fluent/Power BI）用 14px 标准**。财务表格场景 13-14px 合适，兼顾密度与可读性。正文/表格**不建议小于 12px**。

### 3.3 数字与金额显示
- **一律 tabular-nums**（等宽）保证对齐
- 千分位分隔（`1,285,600.00`）
- 保留 2 位小数（分）
- 负数用 `-` 前缀 + 绿色 +（可选）括号
- 货币符号 `¥` 用于总量，明细列可省略

### 3.4 间距（4px 基 + 8px 主流节奏）

| Token | 值 | 用途 |
|---|---|---|
| space-1 | 4px | 图标-文字间隙 |
| space-2 | 8px | 控件内边距、紧凑间隙 |
| space-3 | 12px | 卡片内边距、列表项 |
| space-4 | 16px | 标准间隙 |
| space-5 | 24px | 区块间距、卡片 padding |
| space-6 | 32px | 大区块间距 |
| space-7 | 48px | 页面级留白 |

> 卡片内边距 16-24px；卡片之间 12-16px；主要区块间 24-32px。

### 3.5 圆角（Radius）

| 场景 | 值 | 参考 |
|---|---|---|
| 输入框/按钮 | 6-8px | Linear 6px / Fluent 4px |
| 卡片 | 8-12px | Notion 12px / Linear 12px |
| 弹窗/悬浮面板 | 8-12px | |
| 大容器 | 12-16px | |
| 徽章/标签 | 9999px (胶囊) | |

> **克制原则**：圆角保持在 4-12px 区间，**不要过度圆润**（太圆显"消费级"）。财务工具宜"方中带圆"。

---

## 4. 层级与投影（Elevation）

### 4.1 表面阶梯（推荐）
| 层级 | 表面色(Light) | 边框 | 投影 |
|---|---|---|---|
| 背景 | `#F7F8FA` | - | 无 |
| 卡片 | `#FFFFFF` | `1px #E4E7EB` | 极轻 `0 1px 2px rgba(0,0,0,0.04)` |
| 悬浮 | `#FFFFFF` | `1px #C8CDD3` | `0 4px 12px rgba(0,0,0,0.08)` |
| 弹窗/下拉 | `#FFFFFF` | `1px #C8CDD3` | `0 8px 24px rgba(0,0,0,0.12)` |

### 4.2 投影规范
- 桌面用**柔和、低不透明度**投影（Linear/Stripe 风格）
- 避免浓重/彩色投影
- 卡片 hover 时投影加深 + 边框变深，形成"抬升"反馈

---

## 5. 图标体系

### 5.1 风格选择
| 方案 | 风格 | 适用 |
|---|---|---|
| **Fluent Icons**（推荐） | 线框 1.5-1.75px 描边，圆角端点 | Windows 原生，与 qfluentwidgets 完美契合 |
| Lucide / Feather | 线框 2px，简洁几何 | 通用现代 |
| Segoe Fluent Icons 字体 | 内置系统 | 零依赖 |

> **核心规则**：全应用用**同一套图标集、同一描边粗细（1.5-2px）、同一尺寸网格（16/20/24px）**。严禁混用 emoji 或不同风格。

### 5.2 图标尺寸
- 侧边栏导航：20px
- 顶栏操作：18-20px
- 按钮/徽章：16px
- 大空状态插图：48-64px（可留白）

> **⚠️ 当前 demo 问题**：使用了 emoji（📊✅📋⚙️📁🔧📄📭）。**必须替换为 SVG/字体图标**——emoji 是"非专业"最明显的信号（ui-ux-pro-max 强规则 + 现代产品共识）。

---

## 6. 卡片与表格设计

### 6.1 卡片
- 白底 + `1px` 细边框 + 圆角 8-12px + 极轻投影
- 卡片标题 15px/600 + 元数据 12px 灰色
- 状态徽章（胶囊）区分语义

### 6.2 数据表格（核心，参考 Power BI/Stripe）
| 元素 | 规范 |
|---|---|
| 表头 | 13px / 600，背景 `#F1F3F5`，底部 `1px` 边框 |
| 单元格 | 13-14px / 400，`tabular-nums` |
| 行高 | 36-40px（可配置紧凑 32px） |
| 行分隔 | **细水平线**（`1px #F0F1F3`），不用斑马纹（或极淡斑马纹） |
| hover 行 | 高亮背景 `rgba(94,106,210,0.06)` |
| 选中行 | 强调色淡背景 `rgba(94,106,210,0.10)` |
| 金额列 | 右对齐 + tabular-nums + 千分位 |
| 文本列 | 左对齐 |
| 合计/小计行 | 加粗 + 顶部边框分隔 |
| 差异列 | 盈亏色（红赚/绿亏）+ 符号/箭头 |

### 6.3 校验结果卡片（当前 demo 的规则列表）
建议从"整卡列表"升级为**表格视图**或**紧凑行**：
- 每行：规则ID徽章 | 规则名 | 类别 | 状态徽章 | 差异金额
- 点击展开 → 公式 + 涉及科目追溯表
- 状态用**左侧 4px 色条 + 徽章**，不只靠颜色（无障碍）

---

## 7. 中国财务软件 UI 惯例（金蝶/用友）

### 7.1 色彩基调
- 主流：**商务蓝 + 白 + 浅灰**（简道云/金蝶/用友通用）
- 金融行业偏好：蓝色系（专业、可信、冷静）
- 提供"商务蓝/云白/活力橙"等多主题（金蝶用友），我们至少支持 **Light/Dark 双主题**

### 7.2 红绿惯例（重要）
- **中国股市/财务：红涨绿跌、红赚绿亏**（与西方相反）
- 用友"红字蓝字"：红字=警示/重要，蓝字=链接/提示
- 报表损益表：红=负数/亏损，绿=正数/盈利 —— 注意这与股市"红涨"不完全一致，**但"红=正向/赚钱、绿=负向/亏钱"在财务语境是主流**

> ⚠️ 需在需求确认中向用户明确：**利润/亏损的符号色**用红赚绿亏（贴合财务直觉），且必须配 `+/-` 或箭头第二通道。

### 7.3 财务数据密度
- 财务工具追求"一屏看全"，行高、字号偏向紧凑（14px、行高 36-40px）
- 但**chrome（侧边栏、顶栏、留白）要保持宽松**——"密集数据、宽松 chrome"（Stripe 哲学）

---

## 8. Windows 11 / qfluentwidgets 落地要点

### 8.1 材质（Mica / Acrylic）
- **Mica**: 窗口主背景，半透明跟随桌面，仅用于窗口底座
- **Acrylic**: 瞬态表面（下拉菜单、弹出面板、flyout），不用作大面积背景
- qfluentwidgets 已封装：`AcrylicWindow`、侧边栏可启用 Mica
- ⚠️ **财务数据表格区不用 Acrylic**（影响可读性+GPU），用不透明背景

### 8.2 qfluentwidgets 组件映射
| 需求 | qfluentwidgets 组件 |
|---|---|
| 侧边栏导航 | `NavigationInterface` / `NavigationItemPosition` |
| 数据卡片 | `CardInfoCard`、`HeaderCardWidget` |
| 标签页 | `Pivot` |
| 下拉/弹出 | `DropDownMenu`（Acrylic） |
| 提示/通知 | `InfoBar`（success/warning/error/info） |
| 对话框 | `MessageBox` |
| 表格 | `TableView` + 自定义 QSS，或 `qfluentwidgets.TableWidget` |
| 主题 | `Theme`（Light/Dark/Auto）+ `setThemeColor` |

### 8.3 主题切换
- 支持 `Light / Dark / Auto`（跟随系统）
- **两套完整中性色 token**，语义色各有 dark 变体
- 金额盈亏色在 dark 主题下调亮（见 2.5）

---

## 9. 数据可视化（若 V1+ 需要）

### 9.1 图表类型（Power BI/Tableau 指南）
- **对比 → 柱状图**（人类易比较长度），避免饼图（>8 类禁用）
- 趋势 → 折线图
- 占比 → 饼图仅 <8 类
- 目标达成 → 仪表盘/进度条
- 全部图表**保持同一套配色**、同一坐标尺度约定

### 9.2 图表配色（分类色板 — 需与盈亏色区分）
```
#4E79A7  #F28E2B  #59A14F  #E15759  #B07AA1
#76B7B2  #EDC948  #FF9DA7  #9C755F  #BAB0AC
```
> 分类色板避免与"红/绿"盈亏信号混淆；状态色（error/warning）单独保留。

### 9.3 条件格式（Power BI 模式，适配财务）
- 数据条（Data bars）：单元格内条形图表示大小
- 图标集：箭头 ▲▼ 表示增减
- 色阶：红-黄-绿渐变
- **所有颜色 + 数值/符号双重编码**

---

## 10. 可落地的设计 Token（CSS 变量 / 配置，供直接使用）

### Light 主题 Token
```css
:root {
  /* Brand */
  --accent: #5E6AD2;            /* 线性靛蓝 */
  --accent-hover: #828FFF;
  --accent-press: #5E69D1;
  --on-accent: #FFFFFF;

  /* Neutral */
  --bg-app: #F7F8FA;
  --bg-surface: #FFFFFF;
  --bg-surface-2: #F1F3F5;
  --text-primary: #1A1D21;
  --text-secondary: #5A6472;
  --text-tertiary: #8A93A0;
  --border: #E4E7EB;
  --border-hover: #C8CDD3;

  /* Semantic status */
  --error: #D13438;  --error-bg: #FDECEC;
  --warning: #C89000; --warning-bg: #FFF7E6;
  --pass: #107C10;   --pass-bg: #EFFAF0;
  --info: #0078D4;   --info-bg: #EAF4FF;

  /* Financial P&L (Chinese: red=profit, green=loss) */
  --profit: #D93025;   /* 盈利/正 - 红 */
  --loss: #0A7D33;     /* 亏损/负 - 绿 */

  /* Radius */
  --radius-control: 6px;
  --radius-card: 12px;
  --radius-pill: 9999px;

  /* Spacing (4px base) */
  --space-1: 4px; --space-2: 8px; --space-3: 12px;
  --space-4: 16px; --space-5: 24px; --space-6: 32px;

  /* Elevation */
  --shadow-card: 0 1px 2px rgba(0,0,0,0.04);
  --shadow-hover: 0 4px 12px rgba(0,0,0,0.08);
  --shadow-pop: 0 8px 24px rgba(0,0,0,0.12);

  /* Typography */
  --font: "Segoe UI Variable", "Microsoft YaHei UI", "Microsoft YaHei", sans-serif;
  --font-tabular: "Segoe UI Variable", "Microsoft YaHei UI", sans-serif;
}
```

### Dark 主题 Token（核心覆盖）
```css
.dark {
  --accent: #828FFF;
  --bg-app: #0F1011;
  --bg-surface: #141516;
  --bg-surface-2: #18191A;
  --text-primary: #F7F8F8;
  --text-secondary: #D0D6E0;
  --text-tertiary: #8A8F98;
  --border: #2A2E33;
  --border-hover: #3A3F45;
  --error: #E5484D; --error-bg: rgba(229,72,77,0.12);
  --warning: #FFB020; --warning-bg: rgba(255,176,32,0.12);
  --pass: #4CB782; --pass-bg: rgba(76,183,130,0.12);
  --info: #56A6FF; --info-bg: rgba(86,166,255,0.12);
  --profit: #FF6B6B;  /* 红赚（调亮） */
  --loss: #30A46C;    /* 绿亏（调亮） */
  --border: #2A2E33;
}
```

---

## 11. 当前 demo 的差距清单（直接可改）

| 现状 | 问题 | 改进 |
|---|---|---|
| emoji 图标 📊✅📄 | 不专业 | 换 Fluent/Lucide 线性 SVG 图标 |
| 字号偏小/层级平 | 缺乏层次 | 用 12-24px 字阶，标题 600 |
| 语义色用西方红=error | 金额盈亏未区分 | 增加金额列 `--profit/--loss`（红赚绿亏）+ 符号 |
| 圆角 8px 单一 | 无层级 | control 6px / card 12px |
| 无等宽数字 | 金额不对齐 | 金额启用 tabular-nums |
| 投影较浓 | 显旧 | 改柔和低不透明度投影 |
| 只 light | 无 dark | 提供 Light/Dark/Auto 双主题 |
| 无金额符号第二通道 | 无障碍缺陷 | 负数加 `-` / 括号 / 箭头 |
| 配色单调 | 无强调色纪律 | 单强调色 `#5E6AD2`，其余中性 |

---

## 12. 参考来源

- Fluent 2 Design System: https://fluent2.microsoft.design/typography
- Windows Mica/Acrylic: https://learn.microsoft.com/en-us/windows/apps/design/signature-experiences/materials
- Linear Design Tokens: designmd.cc/benchmarks/linear · shadcn.io/design/linear · designsystems.one/design-systems/linear
- Stripe Design Tokens: designmd.cc/benchmarks/stripe · docs.stripe.com/stripe-apps/style
- Raycast Design System: shadcn.io/design/raycast · seedflip.co/blog/raycast-design-system-dark-ui
- Notion Design System: designmd.cc/benchmarks/notion · duply.ai/notion/design-md
- Power BI 表可视化/主题: learn.microsoft.com/power-bi · Tableau Visual Best Practices
- 金蝶/用友财务软件配色: chanjet.com · jiandaoyun.com
- 中国股市红涨绿跌 & 财务红字: BBC/中国日报/PMC 研究 · colorarchive.org/guides/financial-ui-color-guide
- CJK 字体: Microsoft Learn 国际字体 · Clarity(阿里)design · Noto Sans CJK
