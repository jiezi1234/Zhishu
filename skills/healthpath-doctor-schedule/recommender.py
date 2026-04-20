"""
recommender.py — 就诊时段推荐打分。

维度与权重(总 100 分):
  号源充足度 40 | 时效贴近 30 | 时间偏好 20 | 避开满诊 10(过滤位)
"""

from datetime import date, datetime, timedelta
from typing import Optional


def recommend(
    slots: list,
    user_preferences: Optional[dict] = None,
    today: Optional[date] = None,
) -> dict:
    prefs = user_preferences or {}
    today = today or date.today()

    usable = [s for s in slots if int(s.get("remaining", 0)) > 0]
    if not usable:
        return {
            "recommendation": None,
            "alternatives": [],
            "warning": "未来 14 天该医生号源均已约满,建议改挂同科室其他专家或关注下周放号",
        }

    scored = sorted(
        [(_score(s, prefs, today), s) for s in usable],
        key=lambda x: -x[0],
    )
    _, top_slot = scored[0]
    return {
        "recommendation": _with_reason(top_slot, prefs, today),
        "alternatives": [_with_reason(s, prefs, today) for _, s in scored[1:3]],
        "warning": None,
    }


def _score(slot: dict, prefs: dict, today: date) -> float:
    remaining = int(slot.get("remaining", 0))
    total = int(slot.get("total", 1)) or 1
    ratio = remaining / total

    # 维度 1:号源充足度 0-40
    if ratio >= 0.5:
        score_avail = 40
    elif ratio >= 0.2:
        score_avail = 16 + (ratio - 0.2) * (40 - 16) / (0.5 - 0.2)
    else:
        score_avail = 0

    # 维度 2:时效贴近 0-30
    slot_date = _parse_date(slot.get("date", ""))
    if slot_date is None:
        score_time = 15
    else:
        days = (slot_date - today).days
        if days < 0:
            score_time = 0
        elif days == 0:
            score_time = 15
        elif days == 1:
            score_time = 22
        elif 2 <= days <= 5:
            score_time = 30
        elif 6 <= days <= 7:
            score_time = 22
        elif days <= 14:
            score_time = 15
        else:
            score_time = 8

    # 维度 3:时间偏好 0-20
    score_pref = 5
    period = slot.get("period", "")
    if prefs.get("preferred_period") and prefs["preferred_period"] in period:
        score_pref += 10
    tw = prefs.get("time_window", "")
    if tw == "weekend" and slot_date and slot_date.weekday() >= 5:
        score_pref = 20
    elif tw in ("today", "tomorrow") and slot_date:
        want = today if tw == "today" else today + timedelta(days=1)
        if slot_date == want:
            score_pref = 20

    return score_avail + score_time + score_pref


def _with_reason(slot: dict, prefs: dict, today: date) -> dict:
    remaining = int(slot.get("remaining", 0))
    total = int(slot.get("total", 1)) or 1
    ratio = remaining / total

    if ratio >= 0.5:
        avail_desc = f"号源充足(剩 {remaining}/{total})"
    elif ratio >= 0.2:
        avail_desc = f"号源较充足(剩 {remaining}/{total})"
    else:
        avail_desc = f"号源紧张(剩 {remaining}/{total})"

    slot_date = _parse_date(slot.get("date", ""))
    time_desc = ""
    if slot_date is not None:
        days = (slot_date - today).days
        if days == 0:
            time_desc = "就是今天"
        elif days == 1:
            time_desc = "明天"
        else:
            time_desc = f"距今 {days} 天"

    pref_desc = ""
    mapping = {"today": "今天", "tomorrow": "明天", "this_week": "本周",
               "weekend": "周末", "next_week": "下周"}
    want = mapping.get(prefs.get("time_window", ""))
    if want:
        pref_desc = f",符合您'{want}看'的时间偏好"

    parts = [avail_desc]
    if time_desc:
        parts.append(time_desc)
    reason = ",".join(parts) + pref_desc

    return {
        "date": slot.get("date", ""),
        "period": slot.get("period", ""),
        "reason": reason,
    }


def _parse_date(s: str):
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    for fmt in ("%m-%d", "%m/%d"):
        try:
            d = datetime.strptime(s, fmt).date()
            return d.replace(year=date.today().year)
        except ValueError:
            continue
    return None
