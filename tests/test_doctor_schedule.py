import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "skills", "healthpath-doctor-schedule"
))

import doctor_schedule
from doctor_schedule import list_experts


def _fake_driver_result(status="success", observation="", interact=None,
                        session="sid-1", tab="7"):
    return {
        "status": status,
        "session_id": session,
        "tab_id": tab,
        "observation": observation,
        "structured": {},
        "interact_prompt": interact or "",
        "screenshots": [],
        "error": None,
    }


def test_list_experts_happy_parses_from_observation(monkeypatch):
    fake_md = (
        "神经内科出诊专家:\n"
        "王立凡 主任医师 头痛、脑血管病\n"
        "李晓红 副主任医师 癫痫、睡眠障碍\n"
        "赵卫国 主治医师 头晕、头痛\n"
    )
    monkeypatch.setattr(doctor_schedule, "run_browser_task",
                        lambda **kw: _fake_driver_result(observation=fake_md))
    r = list_experts("北京协和医院", "神经内科",
                     "https://www.pumch.cn/guahao")
    assert r["status"] == "success"
    names = [e["name"] for e in r["experts"]]
    assert "王立凡" in names and "李晓红" in names and "赵卫国" in names
    first = next(e for e in r["experts"] if e["name"] == "王立凡")
    assert first["title"] == "主任医师"
    assert "头痛" in first["specialty"]


def test_list_experts_passes_through_interact(monkeypatch):
    monkeypatch.setattr(doctor_schedule, "run_browser_task",
                        lambda **kw: _fake_driver_result(
                            status="interact_required",
                            interact="协和官网要求登录"))
    r = list_experts("北京协和医院", "神经内科",
                     "https://www.pumch.cn/guahao")
    assert r["status"] == "awaiting_browser_interaction"
    assert r["browser_session"]["session_id"] == "sid-1"
    assert "登录" in r["interact_prompt"]


def test_list_experts_driver_unavailable_returns_error(monkeypatch):
    def _unavail(**kw):
        d = _fake_driver_result(status="not_available", session=None, tab=None)
        d["error"] = "autoclaw 不可用"
        return d
    monkeypatch.setattr(doctor_schedule, "run_browser_task", _unavail)
    r = list_experts("北京协和医院", "神经内科",
                     "https://www.pumch.cn/guahao")
    assert r["status"] == "error"
    assert "不可用" in r["error"]


def test_list_experts_rejects_empty_url():
    r = list_experts("北京协和医院", "神经内科", "")
    assert r["status"] == "error"
    assert "registration_url" in r["error"]


def test_list_experts_resume_prefixes_task(monkeypatch):
    captured = {}

    def _spy(**kw):
        captured["task"] = kw["task"]
        captured["session_id"] = kw.get("session_id")
        captured["tab_id"] = kw.get("tab_id")
        return _fake_driver_result(observation="王立凡 主任医师 某专长")

    monkeypatch.setattr(doctor_schedule, "run_browser_task", _spy)
    r = list_experts("北京协和医院", "神经内科",
                     "https://www.pumch.cn/guahao",
                     browser_resume={"session_id": "sid-X",
                                     "tab_id": "9",
                                     "user_action": "login_done"})
    assert r["status"] == "success"
    assert captured["session_id"] == "sid-X"
    assert captured["tab_id"] == "9"
    assert captured["task"].startswith("用户已完成登录北京协和医院官网。")


# ═══════════════════════════════════════════════════════════════════
# fetch_doctor_schedule 测试(Task 4)
# ═══════════════════════════════════════════════════════════════════

from doctor_schedule import fetch_doctor_schedule, _save_cache, _load_cache


def _fake_schedule_md():
    return (
        "王立凡 主任医师\n"
        "擅长:头痛、脑血管病\n"
        "出诊:周一上午 专家门诊,周三下午 特需门诊\n"
        "排班:\n"
        "2026-04-22|上午|3/20\n"
        "2026-04-23|下午|0/20\n"
        "2026-04-25|上午|10/20\n"
    )


def test_fetch_schedule_success_parses_all_fields(monkeypatch, tmp_path):
    monkeypatch.setattr(doctor_schedule, "CACHE_PATH", str(tmp_path / "cache.json"))
    monkeypatch.setattr(doctor_schedule, "run_browser_task",
                        lambda **kw: _fake_driver_result(observation=_fake_schedule_md()))
    r = fetch_doctor_schedule("北京协和医院", "王立凡",
                              "https://www.pumch.cn/guahao",
                              user_preferences={"time_window": "this_week"})
    assert r["status"] == "success"
    assert r["schedule"]["doctor"]["name"] == "王立凡"
    assert r["schedule"]["doctor"]["title"] == "主任医师"
    assert len(r["schedule"]["weekly_pattern"]) >= 1
    assert len(r["schedule"]["slots"]) == 3
    assert r["recommendation"] is not None
    assert r["schedule"]["from_cache"]["slots"] is False


def test_fetch_schedule_doctor_not_found(monkeypatch, tmp_path):
    monkeypatch.setattr(doctor_schedule, "CACHE_PATH", str(tmp_path / "cache.json"))
    monkeypatch.setattr(doctor_schedule, "run_browser_task",
                        lambda **kw: _fake_driver_result(observation="无此医生"))
    r = fetch_doctor_schedule("北京协和医院", "张不存在",
                              "https://www.pumch.cn/guahao")
    assert r["status"] == "doctor_not_found"
    assert r["schedule"] is None
    assert "未找到" in r["error"]


def test_fetch_schedule_all_booked_returns_warning(monkeypatch, tmp_path):
    monkeypatch.setattr(doctor_schedule, "CACHE_PATH", str(tmp_path / "cache.json"))
    full_md = (
        "王立凡 主任医师\n"
        "2026-04-22|上午|0/20\n"
        "2026-04-23|下午|0/20\n"
    )
    monkeypatch.setattr(doctor_schedule, "run_browser_task",
                        lambda **kw: _fake_driver_result(observation=full_md))
    r = fetch_doctor_schedule("北京协和医院", "王立凡",
                              "https://www.pumch.cn/guahao")
    assert r["status"] == "schedule_fetched_but_full"
    assert r["recommendation"] is None
    assert r["warning"] and "约满" in r["warning"]


def test_fetch_schedule_cache_hit_when_pattern_missing_in_new_fetch(
    monkeypatch, tmp_path
):
    """抓取失败拿不到 weekly_pattern 时,回退到 cache。"""
    monkeypatch.setattr(doctor_schedule, "CACHE_PATH", str(tmp_path / "cache.json"))
    _save_cache("北京协和医院", "王立凡",
                {"name": "王立凡", "title": "主任医师", "specialty": "头痛"},
                [{"weekday": "周一上午", "shift": "专家门诊"}])
    md_no_pattern = "王立凡 主任医师\n2026-04-22|上午|5/20\n"
    monkeypatch.setattr(doctor_schedule, "run_browser_task",
                        lambda **kw: _fake_driver_result(observation=md_no_pattern))
    r = fetch_doctor_schedule("北京协和医院", "王立凡",
                              "https://www.pumch.cn/guahao")
    assert r["status"] == "success"
    assert r["schedule"]["from_cache"]["weekly_pattern"] is True
    assert len(r["schedule"]["weekly_pattern"]) == 1


def test_fetch_schedule_interact_required(monkeypatch, tmp_path):
    monkeypatch.setattr(doctor_schedule, "CACHE_PATH", str(tmp_path / "cache.json"))
    monkeypatch.setattr(doctor_schedule, "run_browser_task",
                        lambda **kw: _fake_driver_result(
                            status="interact_required",
                            interact="请完成短信验证码"))
    r = fetch_doctor_schedule("北京协和医院", "王立凡",
                              "https://www.pumch.cn/guahao")
    assert r["status"] == "awaiting_browser_interaction"
    assert r["browser_session"]["session_id"] == "sid-1"


def test_fetch_schedule_rejects_empty_params():
    r1 = fetch_doctor_schedule("", "王立凡", "https://x")
    assert r1["status"] == "error"
    r2 = fetch_doctor_schedule("协和", "", "https://x")
    assert r2["status"] == "error"
    r3 = fetch_doctor_schedule("协和", "王立凡", "")
    assert r3["status"] == "error"


def test_cache_expires_after_7_days(monkeypatch, tmp_path):
    import json as _json
    monkeypatch.setattr(doctor_schedule, "CACHE_PATH", str(tmp_path / "cache.json"))
    _save_cache("X医院", "某医生",
                {"name": "某", "title": "主任医师", "specialty": ""},
                [{"weekday": "周一上午", "shift": "专家门诊"}])
    with open(tmp_path / "cache.json", encoding="utf-8") as f:
        c = _json.load(f)
    c["X医院::某医生"]["weekly_pattern_cached_at"] = (
        datetime.now() - timedelta(days=8)
    ).isoformat()
    with open(tmp_path / "cache.json", "w", encoding="utf-8") as f:
        _json.dump(c, f)
    assert _load_cache("X医院", "某医生") is None
