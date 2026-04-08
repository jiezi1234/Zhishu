import json
from datetime import datetime
from typing import List, Dict

def evaluate_and_rank(slots: List[Dict], task_params: dict, top_n: int = 2) -> dict:
    """
    Evaluate and rank appointment options.

    Args:
        slots: Available appointment slots from Skill 2
        task_params: Original task parameters from Skill 1
        top_n: Number of top recommendations to return

    Returns:
        Dictionary with ranked recommendations
    """

    budget = task_params.get("budget")
    travel_preference = task_params.get("travel_preference", "balanced")

    # Filter by budget if specified
    if budget:
        slots = [s for s in slots if s.get("registration_fee", 0) <= budget]

    # Calculate scores for each slot
    scored_slots = []
    for slot in slots:
        score = calculate_score(slot, travel_preference)
        scored_slots.append({
            **slot,
            "score": score
        })

    # Sort by score (descending)
    scored_slots.sort(key=lambda x: x["score"], reverse=True)

    # Generate recommendations
    recommendations = []
    for idx, slot in enumerate(scored_slots[:top_n], 1):
        recommendation = {
            "rank": idx,
            "hospital_name": slot.get("hospital_name"),
            "doctor_name": slot.get("doctor_name"),
            "doctor_title": slot.get("doctor_title"),
            "appointment_time": slot.get("available_time"),
            "total_cost": slot.get("registration_fee", 0),
            "total_travel_time_min": slot.get("travel_time_min", 0),
            "distance_km": slot.get("distance_km", 0),
            "queue_estimate_min": slot.get("queue_estimate_min", 0),
            "score": round(slot["score"], 2),
            "reason": generate_reason(slot, idx)
        }
        recommendations.append(recommendation)

    return {
        "recommendations": recommendations,
        "top_n": top_n,
        "total_options_evaluated": len(slots),
        "evaluation_timestamp": datetime.now().isoformat()
    }


def calculate_score(slot: Dict, preference: str) -> float:
    """
    Calculate composite score for a slot.

    Weights:
    - distance: 0.2
    - travel_time: 0.3
    - cost: 0.3
    - queue_time: 0.2
    """

    # Normalize values to 0-10 scale
    distance_score = normalize_distance(slot.get("distance_km", 0))
    travel_time_score = normalize_time(slot.get("travel_time_min", 0))
    cost_score = normalize_cost(slot.get("registration_fee", 0))
    queue_score = normalize_queue(slot.get("queue_estimate_min", 0))

    # Apply weights based on preference
    if preference == "nearby":
        weights = {"distance": 0.4, "travel_time": 0.2, "cost": 0.2, "queue": 0.2}
    elif preference == "fast":
        weights = {"distance": 0.2, "travel_time": 0.4, "cost": 0.2, "queue": 0.2}
    elif preference == "cheap":
        weights = {"distance": 0.2, "travel_time": 0.2, "cost": 0.4, "queue": 0.2}
    else:  # balanced
        weights = {"distance": 0.2, "travel_time": 0.3, "cost": 0.3, "queue": 0.2}

    score = (
        distance_score * weights["distance"] +
        travel_time_score * weights["travel_time"] +
        cost_score * weights["cost"] +
        queue_score * weights["queue"]
    )

    return score


def normalize_distance(km: float) -> float:
    """Normalize distance to 0-10 scale (lower is better)"""
    # 0km = 10, 10km = 0
    return max(0, 10 - km)


def normalize_time(minutes: int) -> float:
    """Normalize travel time to 0-10 scale (lower is better)"""
    # 0min = 10, 60min = 0
    return max(0, 10 - minutes / 6)


def normalize_cost(fee: int) -> float:
    """Normalize cost to 0-10 scale (lower is better)"""
    # 0 = 10, 200 = 0
    return max(0, 10 - fee / 20)


def normalize_queue(minutes: int) -> float:
    """Normalize queue time to 0-10 scale (lower is better)"""
    # 0min = 10, 60min = 0
    return max(0, 10 - minutes / 6)


def generate_reason(slot: Dict, rank: int) -> str:
    """Generate human-readable reason for recommendation"""
    reasons = []

    distance = slot.get("distance_km", 0)
    travel_time = slot.get("travel_time_min", 0)
    queue_time = slot.get("queue_estimate_min", 0)
    fee = slot.get("registration_fee", 0)

    if distance < 3:
        reasons.append("距离最近")
    if travel_time < 20:
        reasons.append("交通便利")
    if queue_time < 25:
        reasons.append("排队时间短")
    if fee < 80:
        reasons.append("挂号费较低")

    if not reasons:
        reasons.append("综合评分最高")

    return "，".join(reasons)


if __name__ == "__main__":
    # Test example
    test_slots = [
        {
            "hospital_name": "北京协和医院",
            "doctor_name": "张医生",
            "doctor_title": "主任医师",
            "available_time": "2026-04-15 09:00",
            "registration_fee": 100,
            "queue_estimate_min": 30,
            "distance_km": 2.5,
            "travel_time_min": 15
        },
        {
            "hospital_name": "北京大学第一医院",
            "doctor_name": "王医生",
            "doctor_title": "主任医师",
            "available_time": "2026-04-15 10:00",
            "registration_fee": 100,
            "queue_estimate_min": 35,
            "distance_km": 3.2,
            "travel_time_min": 20
        }
    ]

    test_task = {
        "budget": None,
        "travel_preference": "nearby"
    }

    result = evaluate_and_rank(test_slots, test_task)
    print(json.dumps(result, ensure_ascii=False, indent=2))
