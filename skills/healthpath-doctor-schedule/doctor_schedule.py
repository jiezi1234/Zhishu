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
