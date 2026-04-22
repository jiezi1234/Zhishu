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
            task.setdefault("doctor_name", extract_doctor_name(user_input))
            task.setdefault("user_location", extract_user_location(user_input))
            task.setdefault("target_hospital", extract_target_hospital(user_input))
            return task

    # 本地解析：symptom / department 走语义，其余走规则
    symptom, department = _extract_symptom_and_dept(user_input)

    task = {
        "symptom":              symptom,
        "department":           department,
        "doctor_name":          extract_doctor_name(user_input),
        "user_location":        extract_user_location(user_input),
        "target_hospital":      extract_target_hospital(user_input),
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

# 明确症状关键词/正则直接映射,避免长句语义检索被"我""的""想"等高频词带偏。
# 每条规则的 patterns 可以是 str(子串匹配)或 re.Pattern(正则搜索),
# 后者用于处理"头有点痛""肚子一阵一阵疼"这类允许中间插字的表达。
# 顺序敏感:更具体的条目放在前面。
_SYMPTOM_RULES: list[tuple[list, str, str]] = [
    # 头痛——允许"头…痛/疼"中间插入描述词
    ([re.compile(r"头[^，,。.!！?？\n]{0,5}(?:痛|疼)"),
      "偏头痛", "脑袋痛", "脑袋疼"],                               "头痛",       "神经内科"),
    # 胸痛/胸闷
    ([re.compile(r"胸(?:口|部)?[^，,。.!！?？\n]{0,3}(?:痛|疼|闷)"),
      "压榨样胸痛", "心前区痛"],                                   "胸痛",       "心内科"),
    # 心悸
    (["心悸", "心慌", "心跳快", "心跳乱"],                         "心悸",       "心内科"),
    # 腹痛/肚子痛
    ([re.compile(r"(?:腹部?|肚子)[^，,。.!！?？\n]{0,4}(?:痛|疼)")],"腹痛",       "消化内科"),
    # 腰背痛
    ([re.compile(r"腰(?:部|背)?[^，,。.!！?？\n]{0,3}(?:痛|疼)"),
      "腰背痛"],                                                   "腰背痛",     "骨科"),
    # 颈部不适
    ([re.compile(r"(?:颈(?:部|椎)|脖子)[^，,。.!！?？\n]{0,3}(?:痛|疼|僵|硬)"),
      "颈椎病"],                                                   "颈部不适",   "骨科"),
    # 咯血
    (["咯血", "痰中带血"],                                         "咯血",       "呼吸科"),
    # 咳嗽
    (["咳嗽", "咳痰"],                                             "咳嗽",       "呼吸科"),
    # 发热
    (["发烧", "发热", "高热", "低热"],                             "发热",       "感染科"),
    # 便血
    (["便血"],                                                     "便血",       "消化内科"),
    # 呕血
    (["呕血", "吐血"],                                             "呕血",       "消化内科"),
    # 恶心呕吐
    (["恶心", "想吐", "呕吐"],                                     "恶心与呕吐", "消化内科"),
    # 尿血
    (["尿血"],                                                     "尿血",       "泌尿科"),
    # 小便异常
    (["尿频", "尿急", "尿痛", "排尿刺痛"],                          "小便异常",   "泌尿科"),
    # 鼻出血
    (["鼻出血", "流鼻血"],                                         "鼻出血",     "耳鼻喉科"),
    # 鼻部问题
    (["鼻塞", "鼻涕", "鼻炎"],                                     "鼻部问题",   "耳鼻喉科"),
    # 水肿
    (["水肿", "浮肿"],                                             "水肿",       "肾内科"),
    # 头晕/眩晕(独立于头痛的表达)
    (["头晕", "晕眩", "天旋地转"],                                 "头晕",       "神经内科"),
    # 失眠
    (["失眠", "睡不着"],                                           "失眠",       "神经内科"),
    # 皮肤问题
    (["皮疹", "瘙痒", "皮肤"],                                     "皮肤问题",   "皮肤科"),
    # 眼部问题
    (["眼睛", "视力", "眼痛"],                                     "眼部问题",   "眼科"),
    # 口腔问题
    ([re.compile(r"牙[^，,。.!！?？\n]{0,3}(?:痛|疼)"),
      "口腔溃疡", "牙龈"],                                         "口腔问题",   "口腔科"),
    # 妇科
    (["月经", "白带", "痛经"],                                     "月经和白带", "妇科"),
]


def _keyword_symptom_match(text: str) -> tuple[str, str] | None:
    for patterns, symptom, dept in _SYMPTOM_RULES:
        for p in patterns:
            if isinstance(p, str):
                if p in text:
                    return symptom, dept
            else:  # re.Pattern
                if p.search(text):
                    return symptom, dept
    return None


def _extract_symptom_and_dept(text: str) -> tuple[str, str]:
    """
    先用关键词/正则规则匹配明确症状;规则未命中时再走语义检索兜底。
    symptom 取命中 route 的末级节点名(患者可读)。
    department 通过与 symptom_triage 共享的映射表转换。
    """
    kw_hit = _keyword_symptom_match(text)
    if kw_hit:
        return kw_hit

    hits = search_knowledge(text, k=1)
    if not hits:
        return "未指定", "未指定"

    route = hits[0]["route"]
    symptom = route.split("/")[-1]
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


# ── 位置 / 目标医院抽取(规则式) ─────────────────────────────────

_LOCATION_BAD_WORDS = {
    "头", "痛", "疼", "病", "医院", "挂号", "想", "找", "挂",
    "发烧", "发热", "咳嗽", "问诊", "治疗",
}


def extract_user_location(text: str) -> str:
    """从 '我在 XXX' / '现在在 XXX' 类表达中提取用户当前位置。"""
    import re as _re
    patterns = [
        r"我(?:现在|目前)?在([^,，。.!！?？\s]{3,30}?)(?:[，,。.\s]|$)",
        r"(?:现在|目前|当前)在([^,，。.!！?？\s]{3,30}?)(?:[，,。.\s]|$)",
    ]
    for p in patterns:
        m = _re.search(p, text)
        if m:
            loc = m.group(1).strip()
            if len(loc) >= 3 and not any(bw in loc for bw in _LOCATION_BAD_WORDS):
                return loc
    return ""


def extract_target_hospital(text: str) -> str:
    """从 '挂/去/到 XX 医院' 类表达中提取目标医院全称。"""
    import re as _re
    m = _re.search(
        r"(?:挂|去|到|找|上|进|在|想去)\s*(?:个|一个|家|一家)?\s*([\u4e00-\u9fa5]{2,15}医院)",
        text,
    )
    if m:
        return m.group(1)
    m = _re.search(r"([\u4e00-\u9fa5]{2,15}医院)", text)
    if m:
        return m.group(1)
    return ""


# ── 医生姓名抽取(规则式) ─────────────────────────────────────────

_DOCTOR_STOPWORDS = {
    "我", "您", "他", "她", "医生", "大夫", "专家", "某某", "主任",
    "主任医师", "副主任医师", "主治医师", "医师",
}

_NAME_INVALID_START = {
    # 机构/地点后缀字(不会作姓氏首字)
    "院", "楼", "室", "科", "厅", "部", "所", "医", "街", "区", "村", "镇", "县", "市",
    # 方位
    "东", "南", "西", "北", "中", "上", "下", "前", "后", "内", "外",
    # 虚词
    "的", "了", "是", "有", "和", "与", "在", "就", "也", "这", "那",
    # 动词
    "挂", "找", "去", "到", "请", "给", "让", "帮", "能", "想", "要",
    # 人称
    "你", "我", "他", "她", "们",
}


def extract_doctor_name(text: str) -> str:
    """
    从用户文本抽取医生姓名(规则式)。

    策略:扫描 "医生/大夫/主任医师/副主任医师/主任" 等触发词,
    向前按 4→3→2 字长尝试取候选姓名,过滤停用词、含'医院/科'的词,
    以及常见非姓氏起始字(如'院''挂''的')。
    """
    triggers = ["主任医师", "副主任医师", "医生", "大夫", "主任"]
    for trigger in triggers:
        pos = 0
        while True:
            idx = text.find(trigger, pos)
            if idx < 0:
                break
            for length in (4, 3, 2):
                start = idx - length
                if start < 0:
                    continue
                candidate = text[start:idx]
                if not all("\u4e00" <= c <= "\u9fa5" for c in candidate):
                    continue
                if candidate in _DOCTOR_STOPWORDS:
                    continue
                if "医院" in candidate or "科" in candidate:
                    continue
                if candidate[0] in _NAME_INVALID_START:
                    continue
                return candidate
            pos = idx + len(trigger)
    return ""


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
