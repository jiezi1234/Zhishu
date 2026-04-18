"""
pdf_generator.py — 现代卡片风 PDF 生成器 (v3)

架构：ReportLab Canvas + Platypus 混合
  - 每个信息板块 = 独立 Flowable 子类
  - 页眉/页脚 = onPage 钩子（Canvas 绘制）
  - 圆角卡片背景 = 每个 Flowable.draw() 内调用 canvas.roundRect()

卡片顺序：
  1. 就诊信息（医院/科室/医生/时间/排队）
  2. 路线规划（真实路线+地图链接+出发时间）
  3. 挂号链接（官网+平台+注意事项）
  4. 就医方案（院内导引步骤）
  5. 出行清单（定制化物品清单）
  6. 医院对比表
"""
import os
from datetime import datetime
from typing import List, Dict, Optional

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        SimpleDocTemplate, Spacer, Table,
        TableStyle, Flowable, KeepTogether
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
        'primary':        colors.HexColor('#2563EB'),
        'card_bg':        colors.HexColor('#EFF6FF'),
        'text':           colors.HexColor('#1E293B'),
        'text_secondary': colors.HexColor('#64748B'),
        'divider':        colors.HexColor('#E2E8F0'),
        'white':          colors.white,
        'table_alt':      colors.HexColor('#F8FAFC'),
        'green':          colors.HexColor('#10B981'),
        'orange':         colors.HexColor('#F59E0B'),
    }
else:
    COLORS = {}

# ── 卡片尺寸常量 ──────────────────────────────────────────────────────────
CARD_RADIUS      = 6
CARD_PADDING_H   = 14
CARD_PADDING_V   = 12
CARD_LEFT_BORDER = 3
CARD_SPACING     = 10


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


# ── 工具函数 ──────────────────────────────────────────────────────────────
def draw_rounded_rect(canvas, x, y, w, h, r=CARD_RADIUS,
                      fill_color=None, stroke_color=None):
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
    canvas.saveState()
    canvas.setStrokeColor(color or COLORS['primary'])
    canvas.setLineWidth(CARD_LEFT_BORDER)
    canvas.line(x, y, x, y + h)
    canvas.restoreState()


# ── 页眉/页脚钩子 ─────────────────────────────────────────────────────────
def _make_page_decorators(font_name: str, fs: 'FontSizes', gen_date: str):
    page_w, page_h = A4
    margin_x = 36

    def draw_header_footer(canvas, doc):
        canvas.saveState()
        header_y = page_h - 28
        canvas.setFont(font_name, fs.header_footer)
        canvas.setFillColor(COLORS['primary'])
        canvas.drawString(margin_x, header_y, "智枢 HealthPath")
        canvas.setFillColor(COLORS['text_secondary'])
        canvas.drawRightString(page_w - margin_x, header_y, f"{gen_date} 生成")
        canvas.setStrokeColor(COLORS['divider'])
        canvas.setLineWidth(0.5)
        canvas.line(margin_x, header_y - 6, page_w - margin_x, header_y - 6)
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
    def __init__(self, font_name: str, fs: FontSizes):
        super().__init__()
        self.font_name = font_name
        self.fs = fs
        self._avail_width = 0
        self.hAlign = 'LEFT'  # 设置对齐方式

    def wrap(self, available_width, available_height):
        self._avail_width = available_width
        h = self._content_height() + CARD_PADDING_V * 2
        return available_width, h

    def split(self, available_width, available_height):
        """
        允许卡片在页面底部被分割。
        如果可用高度太小（< 100pt），返回空列表让卡片移到下一页。
        """
        content_h = self._content_height() + CARD_PADDING_V * 2

        # 如果可用高度太小（< 100pt）或者卡片太大放不下，移到下一页
        if available_height < 100 or content_h > available_height:
            return []

        # 卡片能完整放下，不需要分割
        return [self]

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
        self.canv.saveState()
        self.canv.setFont(self.font_name, self.fs.title)
        self.canv.setFillColor(COLORS['primary'])
        y = card_h - CARD_PADDING_V - self.fs.title
        x = CARD_PADDING_H + CARD_LEFT_BORDER + 4
        self.canv.drawString(x, y, title)
        self.canv.restoreState()
        return y

    def _x0(self):
        return CARD_PADDING_H + CARD_LEFT_BORDER + 4


# ── 卡片1：就诊信息 ───────────────────────────────────────────────────────
class InfoCardFlowable(CardFlowable):
    ALL_ROWS = [
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
        self._rows = []
        for label, key in self.ALL_ROWS:
            val = self._get_value_for_filter(key).strip()
            if val and val not in ("—", "None", "未指定"):
                self._rows.append((label, val))

    def _get_value_for_filter(self, key: str) -> str:
        if key == '_department':
            return self.task_params.get('department', '未指定')
        if key == '_doctor':
            return f"{self.rec.get('doctor_name', '')}  {self.rec.get('doctor_title', '')}".strip()
        if key == '_queue':
            q = str(self.rec.get('queue_estimate_min', '—')).strip()
            return f"约 {q} 分钟" if q and q not in ('—', 'None') else '—'
        return str(self.rec.get(key, '—'))

    def _content_height(self) -> float:
        if not self._rows:
            return 0
        return self.fs.title + 8 + len(self._rows) * self._row_h

    def _draw_content(self, card_w: float, card_h: float):
        if not self._rows:
            return
        title_y  = self._draw_title("🏥  就诊信息", card_h)
        x_label  = self._x0()
        x_value  = x_label + 68
        divider_x2 = card_w - CARD_PADDING_H
        y = title_y - 6
        for i, (label, val) in enumerate(self._rows):
            row_bot = y - self._row_h
            self.canv.saveState()
            self.canv.setFont(self.font_name, self.fs.label)
            self.canv.setFillColor(COLORS['text_secondary'])
            self.canv.drawString(x_label, row_bot + 4, label)
            self.canv.setFont(self.font_name, self.fs.body)
            self.canv.setFillColor(COLORS['text'])
            self.canv.drawString(x_value, row_bot + 4, val)
            if i < len(self._rows) - 1:
                self.canv.setStrokeColor(COLORS['divider'])
                self.canv.setLineWidth(0.5)
                self.canv.line(x_label, row_bot, divider_x2, row_bot)
            self.canv.restoreState()
            y = row_bot


# ── 卡片2：路线规划 ───────────────────────────────────────────────────────
class RouteCardFlowable(CardFlowable):
    """真实路线规划卡片：支持多行路线说明（移除地图链接）。"""

    def __init__(self, task_params: Dict, font_name: str, fs: FontSizes):
        super().__init__(font_name, fs)
        self.task_params = task_params
        
        dist = str(task_params.get('route_distance_km', '—')).strip()
        dur = str(task_params.get('route_duration_min', '—')).strip()
        
        all_rows = [
            ('出发时间', str(task_params.get('depart_time', '—')).strip()),
            ('交通方式', str(task_params.get('route_mode', '—')).strip()),
            ('预计距离', f"{dist} km" if dist not in ('', '—', 'None') else '—'),
            ('预计用时', f"{dur} 分钟" if dur not in ('', '—', 'None') else '—'),
            ('路线说明', str(task_params.get('route_description', '—')).strip()),
        ]
        
        self._rows = [(lbl, val) for lbl, val in all_rows if val and val not in ('—', '— km', '— 分钟')]
        self._line_height = fs.body + 6
        self._pad_y = 4
        
        # 预计算布局
        self._layout = []
        self._total_height = 0
        
    def wrap(self, available_width, available_height):
        # 提前计算布局，因为需要知道可获得的宽度
        self._avail_width = available_width
        self._calc_layout(available_width)
        h = self._content_height() + CARD_PADDING_V * 2
        return available_width, h

    def _calc_layout(self, w: float):
        from reportlab.pdfbase.pdfmetrics import stringWidth
        self._layout = []
        self._total_height = self.fs.title + 8
        x_value = self._x0() + 68
        max_w = w - x_value - CARD_PADDING_H
        
        for i, (label, val) in enumerate(self._rows):
            lines = []
            curr = ""
            for char in val:
                t = curr + char
                if stringWidth(t, self.font_name, self.fs.body) <= max_w:
                    curr = t
                else:
                    if curr: lines.append(curr)
                    curr = char
            if curr:
                lines.append(curr)
            if not lines:
                lines = [""]
            
            row_h = self._pad_y * 2 + len(lines) * self._line_height
            self._layout.append((label, lines, row_h))
            self._total_height += row_h

    def _content_height(self) -> float:
        if not self._rows:
            return 0
        return self._total_height

    def _draw_content(self, card_w: float, card_h: float):
        if not self._rows:
            return
        title_y    = self._draw_title("🚗  路线规划", card_h)
        x_label    = self._x0()
        x_value    = x_label + 68
        divider_x2 = card_w - CARD_PADDING_H
        y = title_y - 6
        
        for i, (label, lines, row_h) in enumerate(self._layout):
            row_bot = y - row_h
            self.canv.saveState()
            
            # Label
            self.canv.setFont(self.font_name, self.fs.label)
            self.canv.setFillColor(COLORS['text_secondary'])
            # 对齐上方
            self.canv.drawString(x_label, y - self._pad_y - self.fs.label, label)
            
            # Value
            self.canv.setFont(self.font_name, self.fs.body)
            self.canv.setFillColor(COLORS['text'])
            for j, line in enumerate(lines):
                ly = y - self._pad_y - self.fs.body - (j * self._line_height)
                self.canv.drawString(x_value, ly, line)
                
            # Divider
            if i < len(self._layout) - 1:
                self.canv.setStrokeColor(COLORS['divider'])
                self.canv.setLineWidth(0.5)
                self.canv.line(x_label, row_bot, divider_x2, row_bot)
                
            self.canv.restoreState()
            y = row_bot


# ── 卡片3：挂号链接 ───────────────────────────────────────────────────────
class RegistrationCardFlowable(CardFlowable):
    """挂号官网、平台、注意事项 + 挂号指导步骤。"""

    def __init__(self, task_params: Dict, font_name: str, fs: FontSizes):
        super().__init__(font_name, fs)
        self.task_params = task_params

        # 基本信息行
        all_rows = [
            ('挂号平台', task_params.get('registration_platform', '')),
            ('官网/链接', task_params.get('registration_url', '')),
            ('注意事项', task_params.get('booking_note', '')),
            ('医院地址', task_params.get('hospital_address', '')),
        ]
        self._rows = [(label, value) for label, value in all_rows if value and value != '—']
        self._row_h = fs.body + 10

        self._layout = []
        self._total_height = 0

    def wrap(self, available_width, available_height):
        self._avail_width = available_width
        self._calc_layout(available_width)
        h = self._content_height() + CARD_PADDING_V * 2
        return available_width, h

    def _calc_layout(self, w: float):
        from reportlab.pdfbase.pdfmetrics import stringWidth
        self._layout = []
        self._total_height = self.fs.title + 8
        x_value = self._x0() + 68
        max_w = w - x_value - CARD_PADDING_H

        for label, val in self._rows:
            lines = []
            curr = ""
            for char in val:
                t = curr + char
                if stringWidth(t, self.font_name, self.fs.body) <= max_w:
                    curr = t
                else:
                    if curr: lines.append(curr)
                    curr = char
            if curr:
                lines.append(curr)
            if not lines:
                lines = [""]
            
            row_h = 4 * 2 + len(lines) * (self.fs.body + 6)
            self._layout.append((label, lines, row_h))
            self._total_height += row_h

    def _content_height(self) -> float:
        if not self._rows:
            return 0
        return self._total_height

    def _draw_content(self, card_w: float, card_h: float):
        if not self._rows:
            return
        title_y = self._draw_title("🔗  挂号信息", card_h)
        x_label = self._x0()
        x_value = x_label + 68
        divider_x2 = card_w - CARD_PADDING_H
        y = title_y - 6

        pad_y = 4
        # 绘制基本信息
        for i, (label, lines, row_h) in enumerate(self._layout):
            row_bot = y - row_h
            self.canv.saveState()
            self.canv.setFont(self.font_name, self.fs.label)
            self.canv.setFillColor(COLORS['text_secondary'])
            self.canv.drawString(x_label, y - pad_y - self.fs.label, label)
            
            # 链接用蓝色
            if label == '官网/链接':
                self.canv.setFillColor(COLORS['primary'])
            else:
                self.canv.setFillColor(COLORS['text'])
                
            self.canv.setFont(self.font_name, self.fs.body)
            for j, line in enumerate(lines):
                ly = y - pad_y - self.fs.body - (j * (self.fs.body + 6))
                self.canv.drawString(x_value, ly, line)
                
            if i < len(self._layout) - 1:
                self.canv.setStrokeColor(COLORS['divider'])
                self.canv.setLineWidth(0.5)
                self.canv.line(x_label, row_bot, divider_x2, row_bot)
            self.canv.restoreState()
            y = row_bot


class RegistrationGuideCardFlowable(CardFlowable):
    """挂号指导步骤卡片"""

    def __init__(self, task_params: Dict, font_name: str, fs: FontSizes):
        super().__init__(font_name, fs)
        self.task_params = task_params
        
        reg_url = task_params.get('registration_url', '')
        if reg_url:
            self._guide_steps = [
                "📱 线上挂号：打开上方链接 → 注册登录 → 选择科室医生 → 预约时间 → 支付",
                "🏥 现场挂号：携带身份证医保卡 → 挂号窗口/自助机 → 告知科室",
            ]
        else:
            self._guide_steps = [
                "📱 线上挂号：微信搜索「京医通」或「健康广东」→ 搜索医院 → 预约",
                "🏥 现场挂号：携带身份证医保卡 → 挂号窗口/自助机 → 告知科室",
                "☎️ 电话预约：拨打医院预约电话（官网查询）→ 按提示选择",
            ]
            
        self._row_h = fs.body + 9

    def _wrap_text(self, text: str, max_width: float) -> list:
        from reportlab.pdfbase.pdfmetrics import stringWidth
        lines = []
        words = text
        current_line = ""

        for char in words:
            test_line = current_line + char
            width = stringWidth(test_line, self.font_name, self.fs.body - 1)
            if width <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = char

        if current_line:
            lines.append(current_line)

        return lines if lines else [text]

    def _content_height(self) -> float:
        if not self._guide_steps:
            return 0
        total_lines = 0
        max_width = 400
        for step in self._guide_steps:
            if not step: continue
            lines = self._wrap_text(step, max_width)
            total_lines += len(lines)
        return self.fs.title + 8 + total_lines * self._row_h

    def _draw_content(self, card_w: float, card_h: float):
        if not self._guide_steps: return
        title_y = self._draw_title("🧭  挂号指导", card_h)
        x0      = self._x0()
        max_width = card_w - x0 - CARD_PADDING_H
        y = title_y - 6

        for step in self._guide_steps:
            if not step: continue
            lines = self._wrap_text(step, max_width)
            
            self.canv.saveState()
            # 首行如果是标题带 emoji 的可以加粗着色
            if step.startswith(('📱', '🏥', '☎️')):
                self.canv.setFillColor(COLORS['text'])
                self.canv.setFont(self.font_name, self.fs.body)
            else:
                self.canv.setFillColor(COLORS['text_secondary'])
                self.canv.setFont(self.font_name, self.fs.body - 1)
                
            for i, line in enumerate(lines):
                row_bot = y - self._row_h
                ly = row_bot + 4
                self.canv.drawString(x0, ly, line)
                y = row_bot
            self.canv.restoreState()


# ── 卡片4：就医方案（院内导引） ───────────────────────────────────────────
class NavStepsCardFlowable(CardFlowable):
    """院内导引步骤卡片，每步一行，支持自动换行。"""

    def __init__(self, nav_steps: list, font_name: str, fs: FontSizes, title: str = "📋  就医方案"):
        super().__init__(font_name, fs)
        self.nav_steps = nav_steps or ['请按医院指示牌前往对应科室。']
        self._row_h = fs.body + 9
        self.title = title

    def _wrap_text(self, text: str, max_width: float) -> list:
        """将长文本按宽度拆分成多行"""
        from reportlab.pdfbase.pdfmetrics import stringWidth
        lines = []
        words = text
        current_line = ""

        for char in words:
            test_line = current_line + char
            width = stringWidth(test_line, self.font_name, self.fs.body)
            if width <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = char

        if current_line:
            lines.append(current_line)

        return lines if lines else [text]

    def _content_height(self) -> float:
        # 计算所有步骤展开后的总高度
        total_lines = 0
        max_width = 400  # 估算可用宽度
        for step in self.nav_steps:
            lines = self._wrap_text(step, max_width)
            total_lines += len(lines)
        return self.fs.title + 8 + total_lines * self._row_h

    def _draw_content(self, card_w: float, card_h: float):
        title_y = self._draw_title(self.title, card_h)
        x0      = self._x0()
        max_width = card_w - x0 - CARD_PADDING_H
        y = title_y - 6

        for step in self.nav_steps:
            lines = self._wrap_text(step, max_width)
            for line in lines:
                row_bot = y - self._row_h
                self.canv.saveState()
                self.canv.setFont(self.font_name, self.fs.body)
                self.canv.setFillColor(COLORS['text'])
                self.canv.drawString(x0, row_bot + 4, line)
                self.canv.restoreState()
                y = row_bot


# ── 卡片5：出行清单（定制化） ─────────────────────────────────────────────
class ChecklistCardFlowable(CardFlowable):
    """出行物品清单，支持从 task_params 传入定制化列表。"""

    DEFAULT_CHECKLIST = [
        '□  身份证（千万别忘了）',
        '□  医保卡 / 社保卡',
        '□  手机 & 充电宝',
        '□  钱包 / 支付宝',
    ]

    def __init__(self, task_params: Dict, font_name: str, fs: FontSizes):
        super().__init__(font_name, fs)
        raw = task_params.get('checklist', [])
        if raw and isinstance(raw, list):
            # checklist 是 [{'item': ..., 'note': ...}] 格式
            if isinstance(raw[0], dict):
                self.items = []
                for d in raw:
                    note = f"  —— {d['note']}" if d.get('note') else ''
                    self.items.append(f"□  {d['item']}{note}")
            else:
                self.items = [f"□  {s}" for s in raw]
        else:
            self.items = self.DEFAULT_CHECKLIST
        self._row_h = fs.body + 9

    def _content_height(self) -> float:
        return self.fs.title + 8 + len(self.items) * self._row_h

    def _draw_content(self, card_w: float, card_h: float):
        title_y   = self._draw_title("🎒  出行清单", card_h)
        x0        = self._x0()
        max_chars = int((card_w - x0 - CARD_PADDING_H) / (self.fs.body * 0.62)) or 30
        y = title_y - 6
        for item in self.items:
            row_bot = y - self._row_h
            self.canv.saveState()
            self.canv.setFont(self.font_name, self.fs.body)
            self.canv.setFillColor(COLORS['text'])
            display = item[:max_chars] + ('…' if len(item) > max_chars else '')
            self.canv.drawString(x0, row_bot + 4, display)
            self.canv.restoreState()
            y = row_bot


# ── 卡片6：医院对比表 ─────────────────────────────────────────────────────
class TableCardFlowable(CardFlowable):
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
        self._draw_title("📊  医院对比", card_h)
        title_h   = self.fs.title + 8
        x         = self._x0()
        table_w   = card_w - x - CARD_PADDING_H
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


# ── 主入口 ────────────────────────────────────────────────────────────────
def generate_pdf_document(recommendations: List[Dict], task_params: Dict,
                          output_path: str, large_font: bool = False):
    """
    生成现代卡片风就医行程单 PDF。
    接口与旧版保持完全一致，output_generator.py 无需修改。

    卡片顺序：就诊信息 → 路线规划 → 挂号信息 → 就医方案 → 出行清单 → 医院对比
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

        # 卡片1：就诊信息
        elements.append(InfoCardFlowable(rec, task_params, font_name, fs))
        elements.append(Spacer(1, CARD_SPACING))

        # 卡片2：路线规划（真实路线数据）
        elements.append(RouteCardFlowable(task_params, font_name, fs))
        elements.append(Spacer(1, CARD_SPACING))

        # 卡片3：挂号链接基本信息
        reg_card = RegistrationCardFlowable(task_params, font_name, fs)
        if reg_card._rows:
            elements.append(reg_card)
            elements.append(Spacer(1, CARD_SPACING))

        # 卡片3.5：挂号指导步骤
        reg_guide_card = RegistrationGuideCardFlowable(task_params, font_name, fs)
        if reg_guide_card._guide_steps:
            elements.append(reg_guide_card)
            elements.append(Spacer(1, CARD_SPACING))

        # 卡片4：就医方案（院内导引） - 切分成小块防止被截断推到下一页
        nav_steps = task_params.get('nav_steps', [])
        if not nav_steps:
            elements.append(NavStepsCardFlowable([], font_name, fs))
            elements.append(Spacer(1, CARD_SPACING))
        else:
            step_chunks = [nav_steps[i:i + 6] for i in range(0, len(nav_steps), 6)]
            for i, chunk in enumerate(step_chunks):
                title = "📋  就医方案" if i == 0 else "📋  就医方案 (接上)"
                elements.append(NavStepsCardFlowable(chunk, font_name, fs, title))
                elements.append(Spacer(1, CARD_SPACING))

        # 卡片5：出行清单（定制化）
        elements.append(ChecklistCardFlowable(task_params, font_name, fs))

    else:
        elements.append(_empty_card(font_name, fs))

    doc.build(elements, onFirstPage=on_page, onLaterPages=on_later)


def _empty_card(font_name, fs):
    from reportlab.platypus import Flowable

    class _Msg(Flowable):
        def wrap(self, w, h):
            self._w = w
            return w, 60
        def draw(self):
            draw_rounded_rect(self.canv, 0, 0, self._w, 60, fill_color=COLORS['card_bg'])
            self.canv.setFont(font_name, fs.body)
            self.canv.setFillColor(COLORS['text_secondary'])
            self.canv.drawCentredString(self._w / 2, 22,
                "未找到符合条件的号源，请稍后重试，或尝试放宽科室和时间条件。")
    return _Msg()


# ── 文本降级 ──────────────────────────────────────────────────────────────
def _generate_text_fallback(recommendations: List[Dict],
                             task_params: Dict, output_path: str):
    lines = ["就医行程单", "=" * 60, ""]
    if recommendations:
        r = recommendations[0]
        lines += [
            f"医院：{r.get('hospital_name', '—')}",
            f"科室：{task_params.get('department', '—')}",
            f"医生：{r.get('doctor_name', '')} {r.get('doctor_title', '')}",
            f"时间：{r.get('appointment_time', '—')}",
            "",
            f"出发时间：{task_params.get('depart_time', '—')}",
            f"路线：{task_params.get('route_description', '—')}",
            f"导航：{task_params.get('route_map_url', '—')}",
            "",
            f"挂号平台：{task_params.get('registration_platform', '—')}",
            f"挂号链接：{task_params.get('registration_url', '—')}",
            f"注意事项：{task_params.get('booking_note', '—')}",
            "",
            "出行清单：身份证 / 医保卡 / 手机 / 钱包",
        ]
    else:
        lines.append("未找到匹配号源，请稍后重试。")
    lines += ["", "=" * 60, "祝您就医顺利！"]
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines))
