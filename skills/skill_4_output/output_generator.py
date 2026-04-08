import json
import os
from datetime import datetime
from typing import Dict, List

from pdf_generator import generate_pdf_document
from excel_generator import generate_excel_document


def generate_output(recommendations: List[Dict], task_params: Dict, output_format: str = "excel") -> dict:
    """
    Generate formatted output documents.

    Args:
        recommendations: Ranked recommendations from Skill 3
        task_params: Original task parameters
        output_format: "excel", "pdf", or "large_font_pdf"

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
        if output_format in ["pdf", "large_font_pdf"]:
            pdf_path = generate_pdf(recommendations, task_params, output_dir, timestamp, output_format)
            result["files"]["pdf"] = pdf_path
        elif output_format == "excel":
            excel_path = generate_excel(recommendations, task_params, output_dir, timestamp)
            result["files"]["excel"] = excel_path
        else:
            # Default: generate both
            pdf_path = generate_pdf(recommendations, task_params, output_dir, timestamp, "large_font_pdf")
            excel_path = generate_excel(recommendations, task_params, output_dir, timestamp)
            result["files"]["pdf"] = pdf_path
            result["files"]["excel"] = excel_path

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


def generate_excel(recommendations: List[Dict], task_params: Dict, output_dir: str, timestamp: str) -> str:
    """
    Generate Excel document using openpyxl.
    """

    filename = f"medical_travel_plan_{timestamp}.xlsx"
    filepath = os.path.join(output_dir, filename)

    generate_excel_document(recommendations, task_params, filepath)

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

    result = generate_output(test_recommendations, test_task, "excel")
    print(json.dumps(result, ensure_ascii=False, indent=2))
