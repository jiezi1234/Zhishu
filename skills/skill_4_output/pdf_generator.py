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
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        SimpleDocTemplate, Spacer, Table,
        TableStyle, Flowable
    )
    from reportlab.lib import colors
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

# ── 颜色系统 ──────────────────────────────────────────────────────────────
if REPORTLAB_AVAILABLE:
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
else:
    COLORS = {}

# ── 卡片尺寸常量 ──────────────────────────────────────────────────────────
CARD_RADIUS    = 6    # 圆角半径 pt
CARD_PADDING_H = 14   # 水平内边距 pt
CARD_PADDING_V = 12   # 垂直内边距 pt
CARD_LEFT_BORDER = 3  # 左侧蓝色边框宽度 pt
CARD_SPACING   = 10   # 卡片间距 pt


def register_chinese_fonts() -> Optional[str]:
    """注册中文字体，返回字体名；失败返回 None。"""
    if not REPORTLAB_AVAILABLE:
        return None
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


# ── 工具：圆角矩形 + 左侧边框 ────────────────────────────────────────────
def draw_rounded_rect(canvas, x, y, w, h, r=CARD_RADIUS,
                      fill_color=None, stroke_color=None):
    """在 canvas 上绘制圆角矩形（左下角坐标系）。"""
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
def _make_page_decorators(font_name: str, fs: 'FontSizes', gen_date: str):
    """返回 (on_first_page, on_later_pages) 两个钩子函数。"""
    page_w, page_h = A4
    margin_x = 36

    def draw_header_footer(canvas, doc):
        canvas.saveState()
        # 页眉
        header_y = page_h - 28
        canvas.setFont(font_name, fs.header_footer)
        canvas.setFillColor(COLORS['primary'])
        canvas.drawString(margin_x, header_y, "智枢 HealthPath")
        canvas.setFillColor(COLORS['text_secondary'])
        canvas.drawRightString(page_w - margin_x, header_y, f"{gen_date} 生成")
        canvas.setStrokeColor(COLORS['divider'])
        canvas.setLineWidth(0.5)
        canvas.line(margin_x, header_y - 6, page_w - margin_x, header_y - 6)
        # 页脚
        footer_y = 18
        canvas.setStrokeColor(COLORS['divider'])
        canvas.line(margin_x, footer_y + 12, page_w - margin_x, footer_y + 12)
        canvas.setFont(font_name, fs.header_footer)
        canvas.setFillColor(COLORS['text_secondary'])
        canvas.drawCentredString(
            page_w / 2, footer_y,
            "祝您就医顺利！本文件仅供参考，具体挂号请以医院官网为准。"
        )
        canvas.restoreState()

    return draw_header_footer, draw_header_footer


# ── 卡片基类 ──────────────────────────────────────────────────────────────
class CardFlowable(Flowable):
    """所有卡片的基类，负责绘制圆角背景和左侧蓝色边框。"""
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
        raise NotImplementedError

    def draw(self):
        w = self._avail_width
        h = self._content_height() + CARD_PADDING_V * 2
        draw_rounded_rect(self.canv, 0, 0, w, h, fill_color=COLORS['card_bg'])
        draw_left_border(self.canv, 0, 0, h)
        self._draw_content(w, h)

    def _draw_content(self, card_w: float, card_h: float):
        raise NotImplementedError

    def _draw_title(self, title: str, card_h: float) -> float:
        """绘制卡片标题，返回标题文字底部 y 坐标。"""
        self.canv.saveState()
        self.canv.setFont(self.font_name, self.fs.title)
        self.canv.setFillColor(COLORS['primary'])
        y = card_h - CARD_PADDING_V - self.fs.title
        self.canv.drawString(CARD_PADDING_H + CARD_LEFT_BORDER + 4, y, title)
        self.canv.restoreState()
        return y


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

    def __init__(self, rec: Dict, task_params: Dict, font_name: str, fs: FontSizes):
        super().__init__(font_name, fs)
        self.rec = rec
        self.task_params = task_params
        self._row_h = fs.body + 10

    def _get_value(self, key: str) -> str:
        if key == '_department':
            return self.task_params.get('department', '未指定')
        if key == '_doctor':
            return f"{self.rec.get('doctor_name', '')}  {self.rec.get('doctor_title', '')}".strip()
        if key == '_queue':
            return f"约 {self.rec.get('queue_estimate_min', '—')} 分钟"
        return str(self.rec.get(key, '—'))

    def _content_height(self) -> float:
        return self.fs.title + 8 + len(self.ROWS) * self._row_h

    def _draw_content(self, card_w: float, card_h: float):
        title_y    = self._draw_title("🏥  就诊信息", card_h)
        x_label    = CARD_PADDING_H + CARD_LEFT_BORDER + 4
        x_value    = x_label + 68
        divider_x2 = card_w - CARD_PADDING_H
        y = title_y - 6
        for i, (label, key) in enumerate(self.ROWS):
            row_bot = y - self._row_h
            self.canv.saveState()
            self.canv.setFont(self.font_name, self.fs.label)
            self.canv.setFillColor(COLORS['text_secondary'])
            self.canv.drawString(x_label, row_bot + 4, label)
            self.canv.setFont(self.font_name, self.fs.body)
            self.canv.setFillColor(COLORS['text'])
            self.canv.drawString(x_value, row_bot + 4, self._get_value(key))
            if i < len(self.ROWS) - 1:
                self.canv.setStrokeColor(COLORS['divider'])
                self.canv.setLineWidth(0.5)
                self.canv.line(x_label, row_bot, divider_x2, row_bot)
            self.canv.restoreState()
            y = row_bot


# ── 时间解析辅助 ──────────────────────────────────────────────────────────
def _parse_appointment_time(time_str: str) -> datetime:
    """解析就诊时间字符串，失败时降级为今天 09:00。"""
    for fmt in ('%Y-%m-%d %H:%M', '%Y-%m-%d %H:%M:%S'):
        try:
            return datetime.strptime(str(time_str), fmt)
        except (ValueError, TypeError):
            continue
    now = datetime.now()
    return now.replace(hour=9, minute=0, second=0, microsecond=0)


# ── 卡片2：就诊时间轴 ─────────────────────────────────────────────────────
class TimelineFlowable(CardFlowable):
    """横向4节点就诊时间轴。"""
    LABELS = ['出发', '到院', '挂号', '就诊']
    NODE_R = 5
    AXIS_H = 44

    def __init__(self, rec: Dict, font_name: str, fs: FontSizes):
        super().__init__(font_name, fs)
        appt_dt = _parse_appointment_time(rec.get('appointment_time', ''))
        travel  = int(rec.get('total_travel_time_min', 30))
        self.times = [
            appt_dt - timedelta(minutes=travel + 30),
            appt_dt - timedelta(minutes=30),
            appt_dt - timedelta(minutes=25),
            appt_dt,
        ]

    def _content_height(self) -> float:
        return self.fs.title + 8 + (self.fs.label + 4) + self.AXIS_H + (self.fs.label + 4)

    def _draw_content(self, card_w: float, card_h: float):
        title_y = self._draw_title("🕐  就诊时间轴", card_h)
        x0      = CARD_PADDING_H + CARD_LEFT_BORDER + 4
        inner_w = card_w - x0 - CARD_PADDING_H
        xs      = [x0 + inner_w * i / 3 for i in range(4)]
        axis_y  = title_y - (self.fs.label + 4) - self.AXIS_H / 2
        # 连线
        self.canv.saveState()
        self.canv.setStrokeColor(COLORS['primary'])
        self.canv.setLineWidth(1.5)
        self.canv.setDash([5, 3])
        for i in range(3):
            self.canv.line(xs[i] + self.NODE_R, axis_y, xs[i+1] - self.NODE_R, axis_y)
        self.canv.restoreState()
        # 节点 + 标签 + 时间
        for x, label, dt in zip(xs, self.LABELS, self.times):
            self.canv.saveState()
            self.canv.setFillColor(COLORS['timeline_node'])
            self.canv.circle(x, axis_y, self.NODE_R, fill=1, stroke=0)
            self.canv.setFont(self.font_name, self.fs.label)
            self.canv.setFillColor(COLORS['text'])
            self.canv.drawCentredString(x, axis_y + self.NODE_R + 5, label)
            self.canv.setFillColor(COLORS['text_secondary'])
            self.canv.drawCentredString(x, axis_y - self.NODE_R - self.fs.label - 3, dt.strftime('%H:%M'))
            self.canv.restoreState()


# ── 卡片3：纯文字卡片 ─────────────────────────────────────────────────────
class TextCardFlowable(CardFlowable):
    """单段文字卡片（交通建议等）。"""
    def __init__(self, title: str, body_text: str, font_name: str, fs: FontSizes):
        super().__init__(font_name, fs)
        self.title     = title
        self.body_text = body_text
        lines = max(1, len(body_text) // 30 + 1)
        self._body_h = lines * (fs.body + 7)

    def _content_height(self) -> float:
        return self.fs.title + 8 + self._body_h

    def _draw_content(self, card_w: float, card_h: float):
        title_y = self._draw_title(self.title, card_h)
        x = CARD_PADDING_H + CARD_LEFT_BORDER + 4
        max_w = card_w - x - CARD_PADDING_H
        cpl   = max(10, int(max_w / (self.fs.body * 0.62)))
        lines = []
        text  = self.body_text
        while text:
            lines.append(text[:cpl])
            text = text[cpl:]
        self.canv.saveState()
        self.canv.setFont(self.font_name, self.fs.body)
        self.canv.setFillColor(COLORS['text'])
        y = title_y - 6
        for line in lines:
            y -= (self.fs.body + 7)
            self.canv.drawString(x, y, line)
        self.canv.restoreState()


# ── 卡片4：医院对比表 ─────────────────────────────────────────────────────
class TableCardFlowable(CardFlowable):
    """医院对比表卡片。"""
    HEADERS          = ['排名', '医院', '医生', '职称', '时间', '费用', '排队', '距离', '评分']
    COL_WIDTHS_RATIO = [0.07, 0.18, 0.11, 0.10, 0.16, 0.09, 0.09, 0.09, 0.11]

    def __init__(self, recommendations: List[Dict], font_name: str, fs: FontSizes):
        super().__init__(font_name, fs)
        self.recommendations = recommendations
        self._row_h    = fs.table + 9
        self._num_rows = len(recommendations) + 1

    def _content_height(self) -> float:
        return self.fs.title + 8 + self._num_rows * self._row_h

    def _draw_content(self, card_w: float, card_h: float):
        self._draw_title("📋  医院对比", card_h)
        title_h = self.fs.title + 8
        x       = CARD_PADDING_H + CARD_LEFT_BORDER + 4
        table_w = card_w - x - CARD_PADDING_H
        col_widths = [r * table_w for r in self.COL_WIDTHS_RATIO]
        data = [self.HEADERS]
        for r in self.recommendations:
            data.append([
                str(r.get('rank', '—')),
                r.get('hospital_name', '—'),
                r.get('doctor_name', '—'),
                r.get('doctor_title', '—'),
                str(r.get('appointment_time', '—')),
                f"{r.get('total_cost', '—')}元",
                f"{r.get('queue_estimate_min', '—')}分",
                f"{r.get('distance_km', '—')}km",
                f"{r.get('score', '—')}/10",
            ])
        style = TableStyle([
            ('FONT',           (0, 0), (-1,  0), self.font_name, self.fs.table),
            ('BACKGROUND',     (0, 0), (-1,  0), COLORS['primary']),
            ('TEXTCOLOR',      (0, 0), (-1,  0), COLORS['white']),
            ('FONT',           (0, 1), (-1, -1), self.font_name, self.fs.table),
            ('TEXTCOLOR',      (0, 1), (-1, -1), COLORS['text']),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [COLORS['white'], COLORS['table_alt']]),
            ('ALIGN',          (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN',         (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID',           (0, 0), (-1, -1), 0.5, COLORS['divider']),
            ('LEFTPADDING',    (0, 0), (-1, -1), 3),
            ('RIGHTPADDING',   (0, 0), (-1, -1), 3),
            ('TOPPADDING',     (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING',  (0, 0), (-1, -1), 3),
        ])
        t = Table(data, colWidths=col_widths, rowHeights=self._row_h)
        t.setStyle(style)
        table_h  = self._num_rows * self._row_h
        y_bottom = card_h - CARD_PADDING_V - title_h - table_h
        t.wrapOn(self.canv, table_w, table_h)
        t.drawOn(self.canv, x, y_bottom)


# ── 卡片5：出行清单 + 需求摘要（左右并排） ────────────────────────────────
class TwoColumnCardFlowable(CardFlowable):
    """左列：出行清单；右列：需求摘要。"""
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
        self._rows  = max(len(self.CHECKLIST), len(self.SUMMARY_KEYS))
        self._row_h = fs.body + 9

    def _content_height(self) -> float:
        return self.fs.title + 10 + self._rows * self._row_h

    def _draw_content(self, card_w: float, card_h: float):
        x0      = CARD_PADDING_H + CARD_LEFT_BORDER + 4
        inner_w = card_w - x0 - CARD_PADDING_H
        mid_x   = x0 + inner_w / 2
        # 两列标题
        title_y = card_h - CARD_PADDING_V - self.fs.title
        self.canv.saveState()
        self.canv.setFont(self.font_name, self.fs.title)
        self.canv.setFillColor(COLORS['primary'])
        self.canv.drawString(x0, title_y, "🎒  出行清单")
        self.canv.drawString(mid_x + 8, title_y, "📊  需求摘要")
        self.canv.restoreState()
        # 竖线分隔
        body_top = title_y - 8
        body_bot = body_top - self._rows * self._row_h
        self.canv.saveState()
        self.canv.setStrokeColor(COLORS['divider'])
        self.canv.setLineWidth(1)
        self.canv.line(mid_x, body_top, mid_x, body_bot)
        self.canv.restoreState()
        # 左列
        y = body_top
        self.canv.saveState()
        self.canv.setFont(self.font_name, self.fs.body)
        self.canv.setFillColor(COLORS['text'])
        for item in self.CHECKLIST:
            y -= self._row_h
            self.canv.drawString(x0, y + 2, item)
        self.canv.restoreState()
        # 右列
        y = body_top
        self.canv.saveState()
        for label, key in self.SUMMARY_KEYS:
            y -= self._row_h
            value = str(self.task_params.get(key, '未指定') or '未指定')
            self.canv.setFont(self.font_name, self.fs.label)
            self.canv.setFillColor(COLORS['text_secondary'])
            self.canv.drawString(mid_x + 8, y + 2, f"{label}：")
            self.canv.setFont(self.font_name, self.fs.body)
            self.canv.setFillColor(COLORS['text'])
            self.canv.drawString(mid_x + 45, y + 2, value)
        self.canv.restoreState()


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

    fs       = FontSizes(large=large_font)
    gen_date = datetime.now().strftime('%Y-%m-%d')
    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        leftMargin=36, rightMargin=36, topMargin=50, bottomMargin=42,
    )
    on_page, on_later = _make_page_decorators(font_name, fs, gen_date)
    elements = []

    if recommendations:
        rec = recommendations[0]
        elements.append(InfoCardFlowable(rec, task_params, font_name, fs))
        elements.append(Spacer(1, CARD_SPACING))
        elements.append(TimelineFlowable(rec, font_name, fs))
        elements.append(Spacer(1, CARD_SPACING))
        travel_text = (
            f"推荐打车前往，预计行程约 {rec.get('total_travel_time_min', '—')} 分钟。"
            f"综合评分 {rec.get('score', '—')}/10 分——{rec.get('reason', '')}。"
            f"建议提前 15 分钟到院完成分诊。"
        )
        elements.append(TextCardFlowable("🚗  交通建议", travel_text, font_name, fs))
        elements.append(Spacer(1, CARD_SPACING))
        elements.append(TableCardFlowable(recommendations, font_name, fs))
        elements.append(Spacer(1, CARD_SPACING))
        elements.append(TwoColumnCardFlowable(task_params, font_name, fs))
    else:
        elements.append(TextCardFlowable(
            "⚠️  暂无匹配号源",
            "未找到符合条件的号源，请稍后重试，或尝试放宽科室和时间条件。",
            font_name, fs
        ))

    doc.build(elements, onFirstPage=on_page, onLaterPages=on_later)


# ── 文本降级 ──────────────────────────────────────────────────────────────
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
            "", "出行清单：身份证 / 医保卡 / 手机 / 钱包",
        ]
    else:
        lines.append("未找到匹配号源，请稍后重试。")
    lines += ["", "=" * 60, "祝您就医顺利！"]
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines))
