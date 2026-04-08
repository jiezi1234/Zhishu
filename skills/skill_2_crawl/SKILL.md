---
name: healthpath-hospital-crawler
description: Search and fetch available medical appointment slots from multiple hospitals based on department and time constraints
metadata: {"openclaw": {"emoji": "🏨", "requires": {"bins": ["python3"]}}}
---

# HealthPath Hospital Crawler Skill

## When to Use

After intent understanding extracts the appointment requirements, this skill searches for available appointment slots across multiple hospitals that match the criteria.

## What It Does

1. **Hospital Selection**: Filters hospitals by location and distance
2. **Slot Retrieval**: Fetches available appointment slots for the requested department
3. **Data Standardization**: Normalizes data from different sources into unified format
4. **Filtering**: Applies time window and other constraints
5. **Ranking**: Sorts results by relevance

## Input

```json
{
  "department": "骨科",
  "target_city": "北京",
  "time_window": "this_week",
  "travel_preference": "nearby"
}
```

## Output

```json
{
  "slots": [
    {
      "hospital_id": "hospital_001",
      "hospital_name": "北京协和医院",
      "department": "骨科",
      "doctor_name": "张医生",
      "doctor_title": "主任医师",
      "available_time": "2026-04-15 09:00",
      "registration_fee": 100,
      "queue_estimate_min": 30,
      "distance_km": 2.5,
      "travel_time_min": 15
    }
  ],
  "total_count": 6,
  "search_timestamp": "2026-04-08T10:30:00"
}
```

## How It Works

1. Receives structured task parameters from Skill 1
2. Queries hospital database for matching hospitals
3. Fetches available slots (from mock data or real APIs)
4. Standardizes all data to unified format
5. Applies filters and sorting
6. Returns ranked list of available slots

## Data Sources

- **Mock Data**: `data/mock/available_slots.json` (for demo)
- **Real APIs**: Hospital-specific adapters (future)
- **Web Scraping**: Selenium-based crawlers (future)

## Error Handling

- If no slots found, suggests alternative departments or time windows
- Handles API timeouts with retry logic
- Logs all failed requests for debugging

## References

See `scripts/hospital_crawler.py` for implementation details.
