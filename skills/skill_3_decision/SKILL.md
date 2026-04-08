---
name: healthpath-decision-engine
description: Evaluate and rank medical appointment options based on multiple criteria including cost, distance, wait time, and user preferences
metadata: {"openclaw": {"emoji": "🎯", "requires": {"bins": ["python3"]}}}
---

# HealthPath Decision Engine Skill

## When to Use

After collecting available appointment slots from multiple hospitals, this skill evaluates and ranks them to provide the best recommendations based on user constraints and preferences.

## What It Does

1. **Multi-Criteria Evaluation**: Scores each option on distance, time, cost, queue wait
2. **Constraint Checking**: Ensures options meet user budget and time requirements
3. **Ranking**: Generates Top-N recommendations with explanations
4. **Travel Integration**: Calculates total journey time including transportation
5. **Accommodation Suggestions**: For remote appointments, suggests nearby hotels

## Input

```json
{
  "slots": [...],
  "budget": null,
  "travel_preference": "nearby",
  "is_remote": false,
  "special_requirements": "large_font"
}
```

## Output

```json
{
  "recommendations": [
    {
      "rank": 1,
      "hospital_name": "北京协和医院",
      "doctor_name": "张医生",
      "appointment_time": "2026-04-15 09:00",
      "total_cost": 100,
      "total_travel_time_min": 15,
      "queue_estimate_min": 30,
      "score": 8.5,
      "reason": "距离最近，排队时间短"
    }
  ],
  "top_n": 2,
  "evaluation_timestamp": "2026-04-08T10:30:00"
}
```

## Scoring Algorithm

```
score = w1 * distance_score + w2 * time_score + w3 * cost_score + w4 * queue_score

where:
  w1 = 0.2 (distance weight)
  w2 = 0.3 (travel time weight)
  w3 = 0.3 (cost weight)
  w4 = 0.2 (queue time weight)
```

## How It Works

1. Receives available slots from Skill 2
2. Calculates composite score for each option
3. Filters by user constraints (budget, time window)
4. Ranks by score and generates Top-N recommendations
5. Provides human-readable explanations for each recommendation

## Error Handling

- If no options meet constraints, suggests relaxing constraints
- Handles missing data gracefully with default values
- Logs scoring details for transparency

## References

See `scripts/decision_engine.py` for implementation details.
