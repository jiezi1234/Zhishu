---
name: healthpath-output-generator
description: Generate formatted output documents (PDF, Excel) with appointment recommendations and travel itinerary
metadata: {"openclaw": {"emoji": "📄", "requires": {"bins": ["python3"]}}}
---

# HealthPath Output Generator Skill

## When to Use

After recommendations are generated, this skill creates formatted output documents suitable for the user's needs and preferences.

## What It Does

1. **PDF Generation**: Creates elderly-friendly large-font PDF itineraries
2. **Excel Generation**: Produces detailed spreadsheets with all appointment and travel details
3. **Email Delivery**: Sends documents to user via email
4. **Format Customization**: Adapts output based on user requirements (large font, accessibility, etc.)

## Input

```json
{
  "recommendations": [...],
  "output_format": "large_font_pdf",
  "special_requirements": "large_font",
  "user_email": "user@example.com"
}
```

## Output

- **PDF File**: `appointment_itinerary_[timestamp].pdf`
- **Excel File**: `medical_travel_plan_[timestamp].xlsx`
- **Email**: Confirmation of delivery

## Output Formats

### Large Font PDF (for elderly)
- Font size: 16pt+ for main content
- High contrast colors (black on white)
- Simplified layout with clear sections
- Large buttons and easy navigation

### Standard Excel
- Multiple sheets: Appointments, Travel, Accommodation
- Color-coded by hospital
- Sortable and filterable columns
- Embedded maps and links

## How It Works

1. Receives recommendations from Skill 3
2. Determines output format based on user preferences
3. Generates document(s) with formatted data
4. Optionally sends via email
5. Returns file paths and delivery status

## Error Handling

- Handles missing email gracefully (saves locally)
- Validates document generation before sending
- Logs all output operations for audit trail

## References

See `scripts/output_generator.py` for implementation details.
