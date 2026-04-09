import json
import os
import sys
from datetime import datetime
from typing import Dict, List

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(__file__))

from pdf_generator import generate_pdf_document


def generate_output(recommendations: List[Dict], task_params: Dict, output_format: str = "large_font_pdf") -> dict:
    """
    Generate formatted output documents (PDF only).

    Args:
        recommendations: Ranked recommendations from Skill 3
        task_params: Original task parameters
        output_format: "pdf" or "large_font_pdf" (default: large_font_pdf for elderly-friendly)

    Returns:
        Dictionary with file paths and generation status
    """

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "output"
    )
    os.makedirs(output_dir, exist_ok=True)

    result = {
        "timestamp": timestamp,
        "format": output_format,
        "files": {},
        "status": "success"
    }

    try:
        # Always generate PDF (large_font_pdf by default for accessibility)
        if output_format not in ["pdf", "large_font_pdf"]:
            output_format = "large_font_pdf"

        pdf_path = generate_pdf(recommendations, task_params, output_dir, timestamp, output_format)
        result["files"]["pdf"] = pdf_path

    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)

    return result


def generate_pdf(recommendations: List[Dict], task_params: Dict, output_dir: str, timestamp: str, format_type: str) -> str:
    """
    Generate PDF document using reportlab.
    """

    filename = f"appointment_itinerary_{timestamp}.pdf"
    filepath = os.path.join(output_dir, filename)

    large_font = format_type == "large_font_pdf"
    generate_pdf_document(recommendations, task_params, filepath, large_font=large_font)

    return filepath


if __name__ == "__main__":
    # Test example
    test_recommendations = [
        {
            "rank": 1,
            "hospital_name": "北京协和医院",
            "doctor_name": "张医生",
            "doctor_title": "主任医师",
            "appointment_time": "2026-04-15 09:00",
            "total_cost": 100,
            "total_travel_time_min": 15,
            "distance_km": 2.5,
            "queue_estimate_min": 30,
            "score": 8.5,
            "reason": "距离最近，排队时间短"
        }
    ]

    test_task = {
        "department": "骨科",
        "symptom": "腰疼"
    }

    result = generate_output(test_recommendations, test_task, "large_font_pdf")
    print(json.dumps(result, ensure_ascii=False, indent=2))
