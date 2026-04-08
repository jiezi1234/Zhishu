import json
import os
from datetime import datetime
from typing import Dict, List

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
    Generate PDF document.

    For now, returns a placeholder. In production, use reportlab or python-docx.
    """

    filename = f"appointment_itinerary_{timestamp}.pdf"
    filepath = os.path.join(output_dir, filename)

    # Create a simple text representation for now
    content = generate_pdf_content(recommendations, task_params, format_type)

    # In production, use reportlab to create actual PDF
    # For now, save as text file with .pdf extension for demo
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    return filepath


def generate_excel(recommendations: List[Dict], task_params: Dict, output_dir: str, timestamp: str) -> str:
    """
    Generate Excel document.

    For now, returns a placeholder. In production, use openpyxl.
    """

    filename = f"medical_travel_plan_{timestamp}.xlsx"
    filepath = os.path.join(output_dir, filename)

    # Create a simple JSON representation for now
    content = generate_excel_content(recommendations, task_params)

    # In production, use openpyxl to create actual Excel file
    # For now, save as JSON for demo
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(content, f, ensure_ascii=False, indent=2)

    return filepath


def generate_pdf_content(recommendations: List[Dict], task_params: Dict, format_type: str) -> str:
    """Generate PDF content as text"""

    lines = []

    if format_type == "large_font_pdf":
        lines.append("=" * 60)
        lines.append("就医行程单（大字版）".center(60))
        lines.append("=" * 60)
    else:
        lines.append("=" * 60)
        lines.append("就医行程单".center(60))
        lines.append("=" * 60)

    lines.append("")
    lines.append(f"生成时间：{datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}")
    lines.append("")

    lines.append("【就医需求】")
    lines.append(f"科室：{task_params.get('department', '未指定')}")
    lines.append(f"症状：{task_params.get('symptom', '未指定')}")
    lines.append(f"时间要求：{task_params.get('time_window', '本周')}")
    lines.append("")

    lines.append("【推荐方案】")
    for rec in recommendations:
        lines.append("")
        lines.append(f"方案 {rec['rank']}：{rec['hospital_name']}")
        lines.append(f"医生：{rec['doctor_name']}（{rec['doctor_title']}）")
        lines.append(f"挂号时间：{rec['appointment_time']}")
        lines.append(f"挂号费：{rec['total_cost']}元")
        lines.append(f"预计排队：{rec['queue_estimate_min']}分钟")
        lines.append(f"距离：{rec['distance_km']}公里")
        lines.append(f"交通时间：{rec['total_travel_time_min']}分钟")
        lines.append(f"推荐理由：{rec['reason']}")

    lines.append("")
    lines.append("=" * 60)
    lines.append("提示：本文件仅供参考，具体挂号请以医院官网为准")
    lines.append("=" * 60)

    return "\n".join(lines)


def generate_excel_content(recommendations: List[Dict], task_params: Dict) -> dict:
    """Generate Excel content as structured data"""

    return {
        "metadata": {
            "title": "医旅全景路书",
            "generated_at": datetime.now().isoformat(),
            "department": task_params.get("department"),
            "symptom": task_params.get("symptom")
        },
        "recommendations": recommendations,
        "task_parameters": task_params,
        "sheets": {
            "appointments": [
                {
                    "rank": rec["rank"],
                    "hospital": rec["hospital_name"],
                    "doctor": rec["doctor_name"],
                    "title": rec["doctor_title"],
                    "time": rec["appointment_time"],
                    "fee": rec["total_cost"],
                    "queue_min": rec["queue_estimate_min"],
                    "score": rec["score"],
                    "reason": rec["reason"]
                }
                for rec in recommendations
            ],
            "travel": [
                {
                    "hospital": rec["hospital_name"],
                    "distance_km": rec["distance_km"],
                    "travel_time_min": rec["total_travel_time_min"],
                    "appointment_time": rec["appointment_time"]
                }
                for rec in recommendations
            ]
        }
    }


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
