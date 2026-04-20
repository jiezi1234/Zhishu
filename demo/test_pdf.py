import os
import sys

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
skill_dir = os.path.join(base_dir, 'skills', 'healthpath-itinerary-builder')
sys.path.append(skill_dir)

from pdf_generator import generate_pdf_document

dummy_rec = [{
    'hospital_name': '测试医院',
    'doctor_name': '李医生',
    'doctor_title': '主任医师',
    'appointment_time': '2026-04-18 上午',
    'total_cost': 50,
    'queue_estimate_min': 30,
    'distance_km': 5,
    'score': 9.5
}]

dummy_params = {
    'department': '内科',
    'depart_time': '08:00',
    'route_distance_km': 10,
    'route_duration_min': 40,
    'route_mode': '公交',
    'route_description': '乘坐游1路从人民广场到市立医院',
    'registration_platform': '微信公众号',
    'registration_url': 'http://example.com/register/1234567890/this-is-a-very-long-url-that-might-not-wrap-properly-and-could-be-truncated-if-not-handled-correctly',
    'booking_note': '需提前30分钟到达',
    'hospital_address': '北京市朝阳区某某路1号',
    'nav_steps': ['1. 进门左转', '2. 上二楼', '3. 找到内科门诊'],
    'checklist': ['身份证', '医保卡', '水']
}

out_path = os.path.join(os.path.dirname(__file__), 'test_output.pdf')
generate_pdf_document(dummy_rec, dummy_params, out_path)
print(f"Generated PDF at {out_path}")
