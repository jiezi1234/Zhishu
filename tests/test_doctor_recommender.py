import os
import sys
from datetime import date

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "skills", "healthpath-doctor-schedule"
))

from recommender import recommend


def _slot(d, period, remaining, total):
    return {"date": d, "period": period, "remaining": remaining, "total": total}


def test_all_full_returns_warning():
    slots = [_slot("2026-04-22", "上午", 0, 20), _slot("2026-04-23", "下午", 0, 20)]
    r = recommend(slots, today=date(2026, 4, 20))
    assert r["recommendation"] is None
    assert r["alternatives"] == []
    assert "约满" in r["warning"]


def test_sufficient_availability_scores_higher_than_tight():
    slots = [
        _slot("2026-04-22", "上午", 15, 20),  # 充足 0.75
        _slot("2026-04-22", "下午", 1, 20),   # 紧张 0.05 → 过滤
        _slot("2026-04-23", "上午", 5, 20),   # 较充足 0.25
    ]
    r = recommend(slots, today=date(2026, 4, 20))
    assert r["recommendation"]["date"] == "2026-04-22"
    assert r["recommendation"]["period"] == "上午"
    assert "号源充足" in r["recommendation"]["reason"]


def test_weekend_preference_is_respected():
    # 2026-04-25 是周六(date.weekday()==5)
    slots = [
        _slot("2026-04-22", "上午", 10, 20),  # 周三
        _slot("2026-04-25", "上午", 10, 20),  # 周六
    ]
    r = recommend(slots, user_preferences={"time_window": "weekend"},
                  today=date(2026, 4, 20))
    assert r["recommendation"]["date"] == "2026-04-25"


def test_too_far_gets_lower_score_than_sweet_spot():
    slots = [
        _slot("2026-04-22", "上午", 10, 20),  # 2 天后,甜蜜区
        _slot("2026-05-03", "上午", 10, 20),  # 13 天后,远
    ]
    r = recommend(slots, today=date(2026, 4, 20))
    assert r["recommendation"]["date"] == "2026-04-22"


def test_reason_contains_remaining_counts_and_time_preference():
    slots = [_slot("2026-04-22", "上午", 3, 20)]
    r = recommend(slots, user_preferences={"time_window": "this_week"},
                  today=date(2026, 4, 20))
    assert "3/20" in r["recommendation"]["reason"]
    assert "本周" in r["recommendation"]["reason"]


def test_alternatives_limited_to_two():
    slots = [_slot(f"2026-04-{22+i}", "上午", 10, 20) for i in range(5)]
    r = recommend(slots, today=date(2026, 4, 20))
    assert len(r["alternatives"]) == 2
