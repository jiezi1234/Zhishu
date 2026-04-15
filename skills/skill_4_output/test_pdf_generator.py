"""
Tests for redesigned pdf_generator.py
Run: python -m pytest skills/skill_4_output/test_pdf_generator.py -v
"""
import sys, os
# 只插入 skill 目录，让系统 Python 的 reportlab 优先（不插入 lib/）
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


# ── Task 2 ────────────────────────────────────────────────────────────────
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


# ── Task 3 ────────────────────────────────────────────────────────────────
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


# ── Task 4 ────────────────────────────────────────────────────────────────
def test_parse_appointment_time():
    from pdf_generator import _parse_appointment_time
    from datetime import datetime
    dt = _parse_appointment_time("2026-04-15 09:00")
    assert dt == datetime(2026, 4, 15, 9, 0)

def test_parse_appointment_time_fallback():
    from pdf_generator import _parse_appointment_time
    result = _parse_appointment_time("invalid_time")
    assert result is not None

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


# ── Task 5 ────────────────────────────────────────────────────────────────
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


# ── Task 6 ────────────────────────────────────────────────────────────────
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


# ── Task 7 ────────────────────────────────────────────────────────────────
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
    assert os.path.exists(out)
    assert os.path.getsize(out) > 1000

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
    assert os.path.exists(out)
    assert os.path.getsize(out) > 1000

def test_generate_pdf_document_empty_recs(tmp_path):
    from pdf_generator import generate_pdf_document
    out = str(tmp_path / "test_empty.pdf")
    generate_pdf_document([], {}, out, large_font=False)
    assert os.path.exists(out)
