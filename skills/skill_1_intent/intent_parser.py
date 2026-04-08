import json
import os
import sys
from datetime import datetime, timedelta

# Add parent directories to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'config'))

from deepseek_client import DeepSeekClient


def parse_intent(user_input: str, use_deepseek: bool = True) -> dict:
    """
    Parse user input into structured task parameters.

    Args:
        user_input: Natural language user request
        use_deepseek: Whether to use DeepSeek API (True) or rule-based parsing (False)

    Returns:
        Structured task JSON with extracted parameters
    """

    if use_deepseek:
        # Try to use DeepSeek API first
        client = DeepSeekClient()
        task = client.extract_intent(user_input)

        if task:
            # Ensure all required fields are present
            task.setdefault("timestamp", datetime.now().isoformat())
            return task

    # Fallback to rule-based parsing if DeepSeek fails or is disabled
    task = {
        "symptom": extract_symptom(user_input),
        "department": extract_department(user_input),
        "target_city": "北京",  # Default to Beijing
        "time_window": extract_time_window(user_input),
        "budget": extract_budget(user_input),
        "travel_preference": extract_travel_preference(user_input),
        "is_remote": "异地" in user_input or "外地" in user_input,
        "output_format": extract_output_format(user_input),
        "special_requirements": extract_special_requirements(user_input),
        "timestamp": datetime.now().isoformat()
    }

    return task


def extract_symptom(text: str) -> str:
    """Extract symptom from user input"""
    symptoms = ["腰疼", "颈椎", "呼吸", "心脏", "胃", "头疼", "发烧", "咳嗽"]
    for symptom in symptoms:
        if symptom in text:
            return symptom
    return "未指定"


def extract_department(text: str) -> str:
    """Extract medical department from user input"""
    departments = {
        "骨科": ["腰疼", "颈椎", "骨", "关节"],
        "呼吸科": ["呼吸", "咳嗽", "肺", "哮喘"],
        "心内科": ["心脏", "心血管", "高血压"],
        "神经内科": ["头疼", "中风", "神经"],
        "消化科": ["胃", "肠", "消化"],
        "内分泌科": ["糖尿病", "甲状腺"]
    }

    for dept, keywords in departments.items():
        for keyword in keywords:
            if keyword in text:
                return dept

    # Check if department is directly mentioned
    for dept in departments.keys():
        if dept in text:
            return dept

    return "未指定"


def extract_time_window(text: str) -> str:
    """Extract time window from user input"""
    time_keywords = {
        "本周": "this_week",
        "下周": "next_week",
        "今天": "today",
        "明天": "tomorrow",
        "这两天": "two_days",
        "周末": "weekend"
    }

    for keyword, value in time_keywords.items():
        if keyword in text:
            return value

    return "this_week"  # Default


def extract_budget(text: str) -> int:
    """Extract budget from user input"""
    import re
    # Look for patterns like "预算三千" or "三千块"
    match = re.search(r'(\d+)(?:块|元|千|万)', text)
    if match:
        amount = int(match.group(1))
        if "千" in text:
            amount *= 1000
        elif "万" in text:
            amount *= 10000
        return amount
    return None


def extract_travel_preference(text: str) -> str:
    """Extract travel preference from user input"""
    if "最近" in text or "近的" in text:
        return "nearby"
    elif "快速" in text or "快" in text:
        return "fast"
    elif "便宜" in text or "便宜的" in text:
        return "cheap"
    return "balanced"


def extract_output_format(text: str) -> str:
    """Extract desired output format"""
    if "大字" in text or "老年" in text or "老人" in text:
        return "large_font_pdf"
    elif "excel" in text.lower() or "表格" in text:
        return "excel"
    elif "pdf" in text.lower():
        return "pdf"
    return "excel"  # Default


def extract_special_requirements(text: str) -> str:
    """Extract special requirements"""
    requirements = []

    if "大字" in text or "老年" in text or "老人" in text:
        requirements.append("large_font")
    if "无障碍" in text:
        requirements.append("accessible")
    if "医保" in text:
        requirements.append("medical_insurance")

    return ",".join(requirements) if requirements else ""


if __name__ == "__main__":
    # Test examples
    test_inputs = [
        "老人这两天腰疼，帮我找本周可挂上的骨科号，并做一份大字版行程单。",
        "我在南山区上班，只能周末看颈椎，帮我找最近且排队短的医院。",
        "下周从赣州去广州看呼吸科，帮我把挂号、车票、住宿一起规划。"
    ]

    for test_input in test_inputs:
        result = parse_intent(test_input)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print("-" * 50)
