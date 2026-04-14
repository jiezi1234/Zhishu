# PDF 生成模块重构 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `skills/skill_4_output/pdf_generator.py` 完全重写为现代卡片风格的 PDF 生成器，输出美观、全年龄通用的就医行程单。

**Architecture:** 使用 ReportLab Canvas + Platypus 混合模式。每个信息板块封装为独立的 `Flowable` 子类，由 `SimpleDocTemplate` 统一排版流；页眉/页脚通过 `onPage` 钩子用 Canvas 绘制；圆角卡片背景在每个 Flowable 的 `draw()` 方法中用 `canvas.roundRect()` 绘制。

**Tech Stack:** Python 3.9+, reportlab >= 4.0（已安装于 `lib/`），Windows 系统中文字体（simhei/msyh）

---

## 文件改动范围

| 文件 | 操作 |
|------|------|
| `skills/skill_4_output/pdf_generator.py` | 完全重写 |
| `skills/skill_4_output/output_generator.py` | 不改动（接口兼容） |

---

## Task 1: 搭建骨架 + 颜色常量 + 字体注册

**Files:**
- Modify: `skills/skill_4_output/pdf_generator.py`（完全重写，从空文件开始）

- [ ] **Step 1: 写测试——字体注册返回字体名（非 None）**

新建 `skills/skill_4_output/test_pdf_generator.py`，内容如下：

```python
"""
Tests for redesigned pdf_generator.py
Run: python -m pytest skills/skill_4_output/test_pdf_generator.py -v
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'lib'))
sys.path.insert(0, os.path.dirname(__file__))

def test_register_chinese_fonts_returns_name():
    from pdf_generator import register_chinese_fonts
    font_name = register_chinese_fonts()
    assert font_name is not None, "未找到中文字体，请确认 Windows 字体目录"
    assert isinstance(font_name, str)

def test_colors_defined():
    from pdf_generator import COLORS
    required = ['primary', 'card_bg', 'text', 'text_secondary',
                'timeline_node', 'divider', 'white']
    for key in required:
        assert key in COLORS, f"COLORS 缺少 '{key}'"
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd "D:\xuexi\competition\计算机设计大赛\project"
python -m pytest skills/skill_4_output/test_pdf_generator.py -v
```

期望：`ImportError` 或 `ModuleNotFoundError`（pdf_generator 还是旧版本）

- [ ] **Step 3: 将 pdf_generator.py 重写为骨架**

用以下内容完全替换 `skills/skill_4_output/pdf_generator.py`：

```python
"""
pdf_generator.py — 现代卡片风 PDF 生成器 (v2)

架构：ReportLab Canvas + Platypus 混合
  - 每个信息板块 = 独立 Flowable 子类
  - 页眉/页脚 = onPage 钩子（Canvas 绘制）
  - 圆角卡片背景 = 每个 Flowable.draw() 内调用 canvas.roundRect()
"""
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import pt, cm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table,
        TableStyle, Flowable
    )
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

# ── 颜色系统 ──────────────────────────────────────────────────────────────
COLORS = {
    'primary':        colors.HexColor('#2563EB'),  # 主色：卡片边框/表头/时间轴线
    'card_bg':        colors.HexColor('#EFF6FF'),  # 卡片背景
    'text':           colors.HexColor('#1E293B'),  # 正文
    'text_secondary': colors.HexColor('#64748B'),  # 标签/次要
    'timeline_node':  colors.HexColor('#10B981'),  # 时间轴节点绿色
    'divider':        colors.HexColor('#E2E8F0'),  # 分隔线
    'white':          colors.white,
    'table_alt':      colors.HexColor('#F8FAFC'),  # 表格偶数行
}

# ── 卡片尺寸常量 ──────────────────────────────────────────────────────────
CARD_RADIUS   = 6        # 圆角半径 pt
CARD_PADDING_H = 14      # 水平内边距 pt
CARD_PADDING_V = 12      # 垂直内边距 pt
CARD_LEFT_BORDER = 3     # 左侧蓝色边框宽度 pt
CARD_SPACING  = 10       # 卡片间距 pt


def register_chinese_fonts() -> Optional[str]:
    """注册中文字体，返回字体名；失败返回 None。"""
    candidates = [
        ("SimHei", "C:\\Windows\\Fonts\\simhei.ttf"),
        ("MSYH",   "C:\\Windows\\Fonts\\msyh.ttc"),
        ("SimSun", "C:\\Windows\\Fonts\\simsun.ttc"),
    ]
    for name, path in candidates:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont(name, path))
                return name
            except Exception:
                continue
    return None
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
python -m pytest skills/skill_4_output/test_pdf_generator.py::test_register_chinese_fonts_returns_name skills/skill_4_output/test_pdf_generator.py::test_colors_defined -v
```

期望：2 passed

- [ ] **Step 5: Commit**

```bash
git add skills/skill_4_output/pdf_generator.py skills/skill_4_output/test_pdf_generator.py
git commit -m "feat: scaffold new pdf_generator with color system and font registration"
```

---

## Task 2: 工具函数 + 页眉/页脚钩子

**Files:**
- Modify: `skills/skill_4_output/pdf_generator.py`（追加内容）

- [ ] **Step 1: 写测试**

在 `skills/skill_4_output/test_pdf_generator.py` 末尾追加：

```python
def test_font_sizes_standard():
    from pdf_generator import FontSizes
    fs = FontSizes(large=False)
    assert fs.title == 14
    assert fs.body  == 12
    assert fs.label == 11
    assert fs.table == 10
    assert fs.header_footer == 11

def test_font_sizes_large():
    from pdf_generator import FontSizes
    fs = FontSizes(large=True)
    assert fs.title == 18
    assert fs.body  == 15
    assert fs.label == 13
    assert fs.table == 12
    assert fs.header_footer == 13
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
python -m pytest skills/skill_4_output/test_pdf_generator.py::test_font_sizes_standard skills/skill_4_output/test_pdf_generator.py::test_font_sizes_large -v
```

期望：`ImportError: cannot import name 'FontSizes'`

- [ ] **Step 3: 实现 FontSizes + 工具函数 + 页眉/页脚**

在 `pdf_generator.py` 末尾追加：

```python
# ── 字体尺寸 ──────────────────────────────────────────────────────────────
class FontSizes:
    """按 large_font 模式返回对应字号。"""
    def __init__(self, large: bool = False):
        if large:
            self.title         = 18
            self.body          = 15
            self.label         = 13
            self.table         = 12
            self.header_footer = 13
        else:
            self.title         = 14
            self.body          = 12
            self.label         = 11
            self.table         = 10
            self.header_footer = 11


# ── 工具：圆角矩形 ────────────────────────────────────────────────────────
def draw_rounded_rect(canvas, x, y, w, h, r=CARD_RADIUS,
                      fill_color=None, stroke_color=None):
    """
    在 canvas 上绘制圆角矩形。
    x, y: 左下角坐标（ReportLab 坐标系，原点在左下）
    w, h: 宽高
    r:    圆角半径
    """
    canvas.saveState()
    if fill_color:
        canvas.setFillColor(fill_color)
    if stroke_color:
        canvas.setStrokeColor(stroke_color)
        canvas.setLineWidth(0.5)
    else:
        canvas.setLineWidth(0)
    canvas.roundRect(x, y, w, h, r,
                     fill=1 if fill_color else 0,
                     stroke=1 if stroke_color else 0)
    canvas.restoreState()


def draw_left_border(canvas, x, y, h, color=None):
    """在卡片左侧绘制 3pt 蓝色竖线。"""
    canvas.saveState()
    canvas.setStrokeColor(color or COLORS['primary'])
    canvas.setLineWidth(CARD_LEFT_BORDER)
    canvas.line(x, y, x, y + h)
    canvas.restoreState()


# ── 页眉/页脚钩子 ─────────────────────────────────────────────────────────
def _make_page_decorators(font_name: str, fs: FontSizes, gen_date: str):
    """
    返回 (on_first_page, on_later_pages) 两个钩子函数。
    gen_date: 'YYYY-MM-DD' 格式字符串
    """
    page_w, page_h = A4
    margin_x = 0.6 * cm * (72 / 2.54)   # ≈ 17pt，与文档边距一致（0.6cm）

    def draw_header_footer(canvas, doc):
        canvas.saveState()
        # ── 页眉 ──
        header_y = page_h - 28
        # 左：项目名
        canvas.setFont(font_name, fs.header_footer)
        canvas.setFillColor(COLORS['primary'])
        canvas.drawString(margin_x, header_y, "智枢 HealthPath")
        # 右：日期
        canvas.setFillColor(COLORS['text_secondary'])
        date_text = f"{gen_date} 生成"
        canvas.drawRightString(page_w - margin_x, header_y, date_text)
        # 底部分隔线
        canvas.setStrokeColor(COLORS['divider'])
        canvas.setLineWidth(0.5)
        canvas.line(margin_x, header_y - 6, page_w - margin_x, header_y - 6)

        # ── 页脚 ──
        footer_y = 20
        canvas.setStrokeColor(COLORS['divider'])
        canvas.line(margin_x, footer_y + 10, page_w - margin_x, footer_y + 10)
        canvas.setFont(font_name, fs.header_footer)
        canvas.setFillColor(COLORS['text_secondary'])
        footer_text = "祝您就医顺利！本文件仅供参考，具体挂号请以医院官网为准。"
        canvas.drawCentredString(page_w / 2, footer_y, footer_text)
        canvas.restoreState()

    return draw_header_footer, draw_header_footer
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
python -m pytest skills/skill_4_output/test_pdf_generator.py -v
```

期望：4 passed

- [ ] **Step 5: Commit**

```bash
git add skills/skill_4_output/pdf_generator.py skills/skill_4_output/test_pdf_generator.py
git commit -m "feat: add FontSizes, draw utils, and page header/footer hooks"
```

---

## Task 3: CardFlowable 基类 + InfoCardFlowable（就诊信息卡）

**Files:**
- Modify: `skills/skill_4_output/pdf_generator.py`（追加内容）

- [ ] **Step 1: 写测试**

在 `test_pdf_generator.py` 末尾追加：

```python
def test_info_card_flowable_wrap():
    """InfoCardFlowable.wrap() 应返回 (available_width, height > 0)"""
    from pdf_generator import InfoCardFlowable, FontSizes, register_chinese_fonts
    font = register_chinese_fonts()
    if font is None:
        import pytest; pytest.skip("No Chinese font available")
    rec = {
        'hospital_name': '北京协和医院',
        'doctor_name': '张医生',
        'doctor_title': '主任医师',
        'appointment_time': '2026-04-15 09:00',
        'queue_estimate_min': 30,
    }
    task = {'department': '骨科'}
    card = InfoCardFlowable(rec, task, font, FontSizes(large=False))
    w, h = card.wrap(400, 600)
    assert w == 400
    assert h > 0
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
python -m pytest skills/skill_4_output/test_pdf_generator.py::test_info_card_flowable_wrap -v
```

期望：`ImportError: cannot import name 'InfoCardFlowable'`

- [ ] **Step 3: 实现 CardFlowable 基类和 InfoCardFlowable**

在 `pdf_generator.py` 末尾追加：

```python
# ── 卡片基类 ──────────────────────────────────────────────────────────────
class CardFlowable(Flowable):
    """
    所有卡片的基类。子类重写 _content_height() 和 _draw_content()。
    负责绘制圆角背景、左侧蓝色边框。
    """
    def __init__(self, font_name: str, fs: FontSizes):
        super().__init__()
        self.font_name = font_name
        self.fs = fs
        self._avail_width = 0

    def wrap(self, available_width, available_height):
        self._avail_width = available_width
        h = self._content_height() + CARD_PADDING_V * 2
        return available_width, h

    def _content_height(self) -> float:
        """子类实现：返回内容区域高度（不含 padding）。"""
        raise NotImplementedError

    def draw(self):
        w = self._avail_width
        h = self._content_height() + CARD_PADDING_V * 2
        # 圆角背景
        draw_rounded_rect(self.canv, 0, 0, w, h,
                          fill_color=COLORS['card_bg'])
        # 左侧蓝色边框
        draw_left_border(self.canv, 0, 0, h)
        # 绘制内容（坐标原点在左下，内容从 top-padding 开始）
        self._draw_content(w, h)

    def _draw_content(self, card_w: float, card_h: float):
        raise NotImplementedError

    # ── 辅助：绘制卡片标题 ──
    def _draw_title(self, title: str, card_h: float):
        self.canv.saveState()
        self.canv.setFont(self.font_name, self.fs.title)
        self.canv.setFillColor(COLORS['primary'])
        # 标题在顶部 padding 位置
        y = card_h - CARD_PADDING_V - self.fs.title
        self.canv.drawString(CARD_PADDING_H + CARD_LEFT_BORDER + 4, y, title)
        self.canv.restoreState()
        return y  # 返回标题底部 y 坐标


# ── 卡片1：就诊信息 ───────────────────────────────────────────────────────
class InfoCardFlowable(CardFlowable):
    """就诊信息 Key-Value 网格卡片。"""

    ROWS = [
        ('医  院', 'hospital_name'),
        ('科  室', '_department'),
        ('医  生', '_doctor'),
        ('时  间', 'appointment_time'),
        ('预计排队', '_queue'),
    ]

    def __init__(self, rec: Dict, task_params: Dict,
                 font_name: str, fs: FontSizes):
        super().__init__(font_name, fs)
        self.rec = rec
        self.task_params = task_params
        self._row_h = fs.body + 10  # 每行高度

    def _get_value(self, key: str) -> str:
        if key == '_department':
            return self.task_params.get('department', '未指定')
        if key == '_doctor':
            return f"{self.rec.get('doctor_name', '')}  {self.rec.get('doctor_title', '')}"
        if key == '_queue':
            return f"约 {self.rec.get('queue_estimate_min', '—')} 分钟"
        return str(self.rec.get(key, '—'))

    def _content_height(self) -> float:
        title_h = self.fs.title + 8
        rows_h  = len(self.ROWS) * self._row_h
        return title_h + rows_h

    def _draw_content(self, card_w: float, card_h: float):
        title_y = self._draw_title("🏥  就诊信息", card_h)
        label_col_w = 60
        x_label = CARD_PADDING_H + CARD_LEFT_BORDER + 4
        x_value = x_label + label_col_w + 8
        divider_x2 = card_w - CARD_PADDING_H

        y = title_y - 6
        for label, key in self.ROWS:
            value = self._get_value(key)
            row_top = y
            row_bot = y - self._row_h

            # 标签
            self.canv.saveState()
            self.canv.setFont(self.font_name, self.fs.label)
            self.canv.setFillColor(COLORS['text_secondary'])
            self.canv.drawString(x_label, row_bot + 4, label)

            # 值
            self.canv.setFont(self.font_name, self.fs.body)
            self.canv.setFillColor(COLORS['text'])
            self.canv.drawString(x_value, row_bot + 4, value)

            # 分隔线（最后一行不画）
            if key != self.ROWS[-1][1]:
                self.canv.setStrokeColor(COLORS['divider'])
                self.canv.setLineWidth(0.5)
                self.canv.line(x_label, row_bot, divider_x2, row_bot)
            self.canv.restoreState()

            y = row_bot
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
python -m pytest skills/skill_4_output/test_pdf_generator.py -v
```

期望：5 passed

- [ ] **Step 5: Commit**

```bash
git add skills/skill_4_output/pdf_generator.py skills/skill_4_output/test_pdf_generator.py
git commit -m "feat: add CardFlowable base class and InfoCardFlowable"
```

---

## Task 4: TimelineFlowable（就诊时间轴）

**Files:**
- Modify: `skills/skill_4_output/pdf_generator.py`（追加内容）

- [ ] **Step 1: 写测试**

在 `test_pdf_generator.py` 末尾追加：

```python
def test_parse_appointment_time():
    from pdf_generator import _parse_appointment_time
    from datetime import datetime
    dt = _parse_appointment_time("2026-04-15 09:00")
    assert dt == datetime(2026, 4, 15, 9, 0)

def test_parse_appointment_time_fallback():
    from pdf_generator import _parse_appointment_time
    result = _parse_appointment_time("invalid_time")
    assert result is not None  # 降级到当天某时

def test_timeline_flowable_wrap():
    from pdf_generator import TimelineFlowable, FontSizes, register_chinese_fonts
    font = register_chinese_fonts()
    if font is None:
        import pytest; pytest.skip("No Chinese font")
    rec = {'appointment_time': '2026-04-15 09:00', 'total_travel_time_min': 30}
    card = TimelineFlowable(rec, font, FontSizes(large=False))
    w, h = card.wrap(400, 600)
    assert w == 400
    assert h > 0
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
python -m pytest skills/skill_4_output/test_pdf_generator.py::test_parse_appointment_time skills/skill_4_output/test_pdf_generator.py::test_timeline_flowable_wrap -v
```

期望：`ImportError`

- [ ] **Step 3: 实现 TimelineFlowable**

在 `pdf_generator.py` 末尾追加：

```python
# ── 时间解析辅助 ──────────────────────────────────────────────────────────
def _parse_appointment_time(time_str: str) -> datetime:
    """
    解析就诊时间字符串，失败时降级为今天 09:00。
    支持格式：'2026-04-15 09:00'，'2026-04-15 09:00:00'
    """
    for fmt in ('%Y-%m-%d %H:%M', '%Y-%m-%d %H:%M:%S'):
        try:
            return datetime.strptime(time_str, fmt)
        except (ValueError, TypeError):
            continue
    # 降级：使用今天 09:00
    now = datetime.now()
    return now.replace(hour=9, minute=0, second=0, microsecond=0)


# ── 卡片2：就诊时间轴 ─────────────────────────────────────────────────────
class TimelineFlowable(CardFlowable):
    """横向4节点就诊时间轴。"""

    LABELS = ['出发', '到院', '挂号', '就诊']
    NODE_R = 5      # 节点半径 pt
    AXIS_H = 40     # 轴线所在行高度 pt

    def __init__(self, rec: Dict, font_name: str, fs: FontSizes):
        super().__init__(font_name, fs)
        appt_dt = _parse_appointment_time(rec.get('appointment_time', ''))
        travel  = int(rec.get('total_travel_time_min', 30))
        self.times = [
            appt_dt - timedelta(minutes=travel + 30),   # 出发
            appt_dt - timedelta(minutes=30),             # 到院
            appt_dt - timedelta(minutes=25),             # 挂号
            appt_dt,                                     # 就诊
        ]

    def _content_height(self) -> float:
        label_h = self.fs.label + 4
        time_h  = self.fs.label + 4
        return self.fs.title + 8 + label_h + self.AXIS_H + time_h

    def _draw_content(self, card_w: float, card_h: float):
        title_y = self._draw_title("🕐  就诊时间轴", card_h)

        inner_w = card_w - (CARD_PADDING_H + CARD_LEFT_BORDER + 4) - CARD_PADDING_H
        x0 = CARD_PADDING_H + CARD_LEFT_BORDER + 4
        # 4个节点 x 坐标
        xs = [x0 + inner_w * i / 3 for i in range(4)]

        # 轴线 y（节点圆心 y）
        axis_y = title_y - (self.fs.label + 4) - self.AXIS_H / 2

        # 绘制连线（节点之间虚线）
        self.canv.saveState()
        self.canv.setStrokeColor(COLORS['primary'])
        self.canv.setLineWidth(1.5)
        self.canv.setDash([4, 3])  # 虚线
        for i in range(3):
            self.canv.line(xs[i] + self.NODE_R, axis_y,
                           xs[i + 1] - self.NODE_R, axis_y)
        self.canv.restoreState()

        # 绘制节点 + 标签 + 时间
        for i, (x, label, dt) in enumerate(zip(xs, self.LABELS, self.times)):
            # 节点圆
            self.canv.saveState()
            self.canv.setFillColor(COLORS['timeline_node'])
            self.canv.circle(x, axis_y, self.NODE_R, fill=1, stroke=0)

            # 标签（节点上方）
            self.canv.setFont(self.font_name, self.fs.label)
            self.canv.setFillColor(COLORS['text'])
            label_y = axis_y + self.NODE_R + 4
            self.canv.drawCentredString(x, label_y, label)

            # 时间（节点下方）
            time_str = dt.strftime('%H:%M')
            self.canv.setFont(self.font_name, self.fs.label)
            self.canv.setFillColor(COLORS['text_secondary'])
            time_y = axis_y - self.NODE_R - self.fs.label - 2
            self.canv.drawCentredString(x, time_y, time_str)
            self.canv.restoreState()
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
python -m pytest skills/skill_4_output/test_pdf_generator.py -v
```

期望：8 passed

- [ ] **Step 5: Commit**

```bash
git add skills/skill_4_output/pdf_generator.py skills/skill_4_output/test_pdf_generator.py
git commit -m "feat: add TimelineFlowable with auto-computed departure/arrival times"
```

---

## Task 5: TextCardFlowable（交通建议）+ TableCardFlowable（医院对比表）

**Files:**
- Modify: `skills/skill_4_output/pdf_generator.py`（追加内容）

- [ ] **Step 1: 写测试**

在 `test_pdf_generator.py` 末尾追加：

```python
def test_text_card_flowable_wrap():
    from pdf_generator import TextCardFlowable, FontSizes, register_chinese_fonts
    font = register_chinese_fonts()
    if font is None:
        import pytest; pytest.skip("No Chinese font")
    card = TextCardFlowable("标题", "这是正文内容测试。", font, FontSizes(False))
    w, h = card.wrap(400, 600)
    assert w == 400
    assert h > 0

def test_table_card_flowable_wrap():
    from pdf_generator import TableCardFlowable, FontSizes, register_chinese_fonts
    font = register_chinese_fonts()
    if font is None:
        import pytest; pytest.skip("No Chinese font")
    recs = [
        {'rank': 1, 'hospital_name': '协和', 'doctor_name': '张医生',
         'doctor_title': '主任', 'appointment_time': '09:00',
         'total_cost': 100, 'queue_estimate_min': 30,
         'distance_km': 2.5, 'score': 8.5}
    ]
    card = TableCardFlowable(recs, font, FontSizes(False))
    w, h = card.wrap(400, 600)
    assert w == 400
    assert h > 0
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
python -m pytest skills/skill_4_output/test_pdf_generator.py::test_text_card_flowable_wrap skills/skill_4_output/test_pdf_generator.py::test_table_card_flowable_wrap -v
```

期望：`ImportError`

- [ ] **Step 3: 实现两个 Flowable**

在 `pdf_generator.py` 末尾追加：

```python
# ── 卡片3：交通建议（纯文本卡片） ─────────────────────────────────────────
class TextCardFlowable(CardFlowable):
    """单段文字卡片，适用于交通建议等。"""

    def __init__(self, title: str, body_text: str,
                 font_name: str, fs: FontSizes):
        super().__init__(font_name, fs)
        self.title     = title
        self.body_text = body_text
        # 估算文字行数（按 30字/行 粗估，最少1行）
        chars_per_line = 28
        lines = max(1, len(body_text) // chars_per_line + 1)
        self._body_h = lines * (fs.body + 6)

    def _content_height(self) -> float:
        return self.fs.title + 8 + self._body_h

    def _draw_content(self, card_w: float, card_h: float):
        title_y = self._draw_title(self.title, card_h)
        x = CARD_PADDING_H + CARD_LEFT_BORDER + 4
        max_w = card_w - x - CARD_PADDING_H

        # 简单自动换行绘制
        self.canv.saveState()
        self.canv.setFont(self.font_name, self.fs.body)
        self.canv.setFillColor(COLORS['text'])

        # 按最大宽度切分文本（按字符数估算）
        chars_per_line = int(max_w / (self.fs.body * 0.6)) or 28
        lines = []
        text = self.body_text
        while text:
            lines.append(text[:chars_per_line])
            text = text[chars_per_line:]

        y = title_y - 6
        for line in lines:
            y -= (self.fs.body + 6)
            self.canv.drawString(x, y, line)
        self.canv.restoreState()


# ── 卡片4：医院对比表 ─────────────────────────────────────────────────────
class TableCardFlowable(CardFlowable):
    """医院对比表卡片，使用 ReportLab Table。"""

    HEADERS = ['排名', '医院', '医生', '职称', '时间', '费用', '排队', '距离', '评分']
    COL_WIDTHS_RATIO = [0.07, 0.18, 0.11, 0.10, 0.16, 0.09, 0.09, 0.09, 0.11]

    def __init__(self, recommendations: List[Dict],
                 font_name: str, fs: FontSizes):
        super().__init__(font_name, fs)
        self.recommendations = recommendations
        self._row_h = fs.table + 8
        self._num_rows = len(recommendations) + 1  # +1 表头

    def _content_height(self) -> float:
        return self.fs.title + 8 + self._num_rows * self._row_h

    def _draw_content(self, card_w: float, card_h: float):
        self._draw_title("📋  医院对比", card_h)
        title_h = self.fs.title + 8

        table_w = card_w - (CARD_PADDING_H + CARD_LEFT_BORDER + 4) - CARD_PADDING_H
        col_widths = [r * table_w for r in self.COL_WIDTHS_RATIO]

        data = [self.HEADERS]
        for r in self.recommendations:
            data.append([
                str(r.get('rank', '—')),
                r.get('hospital_name', '—'),
                r.get('doctor_name', '—'),
                r.get('doctor_title', '—'),
                r.get('appointment_time', '—'),
                f"{r.get('total_cost', '—')}元",
                f"{r.get('queue_estimate_min', '—')}分",
                f"{r.get('distance_km', '—')}km",
                f"{r.get('score', '—')}/10",
            ])

        style = TableStyle([
            # 表头
            ('FONT',        (0, 0), (-1, 0),  self.font_name, self.fs.table),
            ('BACKGROUND',  (0, 0), (-1, 0),  COLORS['primary']),
            ('TEXTCOLOR',   (0, 0), (-1, 0),  COLORS['white']),
            # 数据行
            ('FONT',        (0, 1), (-1, -1), self.font_name, self.fs.table),
            ('TEXTCOLOR',   (0, 1), (-1, -1), COLORS['text']),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [COLORS['white'], COLORS['table_alt']]),
            # 通用
            ('ALIGN',       (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN',      (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID',        (0, 0), (-1, -1), 0.5, COLORS['divider']),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING',(0, 0), (-1, -1), 3),
            ('TOPPADDING',  (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING',(0, 0),(-1, -1), 3),
        ])

        t = Table(data, colWidths=col_widths, rowHeights=self._row_h)
        t.setStyle(style)

        # 在 canvas 上手动定位 Table
        x = CARD_PADDING_H + CARD_LEFT_BORDER + 4
        table_h = self._num_rows * self._row_h
        y_bottom = card_h - CARD_PADDING_V - title_h - table_h
        t.wrapOn(self.canv, table_w, table_h)
        t.drawOn(self.canv, x, y_bottom)
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
python -m pytest skills/skill_4_output/test_pdf_generator.py -v
```

期望：10 passed

- [ ] **Step 5: Commit**

```bash
git add skills/skill_4_output/pdf_generator.py skills/skill_4_output/test_pdf_generator.py
git commit -m "feat: add TextCardFlowable and TableCardFlowable"
```

---

## Task 6: TwoColumnCardFlowable（出行清单 + 需求摘要并排）

**Files:**
- Modify: `skills/skill_4_output/pdf_generator.py`（追加内容）

- [ ] **Step 1: 写测试**

在 `test_pdf_generator.py` 末尾追加：

```python
def test_two_column_card_flowable_wrap():
    from pdf_generator import TwoColumnCardFlowable, FontSizes, register_chinese_fonts
    font = register_chinese_fonts()
    if font is None:
        import pytest; pytest.skip("No Chinese font")
    task = {'department': '骨科', 'symptom': '腰疼',
             'time_window': '本周', 'travel_preference': '均衡'}
    card = TwoColumnCardFlowable(task, font, FontSizes(False))
    w, h = card.wrap(400, 600)
    assert w == 400
    assert h > 0
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
python -m pytest skills/skill_4_output/test_pdf_generator.py::test_two_column_card_flowable_wrap -v
```

期望：`ImportError`

- [ ] **Step 3: 实现 TwoColumnCardFlowable**

在 `pdf_generator.py` 末尾追加：

```python
# ── 卡片5：出行清单 + 需求摘要（左右并排） ────────────────────────────────
class TwoColumnCardFlowable(CardFlowable):
    """左列：出行清单；右列：需求摘要。中间竖线分隔。"""

    CHECKLIST = [
        '□  身份证（千万别忘了）',
        '□  医保卡 / 社保卡',
        '□  手机 & 充电宝',
        '□  钱包 / 支付宝',
    ]
    SUMMARY_KEYS = [
        ('科室', 'department'),
        ('症状', 'symptom'),
        ('时段', 'time_window'),
        ('偏好', 'travel_preference'),
    ]

    def __init__(self, task_params: Dict, font_name: str, fs: FontSizes):
        super().__init__(font_name, fs)
        self.task_params = task_params
        row_count = max(len(self.CHECKLIST), len(self.SUMMARY_KEYS))
        self._row_h = fs.body + 8
        self._rows  = row_count

    def _content_height(self) -> float:
        title_h = self.fs.title + 10
        body_h  = self._rows * self._row_h
        return title_h + body_h

    def _draw_content(self, card_w: float, card_h: float):
        # 两列标题行
        inner_x = CARD_PADDING_H + CARD_LEFT_BORDER + 4
        inner_w = card_w - inner_x - CARD_PADDING_H
        col_w   = inner_w / 2
        mid_x   = inner_x + col_w

        # 标题
        title_y = card_h - CARD_PADDING_V - self.fs.title
        self.canv.saveState()
        self.canv.setFont(self.font_name, self.fs.title)
        self.canv.setFillColor(COLORS['primary'])
        self.canv.drawString(inner_x, title_y, "🎒  出行清单")
        self.canv.drawString(mid_x + 8, title_y, "📊  需求摘要")
        self.canv.restoreState()

        # 竖线分隔
        body_top = title_y - 6
        body_bot = body_top - self._rows * self._row_h
        self.canv.saveState()
        self.canv.setStrokeColor(COLORS['divider'])
        self.canv.setLineWidth(1)
        self.canv.line(mid_x, body_top, mid_x, body_bot)
        self.canv.restoreState()

        # 左列：出行清单
        y = body_top
        self.canv.saveState()
        self.canv.setFont(self.font_name, self.fs.body)
        self.canv.setFillColor(COLORS['text'])
        for item in self.CHECKLIST:
            y -= self._row_h
            self.canv.drawString(inner_x, y + 2, item)
        self.canv.restoreState()

        # 右列：需求摘要
        y = body_top
        self.canv.saveState()
        for label, key in self.SUMMARY_KEYS:
            y -= self._row_h
            value = self.task_params.get(key, '未指定') or '未指定'
            self.canv.setFont(self.font_name, self.fs.label)
            self.canv.setFillColor(COLORS['text_secondary'])
            self.canv.drawString(mid_x + 8, y + 2, f"{label}：")
            self.canv.setFont(self.font_name, self.fs.body)
            self.canv.setFillColor(COLORS['text'])
            self.canv.drawString(mid_x + 8 + 36, y + 2, str(value))
        self.canv.restoreState()
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
python -m pytest skills/skill_4_output/test_pdf_generator.py -v
```

期望：11 passed

- [ ] **Step 5: Commit**

```bash
git add skills/skill_4_output/pdf_generator.py skills/skill_4_output/test_pdf_generator.py
git commit -m "feat: add TwoColumnCardFlowable for checklist and summary"
```

---

## Task 7: 组装主入口 generate_pdf_document()

**Files:**
- Modify: `skills/skill_4_output/pdf_generator.py`（追加内容）

- [ ] **Step 1: 写测试**

在 `test_pdf_generator.py` 末尾追加：

```python
def test_generate_pdf_document_creates_file(tmp_path):
    from pdf_generator import generate_pdf_document
    recs = [
        {
            'rank': 1,
            'hospital_name': '北京协和医院',
            'doctor_name': '张医生',
            'doctor_title': '主任医师',
            'appointment_time': '2026-04-15 09:00',
            'total_cost': 100,
            'total_travel_time_min': 30,
            'distance_km': 2.5,
            'queue_estimate_min': 30,
            'score': 8.5,
            'reason': '距离近，排队短',
        }
    ]
    task = {'department': '骨科', 'symptom': '腰疼',
            'time_window': '本周', 'travel_preference': '均衡'}
    out = str(tmp_path / "test_output.pdf")
    generate_pdf_document(recs, task, out, large_font=False)
    import os
    assert os.path.exists(out)
    assert os.path.getsize(out) > 1000  # PDF 至少 1KB

def test_generate_pdf_document_large_font(tmp_path):
    from pdf_generator import generate_pdf_document
    recs = [
        {
            'rank': 1, 'hospital_name': '协和', 'doctor_name': '李医生',
            'doctor_title': '副主任', 'appointment_time': '2026-04-16 10:00',
            'total_cost': 80, 'total_travel_time_min': 20,
            'distance_km': 3.0, 'queue_estimate_min': 20,
            'score': 7.8, 'reason': '评分较高',
        }
    ]
    task = {'department': '内科', 'symptom': '发烧'}
    out = str(tmp_path / "test_large.pdf")
    generate_pdf_document(recs, task, out, large_font=True)
    import os
    assert os.path.exists(out)
    assert os.path.getsize(out) > 1000

def test_generate_pdf_document_empty_recs(tmp_path):
    from pdf_generator import generate_pdf_document
    out = str(tmp_path / "test_empty.pdf")
    generate_pdf_document([], {}, out, large_font=False)
    import os
    assert os.path.exists(out)  # 即使无数据也应生成文件（显示提示）
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
python -m pytest skills/skill_4_output/test_pdf_generator.py::test_generate_pdf_document_creates_file -v
```

期望：调用 `generate_pdf_document` 失败（函数未实现）

- [ ] **Step 3: 实现 generate_pdf_document() + 文本降级**

在 `pdf_generator.py` 末尾追加：

```python
# ── 主入口 ────────────────────────────────────────────────────────────────
def generate_pdf_document(recommendations: List[Dict], task_params: Dict,
                          output_path: str, large_font: bool = False):
    """
    生成现代卡片风就医行程单 PDF。
    接口与旧版保持完全一致，output_generator.py 无需修改。
    """
    if not REPORTLAB_AVAILABLE:
        _generate_text_fallback(recommendations, task_params, output_path)
        return

    font_name = register_chinese_fonts()
    if not font_name:
        _generate_text_fallback(recommendations, task_params, output_path)
        return

    fs = FontSizes(large=large_font)
    gen_date = datetime.now().strftime('%Y-%m-%d')

    # ── 页面边距（为页眉/页脚留空间）──
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=36,    # 0.5 inch
        rightMargin=36,
        topMargin=48,     # 为页眉留空间
        bottomMargin=40,  # 为页脚留空间
    )

    on_page, on_later = _make_page_decorators(font_name, fs, gen_date)

    elements = []

    if recommendations:
        rec = recommendations[0]

        # 卡片1：就诊信息
        elements.append(InfoCardFlowable(rec, task_params, font_name, fs))
        elements.append(Spacer(1, CARD_SPACING))

        # 卡片2：就诊时间轴
        elements.append(TimelineFlowable(rec, font_name, fs))
        elements.append(Spacer(1, CARD_SPACING))

        # 卡片3：交通建议
        travel_text = (
            f"推荐打车前往，预计行程约 {rec.get('total_travel_time_min', '—')} 分钟。"
            f"综合评分 {rec.get('score', '—')}/10 分——{rec.get('reason', '')}。"
            f"建议提前 15 分钟到院完成分诊。"
        )
        elements.append(TextCardFlowable("🚗  交通建议", travel_text, font_name, fs))
        elements.append(Spacer(1, CARD_SPACING))

        # 卡片4：医院对比表
        elements.append(TableCardFlowable(recommendations, font_name, fs))
        elements.append(Spacer(1, CARD_SPACING))

        # 卡片5：出行清单 + 需求摘要
        elements.append(TwoColumnCardFlowable(task_params, font_name, fs))

    else:
        # 无数据时显示提示卡片
        elements.append(TextCardFlowable(
            "⚠️  暂无匹配号源",
            "未找到符合条件的号源，请稍后重试，或尝试放宽科室和时间条件。",
            font_name, fs
        ))

    doc.build(elements, onFirstPage=on_page, onLaterPages=on_later)


# ── 文本降级（reportlab 不可用时）────────────────────────────────────────
def _generate_text_fallback(recommendations: List[Dict],
                             task_params: Dict, output_path: str):
    """reportlab 不可用时生成纯文本文件。"""
    lines = ["就医行程单", "=" * 60, ""]
    if recommendations:
        r = recommendations[0]
        lines += [
            f"医院：{r.get('hospital_name', '—')}",
            f"科室：{task_params.get('department', '—')}",
            f"医生：{r.get('doctor_name', '—')} {r.get('doctor_title', '')}",
            f"时间：{r.get('appointment_time', '—')}",
            f"排队：约 {r.get('queue_estimate_min', '—')} 分钟",
            "",
            "出行清单：身份证 / 医保卡 / 手机 / 钱包",
        ]
    else:
        lines.append("未找到匹配号源，请稍后重试。")
    lines += ["", "=" * 60, "祝您就医顺利！"]
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines))
```

- [ ] **Step 4: 运行全部测试，确认通过**

```bash
python -m pytest skills/skill_4_output/test_pdf_generator.py -v
```

期望：14 passed（或更多）

- [ ] **Step 5: Commit**

```bash
git add skills/skill_4_output/pdf_generator.py skills/skill_4_output/test_pdf_generator.py
git commit -m "feat: assemble generate_pdf_document() main entry point"
```

---

## Task 8: 端到端验收 + 集成测试

**Files:**
- 无新文件，运行现有测试

- [ ] **Step 1: 目视验收——直接生成 PDF 查看效果**

```bash
cd "D:\xuexi\competition\计算机设计大赛\project"
python skills/skill_4_output/output_generator.py
```

期望输出类似：
```
{
  "timestamp": "20260414_143022",
  "format": "large_font_pdf",
  "files": {"pdf": "D:\\...\\output\\appointment_itinerary_20260414_143022.pdf"},
  "status": "success"
}
```

用 PDF 阅读器（Adobe Reader / 浏览器）打开生成文件，目视确认：
- [ ] 页眉显示"智枢 HealthPath"和日期
- [ ] 5 个卡片均有圆角蓝色背景和左侧边框
- [ ] 时间轴有4个绿色节点和蓝色虚线
- [ ] 医院对比表有蓝色表头
- [ ] 出行清单和需求摘要左右并排
- [ ] 页脚显示祝福语

- [ ] **Step 2: 运行集成测试**

```bash
python tests/test_integration.py
```

期望：所有场景打印 `[PASS] Test passed`

- [ ] **Step 3: 运行全部单元测试**

```bash
python -m pytest skills/skill_4_output/test_pdf_generator.py -v
```

期望：14 passed，0 failed

- [ ] **Step 4: 最终 Commit**

```bash
git add .
git commit -m "feat: complete PDF redesign - modern card layout with timeline

- Modern card-style layout with rounded corners and blue left border
- New timeline card with 4 nodes (departure/arrival/checkin/appointment)
- Clean header/footer on every page
- Two-column card for checklist + summary
- Full backward compatibility with output_generator.py"
```

---

## 自检结果

- ✅ spec 所有板块均有对应 Task
- ✅ 无 TBD / TODO 占位符
- ✅ 类型/方法名一致（`InfoCardFlowable`、`TimelineFlowable` 等在所有 Task 中名称相同）
- ✅ 每步均含完整代码，无"参考上方"引用
- ✅ 接口兼容性：`generate_pdf_document(recommendations, task_params, output_path, large_font)` 签名不变
