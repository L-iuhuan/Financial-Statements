# 财务报表勾稽校验系统 - 设计语言文档

> 本文档定义系统的视觉设计语言，所有 UI 实现必须遵循此规范。
> 灵感来源: Linear, Stripe Dashboard, Toss Securities, Monzo, Wise, Fluent Design 2

---

## 1. 设计哲学

| 原则 | 含义 |
|---|---|
| **克制的专业感** | 这是一个财务工具，不是消费应用。专业、冷静、值得信赖。不追求花哨，追求清晰。 |
| **数据为王** | 页面上的每个元素都应该服务于数据理解。装饰性元素最小化。 |
| **呼吸感** | 充足的留白让数据可读。拥挤 = 不专业。 |
| **层次分明** | 通过颜色深度、字号大小、间距差异建立清晰的视觉层次，而非靠边框分割。 |
| **深色优先** | 深色模式不是附加功能，而是一等公民。两套配色同步设计。 |

---

## 2. 色彩系统

### 2.1 主色 (Brand)

选用**靛蓝 (Indigo)** 作为品牌主色。理由：比 Windows 默认蓝更深沉、更独特，传达专业与可信，不与系统 UI 混淆。

| Token | Light | Dark | 用途 |
|---|---|---|---|
| `--brand-50` | #eef2ff | #1e1b4b | 悬浮态背景 |
| `--brand-100` | #e0e7ff | #312e81 | 选中态背景 |
| `--brand-200` | #c7d2fe | #3730a3 | 边框/分割线 |
| `--brand-500` | #6366f1 | #818cf8 | 主色 (按钮、链接) |
| `--brand-600` | #4f46e5 | #6366f1 | 主色 hover |
| `--brand-700` | #4338ca | #4f46e5 | 主色 active |

### 2.2 语义色 (Semantic)

**校验状态色** -- 用于规则校验结果：

| Token | Light | Dark | 含义 | 用途 |
|---|---|---|---|---|
| `--success` | #10b981 | #34d399 | 通过 | 校验通过、数据正常 |
| `--success-bg` | #ecfdf5 | #052e1b | 通过背景 | 卡片背景色 |
| `--success-border` | #a7f3d0 | #065f46 | 通过边框 | 卡片左边框 |
| `--error` | #ef4444 | #f87171 | 错误 | 校验不通过 (error 级别) |
| `--error-bg` | #fef2f2 | #450a0a | 错误背景 | 卡片背景色 |
| `--error-border` | #fecaca | #991b1b | 错误边框 | 卡片左边框 |
| `--warning` | #f59e0b | #fbbf24 | 警告 | 校验不通过 (warning 级别) |
| `--warning-bg` | #fffbeb | #422006 | 警告背景 | 卡片背景色 |
| `--warning-border` | #fde68a | #92400e | 警告边框 | 卡片左边框 |
| `--info` | #3b82f6 | #60a5fa | 提示 | 信息提示 (info 级别) |
| `--info-bg` | #eff6ff | #0c1c33 | 提示背景 | 卡片背景色 |

**金额色** -- 用于财务数据展示：

| Token | Light | Dark | 含义 | 说明 |
|---|---|---|---|---|
| `--amount-default` | var(--text-primary) | var(--text-primary) | 正常金额 | 正数用默认色 |
| `--amount-negative` | #ef4444 | #f87171 | 负数 | 负数/亏损用红色 |
| `--amount-highlight` | var(--brand-600) | var(--brand-400) | 高亮金额 | 差额/需关注 |

> **注意**：中国股市习惯"红涨绿跌"，但本系统是校验工具不是行情软件。
> 校验状态用国际通用的"绿=通过, 红=错误"。财务金额中负数用红色（会计惯例）。

### 2.3 中性色 (Neutral)

| Token | Light | Dark | 用途 |
|---|---|---|---|
| `--bg-app` | #f8f9fa | #0a0a0b | 应用背景 |
| `--bg-surface` | #ffffff | #18181b | 卡片/面板背景 |
| `--bg-surface-hover` | #f3f4f6 | #27272a | 悬浮态 |
| `--bg-surface-active` | #e5e7eb | #3f3f46 | 按下态 |
| `--bg-sidebar` | #fafafa | #0f0f10 | 侧边栏 |
| `--bg-acrylic` | rgba(255,255,255,0.72) | rgba(24,24,27,0.72) | 顶栏半透明 |
| `--text-primary` | #111827 | #f9fafb | 主文本 |
| `--text-secondary` | #6b7280 | #9ca3af | 次要文本 |
| `--text-tertiary` | #9ca3af | #6b7280 | 辅助文本 |
| `--text-disabled` | #d1d5db | #4b5563 | 禁用文本 |
| `--border` | #e5e7eb | #27272a | 默认边框 |
| `--border-strong` | #d1d5db | #3f3f46 | 强调边框 |

### 2.4 阴影 (Elevation)

| Token | Light | Dark | 用途 |
|---|---|---|---|
| `--shadow-xs` | 0 1px 2px rgba(0,0,0,0.04) | 0 1px 2px rgba(0,0,0,0.3) | 卡片默认 |
| `--shadow-sm` | 0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04) | 0 1px 3px rgba(0,0,0,0.4) | 卡片悬浮 |
| `--shadow-md` | 0 4px 6px -1px rgba(0,0,0,0.08), 0 2px 4px -2px rgba(0,0,0,0.04) | 0 4px 6px -1px rgba(0,0,0,0.5) | 弹出层 |
| `--shadow-lg` | 0 10px 15px -3px rgba(0,0,0,0.08), 0 4px 6px -4px rgba(0,0,0,0.04) | 0 10px 15px -3px rgba(0,0,0,0.6) | 模态框 |

---

## 3. 字体系统 (Typography)

### 3.1 字体族

| 用途 | 字体栈 | 说明 |
|---|---|---|
| UI 文本 | `"HarmonyOS Sans SC", "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", system-ui, sans-serif` | 中文优先, 英文兼容 |
| 等宽数字 | `"JetBrains Mono", "Cascadia Code", "Consolas", "Courier New", monospace` | 金额/数字对齐 |
| 显示标题 | 同 UI 文本 | 统一字体, 通过字重区分 |

> **选择理由**: HarmonyOS Sans 是华为开源字体, CJK 渲染优秀且免费。
> 系统未安装时回退到 Microsoft YaHei UI (Windows 默认中文字体)。
> 等宽字体用于金额列对齐, JetBrains Mono 免费且数字渲染清晰。

### 3.2 字号阶梯

| Token | Size | Weight | Line Height | Letter Spacing | 用途 |
|---|---|---|---|---|---|
| `--text-xs` | 11px | 400 | 16px | +0.02em | 标签/徽章 |
| `--text-sm` | 12px | 400 | 18px | 0 | 辅助文本 |
| `--text-base` | 13px | 400 | 20px | 0 | 正文 (紧凑) |
| `--text-md` | 14px | 400 | 22px | 0 | 正文 (默认) |
| `--text-lg` | 15px | 500 | 24px | -0.01em | 小标题 |
| `--text-xl` | 18px | 600 | 26px | -0.02em | 区块标题 |
| `--text-2xl` | 22px | 700 | 30px | -0.02em | 页面标题 |
| `--text-3xl` | 28px | 700 | 36px | -0.03em | 数据大数字 |

> **设计选择**: 正文用 13-14px (比常见的 16px 紧凑), 因为财务工具是数据密集型应用。
> 大数字用 28px + 700 字重, 确保摘要卡片中的数字醒目。

### 3.3 数字格式

- 金额: 千分位分隔 `1,285,600.00`
- 负数: 红色 + 负号 `-5,000.00` 或括号 `(5,000.00)`
- 百分比: 保留 2 位小数 `28.57%`
- 零值: 显示 `0.00` 不显示 `-`

---

## 4. 间距系统 (Spacing)

采用 **4px 基准单位**, 8 的倍数为主节奏:

| Token | Value | 用途 |
|---|---|---|
| `--space-0` | 0 | 无间距 |
| `--space-1` | 4px | 最小间距 (图标内边距) |
| `--space-2` | 8px | 紧凑间距 (组件内元素) |
| `--space-3` | 12px | 默认间距 (卡片内边距) |
| `--space-4` | 16px | 标准间距 (区块间距) |
| `--space-5` | 20px | 宽松间距 |
| `--space-6` | 24px | 区块内边距 |
| `--space-8` | 32px | 区块间距 |
| `--space-10` | 40px | 大区块间距 |
| `--space-12` | 48px | 页面级间距 |
| `--space-16` | 64px | 最大间距 (页面边缘) |

### 4.1 组件间距规则

| 组件 | 内边距 | 间距 |
|---|---|---|
| 卡片 | 16px (紧凑) / 24px (默认) | 卡片间 12px |
| 按钮 | 8px 16px (高度 32-36px) | 按钮间 8px |
| 表格单元格 | 8px 12px | 行间 0 (靠分割线) |
| 侧边栏项 | 8px 12px | 项间 2px |
| 页面内容 | 24px (水平) / 20px (垂直) | 区块间 24px |

---

## 5. 圆角系统 (Border Radius)

| Token | Value | 用途 |
|---|---|---|
| `--radius-sm` | 4px | 输入框、小标签 |
| `--radius-md` | 6px | 按钮、下拉菜单 |
| `--radius-lg` | 8px | 卡片、面板 |
| `--radius-xl` | 12px | 模态框、大卡片 |
| `--radius-full` | 9999px | 圆形头像、药丸标签 |

> **设计选择**: 不使用 Monzo 的药丸按钮 (太消费化), 用 6px 圆角的紧凑按钮。
> 卡片 8px, 模态框 12px, 形成由小到大的层次。

---

## 6. 图标系统 (Icons)

### 6.1 图标库

使用 **Lucide Icons** (MIT 许可, https://lucide.dev):
- 线性风格 (outline), 非 filled
- 1.5px 描边宽度
- 24x24 网格设计
- 支持自托管 SVG, 不依赖 CDN

> **选择理由**: Lucide 是 Feather Icons 的社区维护分支, 1500+ 图标, MIT 许可, 
> 风格统一, 线条简洁, 与现代 UI 设计趋势一致。

### 6.2 图标尺寸

| 用途 | Size | 描边 |
|---|---|---|
| 侧边栏导航 | 20px | 1.5px |
| 按钮内图标 | 16px | 1.5px |
| 表格行图标 | 14px | 1.5px |
| 空状态大图标 | 48px | 1px |
| 状态徽章 | 12px | 2px |

### 6.3 核心图标映射

| 功能 | 图标 | Lucide 名称 |
|---|---|---|
| 数据导入 | 上传/拖拽 | `upload`, `file-up` |
| 资产负债表 | 文档 | `file-text` |
| 利润表 | 趋势线 | `trending-up` |
| 现金流量表 | 现金 | `banknote` |
| 校验通过 | 勾选圆 | `check-circle` |
| 校验错误 | X 圆 | `x-circle` |
| 校验警告 | 三角感叹 | `alert-triangle` |
| 校验提示 | 信息圆 | `info` |
| 差额追溯 | 搜索 | `search` |
| 导出底稿 | 下载 | `download` |
| 规则管理 | 规则 | `list-checks` |
| 历史记录 | 时钟 | `history` |
| 系统设置 | 齿轮 | `settings` |

---

## 7. 组件设计规范

### 7.1 卡片 (Card)

```
┌─────────────────────────────────────┐
│  卡片标题                    [操作]  │  ← 16px padding, 18px 字号
│  ─────────────────────────────────  │  ← 分隔线 border-bottom
│                                     │
│    卡片内容                         │  ← 16px padding
│                                     │
└─────────────────────────────────────┘
背景: var(--bg-surface)
圆角: var(--radius-lg) = 8px
阴影: var(--shadow-xs)
边框: 1px solid var(--border)
```

**状态色卡片** (校验结果):
- 左边框 4px 宽, 颜色对应语义色
- 背景色为对应语义色的 `*-bg`
- 不可同时有阴影和彩色背景 (避免视觉过载)

### 7.2 按钮 (Button)

| 类型 | 背景 | 文字 | 边框 | 高度 |
|---|---|---|---|---|
| Primary | var(--brand-600) | white | none | 32px |
| Primary hover | var(--brand-700) | white | none | 32px |
| Secondary | var(--bg-surface) | var(--text-primary) | 1px var(--border) | 32px |
| Secondary hover | var(--bg-surface-hover) | var(--text-primary) | 1px var(--border-strong) | 32px |
| Ghost | transparent | var(--text-secondary) | none | 32px |
| Ghost hover | var(--bg-surface-hover) | var(--text-primary) | none | 32px |

- 圆角: `var(--radius-md)` = 6px
- 内边距: `8px 16px`
- 字号: `var(--text-md)` = 14px
- 字重: 500
- 过渡: `all 0.15s ease`

### 7.3 侧边栏 (Sidebar)

| 属性 | 值 |
|---|---|
| 宽度 | 240px (固定) |
| 背景 | var(--bg-sidebar) |
| 右边框 | 1px solid var(--border) |
| 导航项高度 | 36px |
| 导航项圆角 | var(--radius-sm) = 4px |
| 导航项内边距 | 8px 12px |
| 导航项间距 | 2px |
| 激活态背景 | var(--brand-50) |
| 激活态文字 | var(--brand-700) |
| 激活态指示 | 左侧 3px 实色条 |

### 7.4 数据表格 (Table)

| 属性 | 值 |
|---|---|
| 表头背景 | var(--bg-surface-hover) |
| 表头字重 | 600 |
| 表头字号 | var(--text-sm) = 12px |
| 行高 | 36px |
| 单元格内边距 | 8px 12px |
| 行分隔线 | 1px solid var(--border) |
| 悬浮行背景 | var(--bg-surface-hover) |
| 金额列 | 右对齐, 等宽字体 |
| 金额正数 | var(--text-primary) |
| 金额负数 | var(--error), 括号或负号 |

### 7.5 徽章/标签 (Badge)

| 类型 | 背景 | 文字 | 圆角 |
|---|---|---|---|
| 规则ID | var(--bg-surface-active) | var(--text-secondary) | 4px |
| 错误 | var(--error) | white | 4px |
| 警告 | var(--warning) | #422006 | 4px |
| 通过 | var(--success) | white | 4px |

- 字号: `var(--text-xs)` = 11px
- 字重: 600
- 内边距: `2px 6px`

### 7.6 摘要卡片 (Summary Card)

```
┌──────────────────┐
│  通过             │  ← 12px 标签, var(--text-secondary)
│                  │
│  42              │  ← 28px 700 字重, 语义色
│                  │
│  校验规则         │  ← 12px 标签, var(--text-tertiary)
└──────────────────┘
左边框: 4px 语义色
背景: var(--bg-surface)
```

---

## 8. 动效系统 (Motion)

| Token | Duration | Easing | 用途 |
|---|---|---|---|
| `--transition-fast` | 100ms | ease-out | 按钮状态切换 |
| `--transition-base` | 150ms | ease-out | 默认过渡 |
| `--transition-slow` | 250ms | cubic-bezier(0.4, 0, 0.2, 1) | 面板展开/折叠 |

> **原则**: 动效要快且目的明确。用户是财务人员, 不想等动画。
> 所有动效不超过 250ms。

---

## 9. 深色模式 (Dark Mode)

### 9.1 设计原则

- 深色背景不是纯黑, 是 `#0a0a0b` (带微妙的暖调)
- 卡片背景比应用背景稍亮 `#18181b`
- 文字不是纯白, 是 `#f9fafb` (减少对比疲劳)
- 边框非常微妙 `#27272a` (几乎不可见, 靠间距分割)
- 语义色在深色模式下提亮, 确保可读性

### 9.2 切换机制

```python
# PySide6 实现: 通过 qproperty 动态切换
# 在 QApplication 初始化时读取用户偏好
# 提供三种选项: 浅色 / 深色 / 跟随系统
```

---

## 10. 布局系统 (Layout)

### 10.1 主窗口结构

```
┌────────┬─────────────────────────────────────┐
│        │  顶栏 (48px, 半透明毛玻璃)            │
│ 侧     ├─────────────────────────────────────┤
│ 边     │                                     │
│ 栏     │  内容区 (可滚动)                     │
│ 240px  │                                     │
│        │  padding: 24px                      │
└────────┴─────────────────────────────────────┘
```

### 10.2 内容区栅格

- 最大宽度: 不限 (桌面应用, 全屏使用)
- 卡片网格: `grid-template-columns: repeat(auto-fill, minmax(320px, 1fr))`
- 区块间距: 24px
- 区块内边距: 24px

---

## 11. 设计令牌汇总 (CSS Variables)

以下是完整的 CSS 变量定义, 可直接用于 demo HTML 和 PySide6 QSS:

```css
:root {
  /* === Brand === */
  --brand-50: #eef2ff;
  --brand-100: #e0e7ff;
  --brand-200: #c7d2fe;
  --brand-500: #6366f1;
  --brand-600: #4f46e5;
  --brand-700: #4338ca;

  /* === Semantic === */
  --success: #10b981;
  --success-bg: #ecfdf5;
  --success-border: #a7f3d0;
  --error: #ef4444;
  --error-bg: #fef2f2;
  --error-border: #fecaca;
  --warning: #f59e0b;
  --warning-bg: #fffbeb;
  --warning-border: #fde68a;
  --info: #3b82f6;
  --info-bg: #eff6ff;

  /* === Neutral (Light) === */
  --bg-app: #f8f9fa;
  --bg-surface: #ffffff;
  --bg-surface-hover: #f3f4f6;
  --bg-surface-active: #e5e7eb;
  --bg-sidebar: #fafafa;
  --bg-acrylic: rgba(255,255,255,0.72);
  --text-primary: #111827;
  --text-secondary: #6b7280;
  --text-tertiary: #9ca3af;
  --text-disabled: #d1d5db;
  --border: #e5e7eb;
  --border-strong: #d1d5db;

  /* === Shadow === */
  --shadow-xs: 0 1px 2px rgba(0,0,0,0.04);
  --shadow-sm: 0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);
  --shadow-md: 0 4px 6px -1px rgba(0,0,0,0.08), 0 2px 4px -2px rgba(0,0,0,0.04);
  --shadow-lg: 0 10px 15px -3px rgba(0,0,0,0.08), 0 4px 6px -4px rgba(0,0,0,0.04);

  /* === Spacing === */
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 20px;
  --space-6: 24px;
  --space-8: 32px;
  --space-10: 40px;
  --space-12: 48px;
  --space-16: 64px;

  /* === Radius === */
  --radius-sm: 4px;
  --radius-md: 6px;
  --radius-lg: 8px;
  --radius-xl: 12px;
  --radius-full: 9999px;

  /* === Typography === */
  --font-ui: "HarmonyOS Sans SC", "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", system-ui, sans-serif;
  --font-mono: "JetBrains Mono", "Cascadia Code", "Consolas", monospace;
  --text-xs: 11px;
  --text-sm: 12px;
  --text-base: 13px;
  --text-md: 14px;
  --text-lg: 15px;
  --text-xl: 18px;
  --text-2xl: 22px;
  --text-3xl: 28px;

  /* === Motion === */
  --transition-fast: 100ms ease-out;
  --transition-base: 150ms ease-out;
  --transition-slow: 250ms cubic-bezier(0.4, 0, 0.2, 1);
}

[data-theme="dark"] {
  --brand-50: #1e1b4b;
  --brand-100: #312e81;
  --brand-200: #3730a3;
  --brand-500: #818cf8;
  --brand-600: #6366f1;
  --brand-700: #4f46e5;

  --success: #34d399;
  --success-bg: #052e1b;
  --success-border: #065f46;
  --error: #f87171;
  --error-bg: #450a0a;
  --error-border: #991b1b;
  --warning: #fbbf24;
  --warning-bg: #422006;
  --warning-border: #92400e;
  --info: #60a5fa;
  --info-bg: #0c1c33;

  --bg-app: #0a0a0b;
  --bg-surface: #18181b;
  --bg-surface-hover: #27272a;
  --bg-surface-active: #3f3f46;
  --bg-sidebar: #0f0f10;
  --bg-acrylic: rgba(24,24,27,0.72);
  --text-primary: #f9fafb;
  --text-secondary: #9ca3af;
  --text-tertiary: #6b7280;
  --text-disabled: #4b5563;
  --border: #27272a;
  --border-strong: #3f3f46;

  --shadow-xs: 0 1px 2px rgba(0,0,0,0.3);
  --shadow-sm: 0 1px 3px rgba(0,0,0,0.4);
  --shadow-md: 0 4px 6px -1px rgba(0,0,0,0.5);
  --shadow-lg: 0 10px 15px -3px rgba(0,0,0,0.6);
}
```

---

## 12. 与 PySide6 的映射

| CSS Token | PySide6 QSS |
|---|---|
| `--brand-600: #4f46e5` | `QSS: background-color: #4f46e5;` |
| `--text-md: 14px` | `QSS: font-size: 14px;` |
| `--radius-lg: 8px` | `QSS: border-radius: 8px;` |
| `--shadow-sm` | `QSS: 无原生支持, 需 QGraphicsDropShadowEffect` |
| 深色模式 | `QApplication.setPalette() + QSS 变量` |

> **注意**: PySide6 QSS 不支持 CSS Variables。
> 在 Python 中定义常量字典, 运行时生成 QSS 字符串。
> 深色模式通过切换 QSS 字符串实现, 非通过 CSS 变量。

---

## 13. 参考来源

| 来源 | 借鉴点 |
|---|---|
| Linear.app | 紧凑间距、克制配色、深色优先 |
| Stripe Dashboard | 数据卡片、摘要数字、语义色 |
| Toss Securities | 金融蓝 #3182f6、紧凑控件、Toss Product Sans |
| Monzo | 间距系统 16/24/48/128px、pill 按钮 (我们改为 6px 圆角) |
| Wise | 语义色分离、weight 900 标题 (我们用 700) |
| Financial Times | 色彩语义化 (markets up/down 独立色) |
| Fluent Design 2 | Mica 材质、Acrylic 半透明、窗口圆角 |
| Capital One FS | 变量化设计令牌、2px 描边图标 |
| shadcn/ui | 组件 API 设计、Tailwind 变量映射 |
