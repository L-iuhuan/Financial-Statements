"""AI 抽屉消息与建议气泡渲染 (mixin)。

由 AgentDrawer 继承, 与 AgentSessionMixin 共同组成完整抽屉。

职责:
- 消息气泡渲染: AI 气泡用 QTextBrowser 渲染 Markdown 子集 (模块级 md_to_html),
  支持右键"复制全文"菜单, 高度自适应。
- 流式消息气泡: append_stream_chunk 仅累积 raw_text, QTimer(100ms) 节流渲染。
- 可折叠"思考过程"区: 标题按钮 + 完整文本 QLabel, 收尾自动折叠。
- 黏底滚动状态机 + "回到底部"悬浮按钮。
- 欢迎空态: 无消息时的居中引导 (标题/说明/建议按钮/免责小字)。
- refresh_theme(): 主题切换后重刷已渲染 AI 气泡 (含流式中), 接线由宿主负责。

依赖宿主 AgentDrawer 提供的属性 (均在 __init__/_setup_ui 中初始化):
_scroll / _messages_layout / _suggestions_layout / _suggestions_frame /
_last_bubble / _last_user_bubble / send_requested。
"""

from __future__ import annotations

import html
import re
from datetime import datetime
from typing import Protocol

from PySide6.QtCore import QEvent, QObject, Qt, QTimer, Signal
from PySide6.QtGui import QContextMenuEvent, QTextOption
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)
from shiboken6 import isValid

from fsa.gui.theme import current_palette

_SUGGESTIONS: list[str] = [
    "什么是勾稽关系",
    "BS-BAL-001 规则",
    "差额超容差怎么办",
]

# 行内标记: `code` 或 [文本](url) 优先提取 (占位后处理, 防止内部被粗斜体改写)
_INLINE_CODE_OR_LINK = re.compile(r"(`[^`]*`|\[[^\]]*\]\([^)]*\))")
_TABLE_SEP_CELL = re.compile(r":?-+:?")


def _split_fenced(text: str) -> list[tuple[bool, str]]:
    """按 ``` 围栏切分为 [(is_code, content), ...] 段。"""
    lines = text.split("\n")
    segments: list[tuple[bool, str]] = []
    buf: list[str] = []
    in_code = False
    for line in lines:
        if line.strip().startswith("```"):
            if in_code:
                segments.append((True, "\n".join(buf)))
                buf = []
                in_code = False
            else:
                segments.append((False, "\n".join(buf)))
                buf = []
                in_code = True
        else:
            buf.append(line)
    segments.append((bool(in_code), "\n".join(buf)))
    return segments


def _is_table_separator(line: str) -> bool:
    """判断是否为表格分隔行 (|---|---|)。"""
    inner = line.strip()
    if not (inner.startswith("|") and inner.endswith("|")):
        return False
    cells = [c.strip() for c in inner.strip("|").split("|")]
    return bool(cells) and all(_TABLE_SEP_CELL.fullmatch(c) for c in cells)


def _markdown_css() -> dict[str, str]:
    """当前主题的 Markdown 渲染配色 (渲染时从 theme.current_palette 取)。"""
    p = current_palette()
    return {
        "text": p.get("text_primary", "#111827"),
        "muted": p.get("text_secondary", "#6b7280"),
        "code_bg": p.get("bg_surface_hover", "#f3f4f6"),
        "pre_bg": p.get("bg_app", "#f8f9fa"),
        "border": p.get("border", "#e5e7eb"),
    }


def _inline(escaped: str, css: dict[str, str]) -> str:
    """行内标记替换 (入参须已 html.escape)。

    支持: `code` -> <code>, [文本](url) -> 仅文本, **粗** -> <strong>,
    *斜* -> <em>。code/链接内容先占位, 避免被粗斜体规则二次改写。
    """
    placeholders: dict[str, str] = {}

    def store(token: str) -> str:
        key = f"\x00{len(placeholders)}\x00"
        placeholders[key] = token
        return key

    def repl(m: re.Match[str]) -> str:
        token = m.group(0)
        if token.startswith("`") and token.endswith("`"):
            inner = token[1:-1]
            return store(
                f'<code style="background-color:{css["code_bg"]};'
                f'border:1px solid {css["border"]};border-radius:3px;'
                f'padding:0 3px;font-family:Consolas,monospace;font-size:12px;">'
                f"{inner}</code>"
            )
        lm = re.match(r"\[([^\]]*)\]\([^)]*\)", token)
        if lm:
            return store(lm.group(1))
        return token

    s = _INLINE_CODE_OR_LINK.sub(repl, escaped)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", s)
    for key, value in placeholders.items():
        s = s.replace(key, value)
    return s


def _parse_blocks(content: str, css: dict[str, str]) -> str:
    """非代码段逐行状态机: 表格/标题/列表/段落。"""
    out: list[str] = []
    para: list[str] = []
    list_kind: str | None = None
    list_items: list[str] = []
    table: list[list[str]] | None = None

    def flush_para() -> None:
        nonlocal para
        if para:
            out.append("<p>" + "<br/>".join(_inline(p, css) for p in para) + "</p>")
            para = []

    def flush_list() -> None:
        nonlocal list_kind, list_items
        if list_kind:
            tag = "ul" if list_kind == "ul" else "ol"
            out.append(f"<{tag} style=\"margin:4px 0;\">")
            for item in list_items:
                out.append(f'<li style="margin:3px 0;">{_inline(item, css)}</li>')
            out.append(f"</{tag}>")
            list_kind = None
            list_items = []

    def flush_table() -> None:
        nonlocal table
        if table:
            out.append('<table style="border-collapse:collapse;width:100%;margin:4px 0;">')
            for ri, row in enumerate(table):
                tag = "th" if ri == 0 else "td"
                style = (
                    f'border:1px solid {css["border"]};padding:4px 8px;'
                    "font-size:12px;text-align:left;"
                )
                if ri == 0:
                    style += f'font-weight:600;background-color:{css["code_bg"]};'
                cells = "".join(
                    f'<{tag} style="{style}">{_inline(c, css)}</{tag}>' for c in row
                )
                out.append(f"<tr>{cells}</tr>")
            out.append("</table>")
            table = None

    for raw in content.split("\n"):
        s = raw.strip()
        if not s:
            flush_para()
            flush_list()
            flush_table()
            continue
        if s.startswith("|") and s.endswith("|"):
            if _is_table_separator(s):
                continue
            flush_para()
            flush_list()
            cells = [c.strip() for c in s.strip("|").split("|")]
            if table is None:
                table = []
            table.append(cells)
            continue
        flush_table()
        m = re.match(r"^(#{1,3})\s+(.*)$", s)
        if m:
            flush_para()
            flush_list()
            level = len(m.group(1))
            tag = "h3" if level <= 1 else "h4"
            size = "15px" if tag == "h3" else "14px"
            out.append(
                f'<{tag} style="margin:8px 0 4px;font-size:{size};font-weight:600;">'
                f"{_inline(html.escape(m.group(2)), css)}</{tag}>"
            )
            continue
        m = re.match(r"^([-*])\s+(.*)$", s) or re.match(r"^(\d+)\.\s+(.*)$", s)
        if m:
            kind = "ul" if m.group(1) in ("-", "*") else "ol"
            item = html.escape(m.group(2))
            flush_para()
            flush_table()
            if list_kind is None:
                list_kind = kind
                list_items = [item]
            elif list_kind != kind:
                flush_list()
                list_kind = kind
                list_items = [item]
            else:
                list_items.append(item)
            continue
        flush_list()
        para.append(html.escape(s))
    flush_para()
    flush_list()
    flush_table()
    return "".join(out)


def md_to_html(text: str) -> str:
    """将 Markdown 子集渲染为带主题内联 CSS 的 HTML (供 QTextBrowser 使用)。

    支持语法:
    - ``` 围栏代码块 -> <pre> (等宽/弱背景/圆角/padding, 原文 html.escape)
    - |a|b| 表格行 (分隔行跳过) -> <table> (细边框, 首行表头加粗)
    - #/##/### 标题 -> <h3>/<h4>
    - -/* 无序列表, 1. 有序列表 -> <ul>/<ol>
    - 空行段落分隔, 其余 -> <p>
    - 行内: **粗** -> <strong>, *斜* -> <em>, `code` -> <code>,
      [文本](url) -> 仅保留文本
    - 所有原文内容先 html.escape 再注入标签 (XSS 安全)
    """
    css = _markdown_css()
    body: list[str] = []
    for is_code, content in _split_fenced(text):
        if is_code:
            body.append(
                "<pre style=\"font-family:'JetBrains Mono','Cascadia Code',"
                f"Consolas,monospace;background-color:{css['pre_bg']};"
                f"color:{css['text']};border:1px solid {css['border']};"
                "border-radius:6px;padding:8px 10px;white-space:pre-wrap;"
                f'margin:4px 0;font-size:12px;">{html.escape(content)}</pre>'
            )
        else:
            body.append(_parse_blocks(content, css))
    return (
        f'<div style="font-size:13px;line-height:1.55;color:{css["text"]};'
        f'word-wrap:break-word;">{"".join(body)}</div>'
    )


class _AssistantBubble(QTextBrowser):
    """AI 气泡: 渲染 Markdown, 高度自适应, 保留选中 + "复制全文"右键菜单。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._raw = ""
        self.setOpenExternalLinks(False)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        # 模拟气泡内边距 (QSS padding 对 QTextBrowser 不生效)
        self.document().setDocumentMargin(10)
        # 高度自适应: 文档重排(宽度变化/内容变化)后按实际高度撑开, 不留大空白
        self.document().documentLayout().documentSizeChanged.connect(
            self._resize_to_content
        )
        self._resize_to_content()

    def set_markdown(self, text: str) -> None:
        self._raw = text
        self.setHtml(md_to_html(text))
        self._resize_to_content()

    def raw_text(self) -> str:
        return self._raw

    def text(self) -> str:
        """兼容 QLabel 语义: 返回纯文本 (宿主 main_window_agent 用 bubble.text())。"""
        return self.toPlainText()

    def refresh(self) -> None:
        """主题切换后按当前主题重渲染。"""
        self.setHtml(md_to_html(self._raw))
        self._resize_to_content()

    def _resize_to_content(self, *_: object) -> None:
        height = self.document().documentLayout().documentSize().height()
        self.setFixedHeight(int(height) + 16)

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        menu = self.createStandardContextMenu()
        menu.addSeparator()
        action = menu.addAction("复制全文")
        action.triggered.connect(
            lambda: QApplication.clipboard().setText(self._raw)
        )
        menu.exec(event.globalPos())


class _StickButtonHost(Protocol):
    """_StickPositionFilter 的宿主契约: 提供回到底部按钮与定位方法。"""

    _stick_button: QPushButton

    def _position_stick_button(self) -> None: ...


class _StickPositionFilter(QObject):
    """视口 resize 时重新定位"回到底部"按钮 (右下角悬浮)。"""

    def __init__(self, owner: _StickButtonHost) -> None:
        super().__init__()
        self._owner = owner

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.Resize:
            btn = getattr(self._owner, "_stick_button", None)
            if btn is not None:
                self._owner._position_stick_button()
        return False


class _AgentDrawerContracts:
    """跨 mixin 方法契约 (仅类型声明, 运行时由实现方提供)。

    该基类位于 MRO 末端, 不参与实际调用; 仅用于让两个 mixin 在
    相互引用对方方法时通过 mypy strict 类型检查。
    """

    def _persist_message(self, role: str, content: str) -> None:
        """由 AgentSessionMixin 提供: 消息持久化。"""
        raise NotImplementedError

    def _rebuild_messages(self, messages: list[dict[str, object]]) -> None:
        """由 AgentMessageMixin 提供: 重建消息区。"""
        raise NotImplementedError


class StreamMessageHandle:
    """流式消息句柄: 持有气泡与思考区引用, 供逐块追加文本。

    由 AgentMessageMixin.start_stream_message() 创建, 经
    append_stream_chunk / append_stream_reasoning / finish_stream_message 使用。
    """

    def __init__(
        self,
        layout: QVBoxLayout,
        bubble: _AssistantBubble,
        time_label: QLabel,
    ) -> None:
        self.layout = layout
        self.bubble = bubble
        self.time_label = time_label
        self.reasoning_label: QLabel | None = None
        self.reasoning_text = ""
        # 新增字段 (可加不可删)
        self.raw_text = ""
        self.reasoning_toggle: QPushButton | None = None
        self.reasoning_box: QVBoxLayout | None = None


class AgentMessageMixin(QFrame, _AgentDrawerContracts):
    """消息气泡与建议气泡的渲染/发送逻辑 (继承 QFrame 以便访问 QWidget 方法)。"""

    send_requested: Signal

    _scroll: QScrollArea
    _messages_layout: QVBoxLayout
    _suggestions_layout: QGridLayout
    _suggestions_frame: QFrame
    _last_bubble: QLabel | _AssistantBubble
    _last_user_bubble: QLabel | _AssistantBubble

    # 流式节流渲染
    _streaming_handle: StreamMessageHandle | None
    _stream_dirty: bool
    _stream_timer: QTimer | None

    # 黏底滚动状态机
    _stick_bottom: bool
    _stick_button: QPushButton

    def _build_messages(self) -> QScrollArea:
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._stick_bottom = True
        self._ai_bubbles: list[_AssistantBubble] = []
        self._user_bubbles: list[QLabel] = []
        self._welcome_items: list[tuple[QLabel, str]] = []
        self._streaming_handle = None
        self._stream_dirty = False
        self._stream_timer = None
        self._rebuild_messages([])
        # 黏底滚动: 用户拖动滚动条离开底部时翻转为非黏底
        bar = self._scroll.verticalScrollBar()
        bar.valueChanged.connect(self._on_scroll_value_changed)
        bar.sliderMoved.connect(self._on_scroll_value_changed)
        # 内容高度变化(新增消息)后, 若处于黏底则保持滚到底部 (修复新消息断流)
        bar.rangeChanged.connect(self._on_scroll_range_changed)
        self._stick_button = self._build_stick_button()
        return self._scroll

    def _rebuild_messages(self, messages: list[dict[str, object]]) -> None:
        """重建消息区域 (初始化/切换会话时调用)。"""
        old = self._scroll.widget()
        if old is not None:
            # 先隐藏再删除, 避免脱离 scroll 视口后闪现为独立窗口
            old.hide()
            old.deleteLater()

        container = QWidget()
        self._messages_layout = QVBoxLayout(container)
        self._messages_layout.setContentsMargins(16, 12, 16, 12)
        self._messages_layout.setSpacing(8)

        self._ai_bubbles = []
        self._user_bubbles = []
        self._welcome_items = []
        self._streaming_handle = None
        self._stream_dirty = False
        self._stick_bottom = True

        if not messages:
            self._build_welcome()
        else:
            for msg in messages:
                self._add_message(
                    str(msg["role"]),
                    str(msg["content"]),
                    str(msg.get("created_at", "")),
                )

        self._messages_layout.addStretch()
        self._scroll.setWidget(container)
        btn = getattr(self, "_stick_button", None)
        if btn is not None:
            btn.hide()

    def _build_welcome(self) -> None:
        """无消息时的欢迎空态 (居中 QVBoxLayout, 含免责小字)。"""
        self._welcome_items = []

        title = QLabel("AI 诊断助手")
        title.setObjectName("AgentWelcomeTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._style_welcome_label(title, "title")
        self._welcome_items.append((title, "title"))

        desc = QLabel("针对校验差异做根因分析，解答勾稽与 CAS 准则问题")
        desc.setObjectName("AgentWelcomeDesc")
        desc.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        desc.setWordWrap(True)
        self._style_welcome_label(desc, "desc")
        self._welcome_items.append((desc, "desc"))

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        btn_row.addStretch()
        for text in _SUGGESTIONS:
            btn = QPushButton(text)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setObjectName("AgentSuggestion")
            btn.setMinimumHeight(26)
            btn.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
            btn.clicked.connect(lambda checked=False, t=text: self._quick_ask(t))
            btn_row.addWidget(btn)
        btn_row.addStretch()

        disclaim = QLabel("AI 输出仅供参考 · 不构成审计意见")
        disclaim.setObjectName("AgentWelcomeDisclaimer")
        disclaim.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._style_welcome_label(disclaim, "disclaim")
        self._welcome_items.append((disclaim, "disclaim"))

        welcome = QVBoxLayout()
        welcome.setSpacing(10)
        welcome.addStretch()
        welcome.addWidget(title)
        welcome.addWidget(desc)
        welcome.addSpacing(6)
        welcome.addLayout(btn_row)
        welcome.addSpacing(6)
        welcome.addWidget(disclaim)
        welcome.addStretch()

        self._messages_layout.addStretch()
        self._messages_layout.addLayout(welcome)
        self._messages_layout.addStretch()

    def _style_welcome_label(self, label: QLabel, role: str) -> None:
        """欢迎空态标签配色 (随主题)。"""
        p = current_palette()
        if role == "title":
            color = p.get("text_primary", "#111827")
            label.setStyleSheet(f"font-size: 15px; font-weight: 600; color: {color};")
        elif role == "desc":
            color = p.get("text_secondary", "#6b7280")
            label.setStyleSheet(f"font-size: 12px; color: {color};")
        else:
            color = p.get("text_tertiary", "#9ca3af")
            label.setStyleSheet(f"font-size: 10px; color: {color};")

    def _build_suggestions(self) -> QFrame:
        self._suggestions_frame = QFrame()
        # 2 列网格: 窄窗 (280px) 下 3 个 chip 不横排截断
        self._suggestions_layout = QGridLayout(self._suggestions_frame)
        self._suggestions_layout.setContentsMargins(16, 0, 16, 8)
        self._suggestions_layout.setHorizontalSpacing(6)
        self._suggestions_layout.setVerticalSpacing(6)
        self._render_suggestions(_SUGGESTIONS)
        return self._suggestions_frame

    def _render_suggestions(self, suggestions: list[str]) -> None:
        """渲染建议气泡 (清空旧的并重建; QGridLayout 2 列, 每行最多 2 个)。

        第三个起换行占第一列; chip 横向 Minimum 自适应宽度, 文本不截断;
        单 chip 文本本身超宽时 tooltip 兜底展示完整文本。
        """
        # 清空旧气泡
        while self._suggestions_layout.count():
            item = self._suggestions_layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()

        for i, text in enumerate(suggestions):
            btn = QPushButton(text)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setObjectName("AgentSuggestion")
            # 按内容自适应宽度, 避免文字截断; 设置最小高度保证可点
            btn.setMinimumHeight(26)
            btn.setSizePolicy(
                QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed
            )
            btn.setToolTip(text)
            btn.clicked.connect(
                lambda checked=False, t=text: self._quick_ask(t)
            )
            self._suggestions_layout.addWidget(btn, i // 2, i % 2)
        # 两列均分可用宽度, 窄窗下各行 chip 左右对齐
        self._suggestions_layout.setColumnStretch(0, 1)
        self._suggestions_layout.setColumnStretch(1, 1)

    def set_suggestions(self, suggestions: list[str]) -> None:
        """动态更新建议气泡内容 (根据上下文智能推荐)。"""
        if not hasattr(self, "_suggestions_layout"):
            return
        self._render_suggestions(suggestions)

    def _add_message(
        self, role: str, text: str, time_str: str = ""
    ) -> None:
        """添加一条消息 (气泡 + 时间戳)。"""
        if not time_str:
            time_str = datetime.now().strftime("%H:%M")
        elif " " in time_str:
            time_str = time_str.split(" ")[1][:5]

        is_user = role == "user"
        sender = "您" if is_user else "AI 助手"

        bubble: QLabel | _AssistantBubble
        if is_user:
            bubble = QLabel(text)
            bubble.setWordWrap(True)
            bubble.setObjectName("AgentBubbleUser")
            # 用户气泡宽度按消息区视口百分比 (72%), 上限 400px, 下限 220px
            bubble.setMaximumWidth(self._bubble_max_width(0.72, 400))
            self._user_bubbles.append(bubble)
        else:
            bubble = _AssistantBubble()
            bubble.setObjectName("AgentBubbleAssistant")
            bubble.setMaximumWidth(self._bubble_max_width(0.88, 460))
            bubble.set_markdown(text)
            self._style_assistant_bubble(bubble)
            self._ai_bubbles.append(bubble)

        time_label = QLabel(f"{sender} · {time_str}")
        time_label.setObjectName("AgentTimeLabel")

        bubble_row = QHBoxLayout()
        if is_user:
            bubble_row.addStretch()
            bubble_row.addWidget(bubble)
        else:
            bubble_row.addWidget(bubble)
            bubble_row.addStretch()

        time_row = QHBoxLayout()
        if is_user:
            time_row.addStretch()
            time_row.addWidget(time_label)
        else:
            time_row.addWidget(time_label)
            time_row.addStretch()

        msg_layout = QVBoxLayout()
        msg_layout.setSpacing(2)
        msg_layout.setContentsMargins(0, 0, 0, 0)
        msg_layout.addLayout(bubble_row)
        msg_layout.addLayout(time_row)

        self._messages_layout.insertLayout(
            self._messages_layout.count() - 1, msg_layout
        )

        # 记录最新消息 widget, 用于自动滚动
        self._last_bubble = bubble
        if is_user:
            self._last_user_bubble = bubble
            # 用户发新消息 = 想看新回复: 恢复黏底、隐藏按钮并滚到底。
            # (add_user_message 走 _add_message, 同样生效)
            self._stick_bottom = True
            btn = getattr(self, "_stick_button", None)
            if btn is not None:
                btn.hide()
            self._scroll_to_bottom()
        elif self._stick_bottom:
            self._scroll_to_bottom()

    def relayout_bubbles(self) -> None:
        """抽屉宽度变化后重算所有气泡的最大宽度 (内容跟随容器调整)。"""
        for ai_bubble in self._ai_bubbles:
            ai_bubble.setMinimumWidth(0)
            ai_bubble.setMaximumWidth(self._bubble_max_width(0.88, 460))
        for user_bubble in self._user_bubbles:
            user_bubble.setMinimumWidth(0)
            user_bubble.setMaximumWidth(self._bubble_max_width(0.72, 400))
        handle = getattr(self, "_streaming_handle", None)
        if handle is not None:
            handle.bubble.setMinimumWidth(0)
            handle.bubble.setMaximumWidth(self._bubble_max_width(0.88, 460))

    def _bubble_max_width(self, pct: float, cap: int) -> int:
        """按消息区视口宽度计算气泡最大宽度。

        百分比 + 绝对上限 (避免宽抽屉下长行过长, 用户 400px / AI 460px),
        并受“视口宽度 - 左右 16px 边距”约束, 保证窄抽屉下不溢出容器。
        新消息按最新视口取宽; 抽屉拖宽/拖窄时由
        relayout_bubbles 统一重算存量气泡。
        """
        vp = getattr(self, "_scroll", None)
        width = vp.viewport().width() if vp is not None else self.width()
        available = max(120, width - 32)
        return max(120, min(int(width * pct), cap, available))

    def _quick_ask(self, question: str) -> None:
        """点击建议气泡直接发送 (防抖: 避免快速双击产生重复消息)。"""
        if self._is_send_locked():
            return
        self._add_message("user", question)
        self._persist_message("user", question)
        self.send_requested.emit(question)

    def _is_send_locked(self) -> bool:
        """建议气泡防抖: 500ms 内的重复点击被忽略 (仅用于 _quick_ask)。

        Returns:
            True 表示处于锁定期 (应忽略本次点击)
        """
        import time

        now = time.monotonic()
        last = getattr(self, "_last_send_time", 0.0)
        if now - last < 0.5:
            return True
        self._last_send_time = now
        return False


    # ── 黏底滚动 ──

    def _build_stick_button(self) -> QPushButton:
        """\"回到底部\"按钮 (悬浮于滚动区视口右下角)。"""
        btn = QPushButton("↓ 回到底部")
        btn.setObjectName("AgentStickButton")
        btn.setParent(self._scroll.viewport())
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedHeight(26)
        btn.adjustSize()
        self._style_stick_button(btn)
        btn.hide()
        btn.clicked.connect(self._scroll_to_bottom_clicked)
        self._stick_position_filter = _StickPositionFilter(self)
        self._scroll.viewport().installEventFilter(self._stick_position_filter)
        return btn

    def _style_stick_button(self, btn: QPushButton) -> None:
        p = current_palette()
        bg = p.get("bg_surface", "#ffffff")
        fg = p.get("text_secondary", "#6b7280")
        bd = p.get("border", "#e5e7eb")
        hv = p.get("bg_surface_hover", "#f3f4f6")
        btn.setStyleSheet(
            f"QPushButton {{ background-color: {bg}; color: {fg};"
            f"border: 1px solid {bd}; border-radius: 13px; padding: 0 10px;"
            f"font-size: 11px; }}"
            f"QPushButton:hover {{ background-color: {hv}; }}"
        )

    def _position_stick_button(self) -> None:
        btn = getattr(self, "_stick_button", None)
        if btn is None:
            return
        vp = self._scroll.viewport()
        btn.move(
            vp.width() - btn.width() - 14,
            vp.height() - btn.height() - 14,
        )

    def _on_scroll_value_changed(self, value: int) -> None:
        """滚动条位置变化: 距底部 >80px 翻转为非黏底并显示按钮。"""
        bar = self._scroll.verticalScrollBar()
        at_bottom = (bar.maximum() - value) <= 80
        self._stick_bottom = at_bottom
        btn = getattr(self, "_stick_button", None)
        if btn is None:
            return
        if at_bottom:
            btn.hide()
        else:
            btn.show()
            self._position_stick_button()

    def _on_scroll_range_changed(self, _min: int, _max: int) -> None:
        """内容高度变化 (新增消息) 后保持黏底。

        修复: 新消息到达时视口停在旧位置。singleShot(0) 触发时布局可能
        尚未完成, maximum 陈旧; rangeChanged 在布局后触发, 此时滚到底
        才能确保看到最新内容。非黏底 (用户上滑) 时不打扰阅读位置。
        """
        if not self._stick_bottom:
            return
        try:
            bar = self._scroll.verticalScrollBar()
            bar.setValue(bar.maximum())
        except RuntimeError:
            return

    def _scroll_to_bottom(self) -> None:
        """滚到底部 (延迟一拍, 等布局完成后设值, 避免提前滚动)。"""
        QTimer.singleShot(0, self._scroll_to_bottom_now)

    def _scroll_to_bottom_now(self) -> None:
        """延迟滚动回调 (宿主已销毁时安全忽略, 避免 Timer 引用已删对象)。"""
        if not isValid(self):
            return
        try:
            bar = self._scroll.verticalScrollBar()
            bar.setValue(bar.maximum())
        except RuntimeError:
            return

    def _scroll_to_bottom_clicked(self) -> None:
        """点击"回到底部": 滚到底并恢复黏底。"""
        self._stick_bottom = True
        btn = getattr(self, "_stick_button", None)
        if btn is not None:
            btn.hide()
        self._scroll_to_bottom()

    # ── 气泡主题样式 ──

    def _style_assistant_bubble(self, bubble: _AssistantBubble) -> None:
        """AI 气泡背景/圆角 (随主题, 内联覆盖 QSS 对 QTextBrowser 的默认白底)。"""
        p = current_palette()
        bg = p.get("bg_surface_hover", "#f3f4f6")
        bubble.setStyleSheet(
            f"QTextBrowser {{ background-color: {bg}; border-radius: 8px; }}"
        )

    def refresh_theme(self) -> None:
        """主题切换后重刷已渲染 AI 气泡 (含流式中) 与悬浮元素。

        接线由宿主负责 (例如在主题监听回调中调用)。
        """
        for bubble in getattr(self, "_ai_bubbles", []):
            if isinstance(bubble, _AssistantBubble):
                self._style_assistant_bubble(bubble)
                bubble.refresh()
        if self._stream_dirty and self._streaming_handle is not None:
            self._flush_stream()
        for label, role in getattr(self, "_welcome_items", []):
            self._style_welcome_label(label, role)
        btn = getattr(self, "_stick_button", None)
        if btn is not None:
            self._style_stick_button(btn)


    # ── 流式消息气泡 ──

    def start_stream_message(self) -> StreamMessageHandle:
        """创建一条流式助手消息气泡, 返回句柄 (追加文本用)。"""
        bubble = _AssistantBubble()
        bubble.setObjectName("AgentBubbleAssistant")
        bubble.setMaximumWidth(self._bubble_max_width(0.88, 460))
        bubble.set_markdown("")
        self._style_assistant_bubble(bubble)
        self._ai_bubbles.append(bubble)

        time_label = QLabel(f"AI 助手 · {datetime.now().strftime('%H:%M')}")
        time_label.setObjectName("AgentTimeLabel")

        bubble_row = QHBoxLayout()
        bubble_row.addWidget(bubble)
        bubble_row.addStretch()

        msg_layout = QVBoxLayout()
        msg_layout.setSpacing(2)
        msg_layout.setContentsMargins(0, 0, 0, 0)
        msg_layout.addLayout(bubble_row)

        self._messages_layout.insertLayout(
            self._messages_layout.count() - 1, msg_layout
        )
        self._last_bubble = bubble

        handle = StreamMessageHandle(msg_layout, bubble, time_label)
        self._streaming_handle = handle
        self._stream_dirty = False
        return handle

    def _schedule_stream_flush(self) -> None:
        """单例 100ms 节流定时器: 触发一次当前流式气泡渲染。"""
        if self._stream_timer is None:
            self._stream_timer = QTimer(self)
            self._stream_timer.setSingleShot(True)
            self._stream_timer.setInterval(100)
            self._stream_timer.timeout.connect(self._flush_stream)
        if not self._stream_timer.isActive():
            self._stream_timer.start()

    def _flush_stream(self) -> None:
        """渲染当前流式气泡 (markdown), 节流/收尾共用。"""
        if not self._stream_dirty:
            return
        handle = self._streaming_handle
        if handle is None:
            self._stream_dirty = False
            return
        handle.bubble.set_markdown(handle.raw_text)
        self._stream_dirty = False
        if self._stick_bottom:
            self._scroll_to_bottom()

    def append_stream_chunk(self, handle: StreamMessageHandle, text: str) -> None:
        """向流式气泡追加正式内容分块 (仅累积, 由节流定时器渲染)。"""
        handle.raw_text += text
        self._streaming_handle = handle
        self._stream_dirty = True
        self._schedule_stream_flush()
        if self._stick_bottom:
            self._scroll_to_bottom()

    def _on_reasoning_toggled(
        self, handle: StreamMessageHandle, checked: bool
    ) -> None:
        """思考过程折叠/展开切换。"""
        if handle.reasoning_label is not None:
            handle.reasoning_label.setVisible(checked)
        if handle.reasoning_toggle is not None:
            handle.reasoning_toggle.setText(
                "▾ 思考过程" if checked else "▸ 思考过程"
            )

    def append_stream_reasoning(self, handle: StreamMessageHandle, text: str) -> None:
        """向"思考过程"区追加推理分块 (首块创建标题按钮 + 完整文本标签)。"""
        if handle.reasoning_label is None:
            p = current_palette()
            fg = p.get("text_secondary", "#6b7280")
            bd = p.get("border", "#d0d3d9")
            toggle = QPushButton("▾ 思考过程")
            toggle.setObjectName("AgentThinkingToggle")
            toggle.setCheckable(True)
            toggle.setChecked(True)
            toggle.setCursor(Qt.CursorShape.PointingHandCursor)
            toggle.setStyleSheet(
                "QPushButton { border: none; background: transparent;"
                f"font-size: 11px; font-weight: 500; color: {fg}; padding: 0; }}"
            )
            content = QLabel("")
            content.setObjectName("AgentThinkingLabel")
            content.setWordWrap(True)
            content.setStyleSheet(
                f"font-size: 11px; color: {fg}; font-style: italic;"
                f"border-left: 2px solid {bd}; padding-left: 6px;"
            )
            toggle.toggled.connect(
                lambda checked: self._on_reasoning_toggled(handle, checked)
            )

            box = QVBoxLayout()
            box.setSpacing(2)
            box.setContentsMargins(0, 0, 0, 0)
            toggle_row = QHBoxLayout()
            toggle_row.addWidget(toggle)
            toggle_row.addStretch()
            box.addLayout(toggle_row)
            box.addWidget(content)
            handle.layout.insertLayout(0, box)

            handle.reasoning_toggle = toggle
            handle.reasoning_label = content
            handle.reasoning_box = box
            handle.reasoning_text = ""
        handle.reasoning_text += text
        handle.reasoning_label.setText(handle.reasoning_text)
        if self._stick_bottom:
            self._scroll_to_bottom()

    def finish_stream_message(self, handle: StreamMessageHandle) -> None:
        """流式收尾: 最终渲染一次、折叠思考区、持久化并黏底滚动。"""
        if self._stream_timer is not None and self._stream_timer.isActive():
            self._stream_timer.stop()
        # 立即最终渲染一次 (节流未触发的尾部内容)
        self._streaming_handle = handle
        self._stream_dirty = True
        self._flush_stream()
        if self._streaming_handle is handle:
            self._streaming_handle = None
            self._stream_dirty = False

        # 思考过程自动折叠
        if handle.reasoning_toggle is not None:
            handle.reasoning_toggle.setChecked(False)
        if handle.reasoning_label is not None:
            handle.reasoning_label.setVisible(False)

        time_row = QHBoxLayout()
        time_row.addWidget(handle.time_label)
        time_row.addStretch()
        handle.layout.addLayout(time_row)

        content = handle.raw_text
        if content:
            self._persist_message("assistant", content)

        if self._stick_bottom:
            self._scroll_to_bottom()


