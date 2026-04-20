"""
doctor_schedule.py — 医生出诊表与号源查询主模块。

对外三个 dict:
  list_experts(hospital_name, department, registration_url, browser_resume=None)
  fetch_doctor_schedule(hospital_name, doctor_name, registration_url,
                        user_preferences=None, browser_resume=None)

约束:
  - registration_url 必须来自 registration_fetcher,本模块不自查
  - 一次调用内最多触发 1 次 autoclaw
  - 缓存 weekly_pattern 7 天;不缓存 slots
"""

import json
import logging
import os
import re
import sys
from datetime import datetime, timedelta
from typing import Optional

_SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
if _SKILL_DIR not in sys.path:
    sys.path.insert(0, _SKILL_DIR)

from autoclaw_driver import run_browser_task
from recommender import recommend

logger = logging.getLogger(__name__)

CACHE_PATH = os.path.join(_SKILL_DIR, "schedule_cache.json")
CACHE_TTL_DAYS = 7

TASK_LIST_EXPERTS = (
    "打开{registration_url},进入{department}科室介绍页,"
    "列出该科室所有出诊专家,每位专家给出姓名、职称(主任医师/副主任医师/主治医师)、"
    "擅长领域简介,最多10位。以清单形式输出。"
)

TASK_FETCH_SCHEDULE = (
    "打开{registration_url},搜索医生'{doctor_name}',"
    "进入其个人主页,读取未来14天的出诊排班表,"
    "每个时段标注'剩余号数/总号数'。以结构化列表输出,每行格式:"
    "日期|时段(上午/下午)|剩余/总数。"
)


def list_experts(
    hospital_name: str,
    department: str,
    registration_url: str,
    browser_resume: Optional[dict] = None,
) -> dict:
    if not registration_url:
        return _err("experts", "registration_url 为空,请先调用 registration-fetcher")

    task = TASK_LIST_EXPERTS.format(
        registration_url=registration_url, department=department)

    sid = tid = None
    if browser_resume:
        sid = browser_resume.get("session_id")
        tid = browser_resume.get("tab_id")
        task = _resume_prefix(browser_resume, hospital_name) + task

    driver = run_browser_task(
        task=task,
        start_url=registration_url if not sid else None,
        session_id=sid, tab_id=tid,
    )

    if driver["status"] == "not_available":
        return _err("experts", driver.get("error") or "autoclaw 不可用")
    if driver["status"] == "timeout":
        return _err("experts", driver.get("error") or "autoclaw 超时")
    if driver["status"] == "error":
        return _err("experts", driver.get("error") or "autoclaw 返回错误")

    if driver["status"] == "interact_required":
        return {
            "status": "awaiting_browser_interaction",
            "experts": [],
            "browser_session": {
                "session_id": driver["session_id"],
                "tab_id": driver["tab_id"],
            },
            "interact_prompt": driver.get("interact_prompt", ""),
            "error": None,
        }

    experts = _parse_experts(driver["observation"])
    return {"status": "success", "experts": experts, "error": None}


# ── 解析器(规则式,若 autoclaw 输出变化可迭代) ─────────────────────

_TITLE_RE = r"(主任医师|副主任医师|主治医师|医师)"


def fetch_doctor_schedule(
    hospital_name: str,
    doctor_name: str,
    registration_url: str,
    user_preferences: Optional[dict] = None,
    browser_resume: Optional[dict] = None,
) -> dict:
    if not hospital_name:
        return _err("schedule", "hospital_name 为空")
    if not doctor_name:
        return _err("schedule", "doctor_name 为空")
    if not registration_url:
        return _err("schedule", "registration_url 为空,请先调用 registration-fetcher")

    cached = _load_cache(hospital_name, doctor_name)

    task = TASK_FETCH_SCHEDULE.format(
        registration_url=registration_url, doctor_name=doctor_name)

    sid = tid = None
    if browser_resume:
        sid = browser_resume.get("session_id")
        tid = browser_resume.get("tab_id")
        task = _resume_prefix(browser_resume, hospital_name) + task

    driver = run_browser_task(
        task=task,
        start_url=registration_url if not sid else None,
        session_id=sid, tab_id=tid,
    )

    if driver["status"] in ("not_available", "timeout", "error"):
        return _err("schedule", driver.get("error") or "autoclaw 不可用")

    if driver["status"] == "interact_required":
        return {
            "status": "awaiting_browser_interaction",
            "schedule": None,
            "recommendation": None,
            "warning": None,
            "error": None,
            "browser_session": {
                "session_id": driver["session_id"],
                "tab_id": driver["tab_id"],
            },
            "interact_prompt": driver.get("interact_prompt", ""),
        }

    obs = driver["observation"]
    doctor_meta = _parse_doctor_meta(obs, doctor_name)
    if doctor_meta is None:
        return {
            "status": "doctor_not_found",
            "schedule": None,
            "recommendation": None,
            "warning": None,
            "error": f"在当前页面未找到医生'{doctor_name}',请确认姓名是否正确或改走专家列表分支",
        }

    weekly_pattern = _parse_weekly_pattern(obs)
    slots = _parse_slots(obs)

    from_cache_pattern = False
    if not weekly_pattern and cached:
        weekly_pattern = cached.get("weekly_pattern", [])
        from_cache_pattern = True
    elif weekly_pattern:
        _save_cache(hospital_name, doctor_name, doctor_meta, weekly_pattern)

    rec = recommend(slots, user_preferences=user_preferences)

    schedule = {
        "doctor": doctor_meta,
        "weekly_pattern": weekly_pattern,
        "slots": slots,
        "data_timestamp": datetime.now().isoformat(),
        "from_cache": {"weekly_pattern": from_cache_pattern, "slots": False},
    }

    if rec["recommendation"] is None:
        return {
            "status": "schedule_fetched_but_full",
            "schedule": schedule,
            "recommendation": None,
            "warning": rec["warning"],
            "error": None,
        }

    return {
        "status": "success",
        "schedule": schedule,
        "recommendation": rec["recommendation"],
        "alternatives": rec["alternatives"],
        "warning": None,
        "error": None,
    }


def _parse_experts(md: str) -> list:
    """
    从自由文本抽取专家。接受类似:
      "王立凡 主任医师 头痛、脑血管病"
      "王立凡,主任医师,头痛"
      "- 王立凡 主任医师:头痛"
    """
    pattern = re.compile(
        r"([\u4e00-\u9fa5]{2,4})\s*[,、\|:： \t]+"
        rf"{_TITLE_RE}\s*[,、\|:： \t]+"
        r"([^\n]+)"
    )
    experts = []
    seen = set()
    for m in pattern.finditer(md):
        name = m.group(1)
        if name in seen or name in {"主任", "医生", "大夫", "专家"}:
            continue
        seen.add(name)
        experts.append({
            "name": name,
            "title": m.group(2),
            "specialty": m.group(3).strip()[:60],
            "profile_url": "",
        })
        if len(experts) >= 10:
            break
    return experts


# ── 恢复前缀 ─────────────────────────────────────────────────────

def _parse_doctor_meta(md: str, doctor_name: str) -> Optional[dict]:
    if doctor_name not in md:
        return None
    title_m = re.search(
        rf"{re.escape(doctor_name)}\s*[,、\|:： \t]*{_TITLE_RE}", md)
    title = title_m.group(1) if title_m else "医师"
    spec_m = re.search(
        rf"{re.escape(doctor_name)}[\s\S]{{0,80}}?(?:擅长|专长)[::]\s*([^\n]+)",
        md)
    specialty = spec_m.group(1).strip()[:80] if spec_m else ""
    return {"name": doctor_name, "title": title, "specialty": specialty}


def _parse_weekly_pattern(md: str) -> list:
    pattern = []
    wk = re.compile(
        r"(周[一二三四五六日])\s*(上午|下午)\s*[:： ]?\s*([^\n,。;;]{0,20})"
    )
    for m in wk.finditer(md):
        pattern.append({
            "weekday": f"{m.group(1)}{m.group(2)}",
            "shift": m.group(3).strip() or "门诊",
        })
    return pattern


def _parse_slots(md: str) -> list:
    slots = []
    slot_re = re.compile(
        r"(\d{4}-\d{1,2}-\d{1,2}|\d{1,2}[-/]\d{1,2})"
        r"\s*[\|\s,]+\s*(上午|下午|全天)"
        r"\s*[\|\s,]+\s*(\d+)\s*[/／]\s*(\d+)"
    )
    for m in slot_re.finditer(md):
        d = m.group(1)
        if "-" in d and len(d.split("-")) == 2:
            d = f"{datetime.now().year}-{d}"
        elif "/" in d and len(d.split("/")) == 2:
            parts = d.split("/")
            d = f"{datetime.now().year}-{parts[0]}-{parts[1]}"
        slots.append({
            "date": d,
            "period": m.group(2),
            "remaining": int(m.group(3)),
            "total": int(m.group(4)),
        })
    return slots


# ── 缓存 ─────────────────────────────────────────────────────────

def _load_cache(hospital_name: str, doctor_name: str) -> Optional[dict]:
    if not os.path.exists(CACHE_PATH):
        return None
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            cache = json.load(f)
    except Exception:
        return None
    entry = cache.get(f"{hospital_name}::{doctor_name}")
    if not entry:
        return None
    try:
        cached_at = datetime.fromisoformat(entry.get("weekly_pattern_cached_at", ""))
    except Exception:
        return None
    if datetime.now() - cached_at > timedelta(days=CACHE_TTL_DAYS):
        return None
    return entry


def _save_cache(hospital_name: str, doctor_name: str,
                doctor_meta: dict, weekly_pattern: list) -> None:
    cache = {}
    if os.path.exists(CACHE_PATH):
        try:
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                cache = json.load(f)
        except Exception:
            cache = {}
    cache[f"{hospital_name}::{doctor_name}"] = {
        "doctor_meta": doctor_meta,
        "weekly_pattern": weekly_pattern,
        "weekly_pattern_cached_at": datetime.now().isoformat(),
        "weekly_pattern_ttl_days": CACHE_TTL_DAYS,
    }
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


# ── 恢复前缀 ─────────────────────────────────────────────────────

def _resume_prefix(browser_resume: dict, hospital_name: str) -> str:
    action = browser_resume.get("user_action", "")
    if action == "login_done":
        return f"用户已完成登录{hospital_name}官网。"
    if action == "captcha_done":
        return "用户已完成验证码。"
    if action == "approve":
        return "用户已同意上述敏感操作,请直接完成该操作。"
    if action == "reject":
        return "用户已拒绝上述操作,请直接跳过该操作。"
    if action:
        return f"用户反馈:{action}。"
    return ""


# ── 统一错误结构 ─────────────────────────────────────────────────

def _err(kind: str, msg: str) -> dict:
    """kind='experts' 返回 experts 结构;kind='schedule' 返回 schedule 结构。"""
    base = {"status": "error", "error": msg}
    if kind == "experts":
        base["experts"] = []
    else:
        base["schedule"] = None
        base["recommendation"] = None
        base["warning"] = None
    return base
