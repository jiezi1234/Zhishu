import json
import os
import re
import sys
from datetime import datetime

# ── 路径注入 ──────────────────────────────────────────────────────
_SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
_CONFIG_DIR = os.path.join(_SKILL_DIR, "..", "..", "config")
if _CONFIG_DIR not in sys.path:
    sys.path.insert(0, _CONFIG_DIR)

from deepseek_client import DeepSeekClient
from semantic_matcher import search_knowledge


def parse_intent(user_input: str, use_deepseek: bool = True) -> dict:
    """
    Parse user input into structured task parameters.

    Args:
        user_input:    Natural language user request
        use_deepseek:  Whether to use DeepSeek API (True) or local parsing (False)

    Returns:
        Structured task JSON with extracted parameters
    """
    if use_deepseek:
        client = DeepSeekClient()
        task = client.extract_intent(user_input)
        if task:
            task.setdefault("timestamp", datetime.now().isoformat())
            return task

    # 本地解析：symptom / department 走语义，其余走规则
    symptom, department = _extract_symptom_and_dept(user_input)

    task = {
        "symptom":              symptom,
        "department":           department,
        "target_city":          "北京",
        "time_window":          extract_time_window(user_input),
        "budget":               extract_budget(user_input),
        "travel_preference":    extract_travel_preference(user_input),
        "is_remote":            "异地" in user_input or "外地" in user_input,
        "output_format":        extract_output_format(user_input),
        "special_requirements": extract_special_requirements(user_input),
        "timestamp":            datetime.now().isoformat(),
    }
    return task


# ── 语义提取：symptom + department（一次检索，两个字段）────────────

def _extract_symptom_and_dept(text: str) -> tuple[str, str]:
    """
    一次语义检索同时得到 symptom 和 department。
    symptom 取命中 route 的末级节点名（患者可读）。
    department 通过与 symptom_triage 共享的映射表转换。
    """
    hits = search_knowledge(text, k=1)
    if not hits:
        return "未指定", "未指定"

    route = hits[0]["route"]

    # symptom：取 route 最后一段，例如 "疼痛/腰背痛" → "腰背痛"
    symptom = route.split("/")[-1]

    # department：复用 symptom_triage 的映射逻辑
    department = _route_to_dept(route)

    return symptom, department or "未指定"


def _route_to_dept(route: str) -> str | None:
    """与 symptom_triage._route_to_dept 保持一致的映射表。"""
    _ROUTE_DEPT = [
        ("常见症状辨病/疼痛/头痛",           "神经内科"),
        ("常见症状辨病/疼痛/胸痛",           "心内科"),
        ("常见症状辨病/疼痛/腹痛",           "消化内科"),
        ("常见症状辨病/疼痛/腰背痛",          "骨科"),
        ("常见症状辨病/心悸",               "心内科"),
        ("常见症状辨病/发热",               "感染科"),
        ("常见症状辨病/咳嗽",               "呼吸科"),
        ("常见症状辨病/咯血",               "呼吸科"),
        ("常见症状辨病/便血",               "消化内科"),
        ("常见症状辨病/呕血",               "消化内科"),
        ("常见症状辨病/恶心与呕吐",           "消化内科"),
        ("常见症状辨病/尿血",               "泌尿科"),
        ("常见症状辨病/鼻出血",              "耳鼻喉科"),
        ("常见症状辨病/水肿",               "肾内科"),
        ("常见症状辨病/皮肤粘膜出血",          "血液科"),
        ("常见症状辨病/感觉器官功能异常",       "神经内科"),
        ("观察机体局部辨病/眼睛",             "眼科"),
        ("观察机体局部辨病/皮肤",             "皮肤科"),
        ("观察机体局部辨病/口腔",             "口腔科"),
        ("观察机体局部辨病/四肢形态",          "骨科"),
        ("观察机体局部辨病/脊柱",             "骨科"),
        ("观察机体局部辨病/颈部",             "骨科"),
        ("观察机体局部辨病/胸廓形态",          "呼吸科"),
        ("观察机体局部辨病/脉搏",             "心内科"),
        ("观察机体局部辨病/腹部",             "消化内科"),
        ("观察机体局部辨病/头颅",             "神经内科"),
        ("观察机体局部辨病/毛发",             "皮肤科"),
        ("观察机体局部辨病/鼻",              "耳鼻喉科"),
        ("观察分泌物排泄物辨病/痰液",          "呼吸科"),
        ("观察分泌物排泄物辨病/鼻涕",          "耳鼻喉科"),
        ("观察分泌物排泄物辨病/大便",          "消化内科"),
        ("观察分泌物排泄物辨病/小便",          "泌尿科"),
        ("观察分泌物排泄物辨病/汗液异常",       "内分泌科"),
        ("饮食起居辨病/失眠",               "神经内科"),
        ("饮食起居辨病/嗜睡",               "神经内科"),
        ("饮食起居辨病/睡眠",               "神经内科"),
        ("饮食起居辨病/说话异常",             "神经内科"),
        ("饮食起居辨病/运动异常",             "神经内科"),
        ("饮食起居辨病/饮食",               "消化内科"),
        ("妇科疾病/",                      "妇科"),
        ("儿童疾病/",                      "儿科"),
    ]
    for prefix, dept in _ROUTE_DEPT:
        if route.startswith(prefix):
            return dept
    return None


# ── 规则提取：时间、预算、出行偏好、格式、特殊需求 ────────────────
# 这些字段是结构化偏好，语义匹配反而不稳定，保留规则。

def extract_time_window(text: str) -> str:
    time_keywords = {
        "今天": "today",
        "明天": "tomorrow",
        "这两天": "two_days",
        "本周": "this_week",
        "下周": "next_week",
        "周末": "weekend",
    }
    for keyword, value in time_keywords.items():
        if keyword in text:
            return value
    return "this_week"


def extract_budget(text: str) -> int | None:
    match = re.search(r'(\d+)\s*(?:块|元|千|万)', text)
    if match:
        amount = int(match.group(1))
        if "千" in text[match.start():match.end() + 1]:
            amount *= 1000
        elif "万" in text[match.start():match.end() + 1]:
            amount *= 10000
        return amount
    return None


def extract_travel_preference(text: str) -> str:
    if "最近" in text or "近的" in text:
        return "nearby"
    elif "快" in text:
        return "fast"
    elif "便宜" in text:
        return "cheap"
    return "balanced"


def extract_output_format(text: str) -> str:
    if "大字" in text or "老年" in text or "老人" in text:
        return "large_font_pdf"
    elif "excel" in text.lower() or "表格" in text:
        return "excel"
    elif "pdf" in text.lower():
        return "pdf"
    return "large_font_pdf"


def extract_special_requirements(text: str) -> str:
    reqs = []
    if "大字" in text or "老年" in text or "老人" in text:
        reqs.append("large_font")
    if "无障碍" in text:
        reqs.append("accessible")
    if "医保" in text:
        reqs.append("medical_insurance")
    return ",".join(reqs)


if __name__ == "__main__":
    test_inputs = [
        "老人这两天腰疼，帮我找本周可挂上的骨科号，并做一份大字版行程单。",
        "我在南山区上班，只能周末看颈椎，帮我找最近且排队短的医院。",
        "下周从赣州去广州看呼吸科，帮我把挂号、车票、住宿一起规划。",
        "肚子一阵一阵绞痛，想吐，帮我找消化科。",
    ]

    for test_input in test_inputs:
        result = parse_intent(test_input, use_deepseek=False)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print("-" * 50)
