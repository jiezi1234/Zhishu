import os
import sys

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
