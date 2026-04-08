---
name: healthpath-intent-understanding
description: Parse user medical appointment request into structured task parameters using natural language understanding
metadata: {"openclaw": {"emoji": "🏥", "requires": {"bins": ["python3"]}}}
---

# HealthPath Intent Understanding Skill

## When to Use

When a user provides a natural language request about finding a medical appointment, this skill extracts and structures the key parameters needed for the appointment search.

## What It Does

Parses user input to extract:
- **Symptom/Department**: What medical issue or department (e.g., "骨科", "呼吸科")
- **Target City**: Where to search for hospitals
- **Time Window**: When they want the appointment (e.g., "本周", "下周一")
- **Budget**: Maximum acceptable registration fee
- **Travel Preference**: Distance/time preference
- **Output Format**: Desired output format (PDF, Excel, etc.)
- **Special Requirements**: Large font for elderly, etc.

## Example Usage

**Input:**
```
老人这两天腰疼，帮我找本周可挂上的骨科号，并做一份大字版行程单。
```

**Output:**
```json
{
  "symptom": "腰疼",
  "department": "骨科",
  "target_city": "北京",
  "time_window": "本周",
  "budget": null,
  "travel_preference": "nearby",
  "is_remote": false,
  "output_format": "large_font_pdf",
  "special_requirements": "大字版"
}
```

## How It Works

1. Receives user input (text or voice transcription)
2. Calls DeepSeek API with structured prompt
3. Extracts JSON parameters from response
4. Validates required fields
5. Returns structured task JSON

## Error Handling

- If required fields are missing, asks clarifying questions
- If department name is ambiguous, suggests alternatives
- If city is not recognized, defaults to user's current location

## References

See `scripts/intent_parser.py` for implementation details.
