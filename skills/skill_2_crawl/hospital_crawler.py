import json
import os
import sys
from datetime import datetime, timedelta
from typing import List, Dict

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(__file__))

from hospital_adapter import HospitalDataManager

def search_available_slots(task_params: dict) -> dict:
    """
    Search for available appointment slots based on task parameters.
    Uses real data sources with fallback to mock data.

    Args:
        task_params: Structured task parameters from Skill 1

    Returns:
        Dictionary with available slots and metadata
    """

    department = task_params.get("department", "未指定")
    target_city = task_params.get("target_city", "北京")
    time_window = task_params.get("time_window", "this_week")
    travel_preference = task_params.get("travel_preference", "balanced")

    # Initialize data manager (tries real sources, falls back to mock)
    data_manager = HospitalDataManager()

    # Fetch hospitals from available data sources
    hospitals_data = data_manager.fetch_hospitals(target_city)

    # For now, use mock slots (real implementation would fetch from adapters)
    slots_data = load_mock_slots()

    # Filter slots by department
    filtered_slots = [
        slot for slot in slots_data.get("available_slots", [])
        if slot.get("department") == department
    ]

    # Filter by time window
    filtered_slots = filter_by_time_window(filtered_slots, time_window)

    # Enrich with hospital info
    for slot in filtered_slots:
        hospital_info = next(
            (h for h in hospitals_data
             if h.get("hospital_id") == slot.get("hospital_id")),
            {}
        )
        slot["distance_km"] = hospital_info.get("distance_km", 0)
        slot["travel_time_min"] = hospital_info.get("distance_km", 0) * 2  # Rough estimate

    # Sort by travel preference
    filtered_slots = sort_by_preference(filtered_slots, travel_preference)

    return {
        "slots": filtered_slots,
        "total_count": len(filtered_slots),
        "search_timestamp": datetime.now().isoformat(),
        "department": department,
        "time_window": time_window,
        "data_sources": data_manager.get_available_adapters()
    }


def load_mock_slots() -> dict:
    """Load mock available slots from JSON file"""
    base_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    slots_file = os.path.join(base_path, "data", "mock", "available_slots.json")

    try:
        with open(slots_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {"available_slots": []}




def filter_by_time_window(slots: List[Dict], time_window: str) -> List[Dict]:
    """Filter slots by time window"""
    today = datetime.now().date()

    time_ranges = {
        "today": (today, today),
        "tomorrow": (today + timedelta(days=1), today + timedelta(days=1)),
        "two_days": (today, today + timedelta(days=2)),
        "this_week": (today, today + timedelta(days=7)),
        "next_week": (today + timedelta(days=7), today + timedelta(days=14)),
        "weekend": (today + timedelta(days=(5 - today.weekday()) % 7),
                    today + timedelta(days=(6 - today.weekday()) % 7))
    }

    start_date, end_date = time_ranges.get(time_window, (today, today + timedelta(days=7)))

    filtered = []
    for slot in slots:
        slot_date = datetime.fromisoformat(slot["available_time"]).date()
        if start_date <= slot_date <= end_date:
            filtered.append(slot)

    return filtered


def sort_by_preference(slots: List[Dict], preference: str) -> List[Dict]:
    """Sort slots by travel preference"""
    if preference == "nearby":
        return sorted(slots, key=lambda x: (x.get("distance_km", 999), x.get("queue_estimate_min", 999)))
    elif preference == "fast":
        return sorted(slots, key=lambda x: (x.get("travel_time_min", 999), x.get("queue_estimate_min", 999)))
    elif preference == "cheap":
        return sorted(slots, key=lambda x: (x.get("registration_fee", 999), x.get("distance_km", 999)))
    else:  # balanced
        # Weighted score: 40% distance, 30% queue time, 30% fee
        def score(slot):
            distance_score = slot.get("distance_km", 999) / 10
            queue_score = slot.get("queue_estimate_min", 999) / 10
            fee_score = slot.get("registration_fee", 999) / 100
            return distance_score * 0.4 + queue_score * 0.3 + fee_score * 0.3

        return sorted(slots, key=score)


if __name__ == "__main__":
    # Test example
    test_task = {
        "department": "骨科",
        "target_city": "北京",
        "time_window": "this_week",
        "travel_preference": "nearby"
    }

    result = search_available_slots(test_task)
    print(json.dumps(result, ensure_ascii=False, indent=2))
