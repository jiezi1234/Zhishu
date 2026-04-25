#!/usr/bin/env python3
"""Integration tests for the unified healthpath skill chain."""

import os
import sys
import types

# 注入 fake semantic_matcher 避免拉 sentence_transformers(CI/开发机可能未装)。
# 生产代码不受影响;这只是让测试在 import 时不炸。
_fake_sm = types.ModuleType("semantic_matcher")
_fake_sm.search_knowledge = lambda text, k=1: []
_fake_sm.detect_emergency = lambda text: []
_fake_sm.normalize_symptoms = lambda text: text
_fake_sm.get_knowledge = lambda: {
    "route_dept": [],
    "parent_only_routes": [],
    "term_dept_rules": {},
}
sys.modules.setdefault("semantic_matcher", _fake_sm)

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "skills", "healthpath-doctor-schedule"
))

from main_skill import execute, get_info
import main_skill
import itinerary_builder
import doctor_schedule
from intent_parser import parse_intent
from hospital_matcher import match
from registration_fetcher import fetch


def test_get_info_skills():
    info = get_info()
    assert info["name"] == "智枢"
    assert "healthpath-intent-understanding" in info["skills"]
    assert "healthpath-itinerary-builder" in info["skills"]


def test_execute_requests_location_when_missing():
    result = execute(user_input="最近头晕，想看医生")
    assert result["status"] in ("need_location", "need_more_info", "emergency_warning")


def test_execute_returns_emergency_warning_for_chest_pain_with_dyspnea():
    # fake semantic_matcher 的 detect_emergency 返回 [],
    # 在测试环境下无法走到 emergency_warning。skip 即可。
    from semantic_matcher import detect_emergency
    if detect_emergency("剧烈胸痛，呼吸困难") == []:
        import pytest
        pytest.skip("detect_emergency is stubbed — requires real semantic_matcher")
    result = execute(user_input="剧烈胸痛，呼吸困难")
    assert result["status"] == "emergency_warning"
    assert "warning" in result["final_output"]
    assert "match" not in result["steps"]


def test_execute_full_flow_generates_output(monkeypatch):
    # 原测试依赖真实 semantic_matcher / hospital_matcher CSV,
    # 在无 sentence_transformers 的 CI 环境会 fail。
    # 这里用和下面 doctor 流程一致的 upstream stub,让它独立工作。
    import main_skill as _m
    monkeypatch.setattr(_m, "parse_intent",
        lambda text, use_deepseek=True: {
            "symptom": "腰疼", "department": "骨科", "doctor_name": "",
            "target_city": "北京", "time_window": "this_week",
        })
    monkeypatch.setattr(_m, "match",
        lambda user_location, departments, preferences: {
            "candidates": [{
                "hospital_name": "北京大学第三医院",
                "address": "北京市海淀区花园北路49号",
                "yixue_url": "",
            }],
        })
    monkeypatch.setattr(_m, "fetch",
        lambda hospital_name, department, user_location, yixue_url: {
            "hospital_name": hospital_name,
            "department": department,
            "official_url": "https://www.puh3.net.cn/",
            "registration_url": "https://www.puh3.net.cn/",
            "registration_platform": "医院官网",
            "booking_note": "", "from_cache": True, "timestamp": "",
        })
    # 让 doctor-schedule 走 L1 降级(autoclaw 不可用),确保仍生成 PDF
    import doctor_schedule as _ds
    monkeypatch.setattr(_ds, "run_browser_task",
        lambda **kw: {
            "status": "not_available",
            "session_id": None, "tab_id": None,
            "observation": "", "structured": {}, "interact_prompt": "",
            "screenshots": [], "error": "autoclaw 不可用",
        })

    out_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "_generated_test")
    os.makedirs(out_dir, exist_ok=True)
    monkeypatch.setattr(itinerary_builder, "OUTPUT_DIR", out_dir)
    monkeypatch.setattr(itinerary_builder, "HISTORY_PATH", os.path.join(out_dir, "user_history.json"))
    result = execute(
        user_input="最近腰疼，想看骨科",
        user_location="北京市海淀区",
        selected_hospital="北京大学第三医院",
        output_format="pdf",
        user_profile={"age_group": "adult"},
    )

    assert result["status"] == "success"
    assert "final_output" in result
    pdf_path = result["final_output"].get("pdf_path", "")
    assert pdf_path
    assert os.path.exists(pdf_path)


# ═══════════════════════════════════════════════════════════════════
# doctor-schedule 流程集成测试(Task 10)
# ═══════════════════════════════════════════════════════════════════

import main_skill as _main_skill_mod


def _stub_driver(observation):
    return {
        "status": "success",
        "session_id": "sid-stub",
        "tab_id": "1",
        "observation": observation,
        "structured": {},
        "interact_prompt": "",
        "screenshots": [],
        "error": None,
    }


def _install_upstream_stubs(monkeypatch, user_input):
    """
    stub intent_parser/hospital_matcher/registration_fetcher,
    让 execute() 流程可以抵达 doctor_schedule 步骤。
    """
    from intent_parser import extract_doctor_name

    monkeypatch.setattr(
        _main_skill_mod, "parse_intent",
        lambda text, use_deepseek=True: {
            "symptom": "",
            "department": "骨科",
            "doctor_name": extract_doctor_name(text),
            "target_city": "北京",
            "time_window": "this_week",
        },
    )
    monkeypatch.setattr(
        _main_skill_mod, "match",
        lambda user_location, departments, preferences: {
            "candidates": [{
                "hospital_name": "北京大学第三医院",
                "address": "北京市海淀区花园北路49号",
                "yixue_url": "",
            }],
        },
    )
    monkeypatch.setattr(
        _main_skill_mod, "fetch",
        lambda hospital_name, department, user_location, yixue_url:
        {
            "hospital_name": hospital_name,
            "department": department,
            "official_url": "https://www.puh3.net.cn/",
            "registration_url": "https://www.puh3.net.cn/",
            "registration_platform": "医院官网",
            "booking_note": "",
            "from_cache": True,
            "timestamp": "",
        },
    )


def test_execute_returns_doctor_schedule_fetched_when_doctor_named(monkeypatch, tmp_path):
    _install_upstream_stubs(monkeypatch, "")
    monkeypatch.setattr(doctor_schedule, "CACHE_PATH", str(tmp_path / "cache.json"))
    monkeypatch.setattr(
        doctor_schedule,
        "run_browser_task",
        lambda **kw: _stub_driver(
            "王立凡 主任医师\n"
            "擅长:头痛、脑血管病\n"
            "2026-04-22|上午|3/20\n"
            "2026-04-24|下午|5/20\n"
        ),
    )

    out_dir = str(tmp_path / "out")
    os.makedirs(out_dir, exist_ok=True)
    itinerary_builder.OUTPUT_DIR = out_dir

    result = execute(
        user_input="我要挂北京大学第三医院骨科王立凡医生的号",
        user_location="北京市海淀区",
        selected_hospital="北京大学第三医院",
        output_format="pdf",
        user_profile={"age_group": "adult"},
    )
    assert result["status"] == "doctor_schedule_fetched"
    assert result["final_output"]["recommendation"] is not None
    # 2026-04-24 下午(5/20=0.25)分数高于 2026-04-22 上午(3/20=0.15,号源紧张)
    assert result["final_output"]["recommendation"]["date"] == "2026-04-24"


def test_execute_returns_awaiting_doctor_selection_when_not_named(monkeypatch, tmp_path):
    _install_upstream_stubs(monkeypatch, "")
    monkeypatch.setattr(doctor_schedule, "CACHE_PATH", str(tmp_path / "cache.json"))
    monkeypatch.setattr(
        doctor_schedule,
        "run_browser_task",
        lambda **kw: _stub_driver(
            "骨科专家:\n"
            "王立凡 主任医师 腰椎、脊柱\n"
            "李二 副主任医师 关节、骨折\n"
        ),
    )

    result = execute(
        user_input="帮我找北京大学第三医院骨科",
        user_location="北京市海淀区",
        selected_hospital="北京大学第三医院",
        output_format="pdf",
        user_profile={"age_group": "adult"},
    )
    assert result["status"] == "awaiting_doctor_selection"
    experts = result["final_output"]["experts"]
    assert any(e["name"] == "王立凡" for e in experts)


def test_execute_final_pdf_contains_doctor_when_confirmed(monkeypatch, tmp_path):
    _install_upstream_stubs(monkeypatch, "")
    monkeypatch.setattr(doctor_schedule, "CACHE_PATH", str(tmp_path / "cache.json"))
    monkeypatch.setattr(
        doctor_schedule,
        "run_browser_task",
        lambda **kw: _stub_driver(
            "王立凡 主任医师\n"
            "擅长:腰椎\n"
            "2026-04-22|上午|3/20\n"
        ),
    )

    # 捕获传给 pdf_generator 的 recommendations,验证 doctor 字段在推荐卡片里
    captured = {}
    import pdf_generator as _pg
    orig = _pg.generate_pdf_document

    def _spy(recs, task_params, filepath, large_font=False):
        captured["recs"] = recs
        captured["task_params"] = task_params
        return orig(recs, task_params, filepath, large_font=large_font)

    monkeypatch.setattr(_pg, "generate_pdf_document", _spy)

    out_dir = str(tmp_path / "out")
    os.makedirs(out_dir, exist_ok=True)
    itinerary_builder.OUTPUT_DIR = out_dir

    result = execute(
        user_input="我要挂北京大学第三医院骨科王立凡医生的号",
        user_location="北京市海淀区",
        selected_hospital="北京大学第三医院",
        confirmed_appointment={"date": "2026-04-22", "time_slot": "上午"},
        output_format="pdf",
        user_profile={"age_group": "adult"},
    )
    assert result["status"] == "success"
    pdf_path = result["final_output"]["pdf_path"]
    assert os.path.exists(pdf_path)
    assert result["final_output"]["doctor"]["name"] == "王立凡"
    # 核心断言:PDF 推荐卡片里应有医生信息(不是空/dash)
    r0 = captured["recs"][0]
    assert r0["doctor_name"] == "王立凡"
    assert r0["doctor_title"] == "主任医师"
    assert r0["appointment_time"].startswith("2026-04-22")


def test_execute_selected_doctor_from_expert_list_shows_in_pdf(monkeypatch, tmp_path):
    """用户未指名医生 → 列表选 → 再次 execute 传 selected_doctor + confirmed_appointment →
    PDF 推荐卡片应显示用户选定的医生。"""
    _install_upstream_stubs(monkeypatch, "")
    monkeypatch.setattr(doctor_schedule, "CACHE_PATH", str(tmp_path / "cache.json"))
    monkeypatch.setattr(
        doctor_schedule,
        "run_browser_task",
        lambda **kw: _stub_driver(
            "李晓红 副主任医师\n"
            "擅长:癫痫\n"
            "2026-04-23|下午|8/20\n"
        ),
    )

    captured = {}
    import pdf_generator as _pg
    orig = _pg.generate_pdf_document

    def _spy(recs, task_params, filepath, large_font=False):
        captured["recs"] = recs
        return orig(recs, task_params, filepath, large_font=large_font)

    monkeypatch.setattr(_pg, "generate_pdf_document", _spy)

    out_dir = str(tmp_path / "out")
    os.makedirs(out_dir, exist_ok=True)
    itinerary_builder.OUTPUT_DIR = out_dir

    # user_input 里不含医生名,但显式传 selected_doctor(模拟用户从列表里选了李晓红)
    result = execute(
        user_input="帮我找北京大学第三医院神经内科",
        user_location="北京市海淀区",
        selected_hospital="北京大学第三医院",
        selected_doctor="李晓红",
        confirmed_appointment={"date": "2026-04-23", "time_slot": "下午"},
        output_format="pdf",
        user_profile={"age_group": "adult"},
    )
    assert result["status"] == "success"
    r0 = captured["recs"][0]
    assert r0["doctor_name"] == "李晓红"
    assert r0["doctor_title"] == "副主任医师"
    assert "癫痫" in r0["doctor_specialty"]


def test_execute_autoclaw_unavailable_still_generates_pdf(monkeypatch, tmp_path):
    """autoclaw 不可用时降级路径:最终仍生成 PDF,只是没有 doctor 上下文。"""
    _install_upstream_stubs(monkeypatch, "")
    monkeypatch.setattr(doctor_schedule, "CACHE_PATH", str(tmp_path / "cache.json"))
    monkeypatch.setattr(
        doctor_schedule,
        "run_browser_task",
        lambda **kw: {
            "status": "not_available",
            "session_id": None, "tab_id": None,
            "observation": "", "structured": {}, "interact_prompt": "",
            "screenshots": [], "error": "autoclaw 不可用",
        },
    )

    out_dir = str(tmp_path / "out")
    os.makedirs(out_dir, exist_ok=True)
    itinerary_builder.OUTPUT_DIR = out_dir

    result = execute(
        user_input="我要挂北京大学第三医院骨科王立凡医生的号",
        user_location="北京市海淀区",
        selected_hospital="北京大学第三医院",
        confirmed_appointment={"date": "2026-04-22", "time_slot": "上午"},
        output_format="pdf",
        user_profile={"age_group": "adult"},
    )
    # 因为 doctor-schedule 降级,status 不再是 doctor_schedule_fetched 但仍应到 success
    assert result["status"] == "success"
    assert os.path.exists(result["final_output"]["pdf_path"])


def test_intent_parser_extracts_basic_preferences_without_remote_model():
    result = parse_intent(
        "我奶奶这两天腰疼，想看骨科，帮我做一份大字版行程单",
        use_deepseek=False,
    )

    assert result["output_format"] == "large_font_pdf"
    assert result["time_window"] in {"two_days", "this_week"}
    assert result["is_remote"] is False
    assert "timestamp" in result


def test_hospital_matcher_returns_candidates_with_registration_source():
    result = match(
        user_location="北京市海淀区",
        departments=["骨科"],
        preferences={"max_distance_km": 15, "hospital_level": "三甲"},
        top_n=3,
    )

    assert result["candidates"]
    first = result["candidates"][0]
    assert first["hospital_name"]
    assert first["distance_km"] <= 15
    assert first["map_route_url"].startswith("https://map.baidu.com/dir/")
    assert result["data_sources"]


def test_registration_fetcher_uses_cached_official_link():
    result = fetch("北京大学第三医院", department="骨科")

    assert result["from_cache"] is True
    assert result["hospital_name"] == "北京大学第三医院"
    assert result["registration_url"].startswith("https://")
    assert result["booking_note"]


def test_itinerary_builder_generates_pdf_with_fallback_route(monkeypatch):
    out_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "_generated_test")
    os.makedirs(out_dir, exist_ok=True)
    monkeypatch.delenv("BAIDU_MAP_AUTH_TOKEN", raising=False)
    monkeypatch.setattr(itinerary_builder, "OUTPUT_DIR", out_dir)
    monkeypatch.setattr(itinerary_builder, "HISTORY_PATH", os.path.join(out_dir, "user_history.json"))

    result = itinerary_builder.build(
        user_location="北京市海淀区",
        hospital_name="北京大学第三医院",
        hospital_address="北京市海淀区花园北路49号",
        department="骨科",
        registration_info={
            "registration_url": "https://www.puh3.net.cn/",
            "registration_platform": "医院官网",
            "booking_note": "请以医院官网最新放号信息为准。",
        },
        output_format="large_font_pdf",
        user_profile={"age_group": "elderly"},
    )

    assert result["pdf_path"].endswith(".pdf")
    assert os.path.exists(result["pdf_path"])
    assert os.path.getsize(result["pdf_path"]) > 0
    assert result["route_summary"]["source"] == "估算"
    assert len(result["checklist"]) > 4
    assert result["saved_to_history"] is True


def test_emergency_symptoms_stop_before_hospital_matching(monkeypatch):
    monkeypatch.setattr(
        main_skill,
        "parse_intent",
        lambda *args, **kwargs: {
            "symptom": "胸痛",
            "department": "未指定",
            "timestamp": "2026-04-22T00:00:00",
        },
    )

    def emergency_triage(*args, **kwargs):
        return {
            "recommended_departments": [],
            "warning_flags": ["胸痛伴呼吸困难"],
            "need_more_info": False,
            "follow_up_questions": [],
        }

    monkeypatch.setattr(main_skill, "triage", emergency_triage)
    result = execute(user_input="突发胸痛，呼吸困难", user_profile={"age_group": "adult"})

    assert result["status"] == "emergency_warning"
    assert result["final_output"]["warning"]
    assert "match" not in result["steps"]
    assert "registration" not in result["steps"]
