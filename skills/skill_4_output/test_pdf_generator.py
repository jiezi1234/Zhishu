"""
Tests for pdf_generator.py v3
Run: python -m pytest skills/skill_4_output/test_pdf_generator.py -v
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))


# ── Task 1: 基础 ──────────────────────────────────────────────────────────
def test_register_chinese_fonts_returns_name():
    from pdf_generator import register_chinese_fonts
    font_name = register_chinese_fonts()
    assert font_name is not None, "未找到中文字体"
    assert isinstance(font_name, str)

def test_colors_defined():
    from pdf_generator import COLORS
    required = ['primary', 'card_bg', 'text', 'text_secondary', 'divider', 'white']
    for key in required:
        assert key in COLORS, f"COLORS 缺少 '{key}'"

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


# ── Task 2: InfoCardFlowable ──────────────────────────────────────────────
def test_info_card_flowable_wrap():
    from pdf_generator import InfoCardFlowable, FontSizes, register_chinese_fonts
    font = register_chinese_fonts()
    if font is None:
        import pytest; pytest.skip("No Chinese font")
    rec  = {'hospital_name': '北京协和医院', 'doctor_name': '张医生',
            'doctor_title': '主任医师', 'appointment_time': '2026-04-20 09:00',
            'queue_estimate_min': 30}
    task = {'department': '骨科'}
    card = InfoCardFlowable(rec, task, font, FontSizes(False))
    w, h = card.wrap(400, 600)
    assert w == 400 and h > 0


# ── Task 3: RouteCardFlowable ─────────────────────────────────────────────
def test_route_card_flowable_wrap():
    from pdf_generator import RouteCardFlowable, FontSizes, register_chinese_fonts
    font = register_chinese_fonts()
    if font is None:
        import pytest; pytest.skip("No Chinese font")
    task = {
        'depart_time': '04月20日 07:30 出发',
        'route_mode': '公共交通',
        'route_duration_min': '30',
        'route_distance_km': '5.2',
        'route_description': '乘坐地铁4号线至西直门站',
        'route_map_url': 'https://map.baidu.com/dir/?origin=北京师范大学&destination=北京协和医院',
    }
    card = RouteCardFlowable(task, font, FontSizes(False))
    w, h = card.wrap(400, 600)
    assert w == 400 and h > 0


# ── Task 4: RegistrationCardFlowable ─────────────────────────────────────
def test_registration_card_flowable_wrap():
    from pdf_generator import RegistrationCardFlowable, FontSizes, register_chinese_fonts
    font = register_chinese_fonts()
    if font is None:
        import pytest; pytest.skip("No Chinese font")
    task = {
        'registration_platform': '京医通',
        'registration_url': 'https://www.jingytong.com/hospital/pkuh6',
        'booking_note': '提前在微信小程序预约',
        'hospital_address': '海淀区花园北路51号',
    }
    card = RegistrationCardFlowable(task, font, FontSizes(False))
    w, h = card.wrap(400, 600)
    assert w == 400 and h > 0


# ── Task 5: NavStepsCardFlowable ──────────────────────────────────────────
def test_nav_steps_card_flowable_wrap():
    from pdf_generator import NavStepsCardFlowable, FontSizes, register_chinese_fonts
    font = register_chinese_fonts()
    if font is None:
        import pytest; pytest.skip("No Chinese font")
    steps = ['第一步：进入大厅取号', '第二步：前往2楼骨科候诊区', '第三步：签到等候叫号']
    card = NavStepsCardFlowable(steps, font, FontSizes(False))
    w, h = card.wrap(400, 600)
    assert w == 400 and h > 0


# ── Task 6: ChecklistCardFlowable ────────────────────────────────────────
def test_checklist_card_default():
    from pdf_generator import ChecklistCardFlowable, FontSizes, register_chinese_fonts
    font = register_chinese_fonts()
    if font is None:
        import pytest; pytest.skip("No Chinese font")
    card = ChecklistCardFlowable({}, font, FontSizes(False))
    w, h = card.wrap(400, 600)
    assert w == 400 and h > 0

def test_checklist_card_custom():
    from pdf_generator import ChecklistCardFlowable, FontSizes, register_chinese_fonts
    font = register_chinese_fonts()
    if font is None:
        import pytest; pytest.skip("No Chinese font")
    task = {'checklist': [
        {'item': '身份证', 'note': '千万别忘了'},
        {'item': '医保卡', 'note': ''},
        {'item': '老花镜', 'note': ''},
    ]}
    card = ChecklistCardFlowable(task, font, FontSizes(False))
    w, h = card.wrap(400, 600)
    assert w == 400 and h > 0


# ── Task 7: TableCardFlowable ─────────────────────────────────────────────
def test_table_card_flowable_wrap():
    from pdf_generator import TableCardFlowable, FontSizes, register_chinese_fonts
    font = register_chinese_fonts()
    if font is None:
        import pytest; pytest.skip("No Chinese font")
    recs = [{'rank': 1, 'hospital_name': '协和', 'doctor_name': '张医生',
             'doctor_title': '主任', 'appointment_time': '09:00',
             'total_cost': 100, 'queue_estimate_min': 30,
             'distance_km': 2.5, 'score': 8.5}]
    card = TableCardFlowable(recs, font, FontSizes(False))
    w, h = card.wrap(400, 600)
    assert w == 400 and h > 0


# ── Task 8: generate_pdf_document 端到端 ─────────────────────────────────
def _make_test_task():
    return {
        'department': '骨科', 'symptom': '腰疼',
        'time_window': '本周', 'travel_preference': '均衡',
        'depart_time': '04月20日 07:30 出发',
        'route_mode': '公共交通',
        'route_duration_min': '30',
        'route_distance_km': '5.2',
        'route_description': '乘坐地铁前往',
        'route_map_url': 'https://map.baidu.com/dir/?origin=望京&destination=协和医院',
        'registration_platform': '京医通',
        'registration_url': 'https://www.jingytong.com/hospital/pkuh6',
        'booking_note': '提前在微信小程序预约',
        'hospital_address': '东城区帅府园1号',
        'nav_steps': ['第一步：大厅取号', '第二步：2楼骨科签到'],
        'checklist': [{'item': '身份证', 'note': ''}, {'item': '医保卡', 'note': ''}],
    }

def _make_test_recs():
    return [{'rank': 1, 'hospital_name': '北京协和医院', 'doctor_name': '张医生',
             'doctor_title': '主任医师', 'appointment_time': '2026-04-20 09:00',
             'total_cost': 100, 'total_travel_time_min': 30,
             'distance_km': 2.5, 'queue_estimate_min': 30,
             'score': 8.5, 'reason': '距离近，排队短'}]

def test_generate_pdf_document_creates_file(tmp_path):
    from pdf_generator import generate_pdf_document
    out = str(tmp_path / "test_output.pdf")
    generate_pdf_document(_make_test_recs(), _make_test_task(), out, large_font=False)
    assert os.path.exists(out)
    assert os.path.getsize(out) > 1000

def test_generate_pdf_document_large_font(tmp_path):
    from pdf_generator import generate_pdf_document
    out = str(tmp_path / "test_large.pdf")
    generate_pdf_document(_make_test_recs(), _make_test_task(), out, large_font=True)
    assert os.path.exists(out)
    assert os.path.getsize(out) > 1000

def test_generate_pdf_document_empty_recs(tmp_path):
    from pdf_generator import generate_pdf_document
    out = str(tmp_path / "test_empty.pdf")
    generate_pdf_document([], {}, out, large_font=False)
    assert os.path.exists(out)
