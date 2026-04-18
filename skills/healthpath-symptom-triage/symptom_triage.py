"""
symptom_triage.py - 病情预判与科室推荐

基于 semantic_matcher 对 yixue_knowledge.json 做语义检索，实现：
1. 危急症状检测
2. 科室推荐
3. 信息不足时追问
"""

import logging
import os
import sys

_SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
_CONFIG_DIR = os.path.join(_SKILL_DIR, "..", "..", "config")
if _CONFIG_DIR not in sys.path:
    sys.path.insert(0, _CONFIG_DIR)

from semantic_matcher import detect_emergency, normalize_symptoms, search_knowledge

logger = logging.getLogger(__name__)

DISCLAIMER = (
    "⚠️ 以上判断仅供参考，不构成医学诊断，不替代执业医师意见。"
    "如症状严重或突发，请立即拨打 120 或前往最近急诊。"
)

_ROUTE_DEPT: list[tuple[str, str]] = [
    ("常见症状辨病/疼痛/头痛", "神经内科"),
    ("常见症状辨病/疼痛/胸痛", "心内科"),
    ("常见症状辨病/疼痛/腹痛", "消化内科"),
    ("常见症状辨病/疼痛/腰背痛", "骨科"),
    ("常见症状辨病/心悸", "心内科"),
    ("常见症状辨病/发热", "发热门诊"),
    ("常见症状辨病/咳嗽", "呼吸科"),
    ("常见症状辨病/咯血", "呼吸科"),
    ("常见症状辨病/便血", "消化内科"),
    ("常见症状辨病/呕血", "消化内科"),
    ("常见症状辨病/恶心与呕吐", "消化内科"),
    ("常见症状辨病/尿血", "泌尿科"),
    ("常见症状辨病/鼻出血", "耳鼻喉科"),
    ("常见症状辨病/水肿", "肾内科"),
    ("常见症状辨病/皮肤粘膜出血", "血液科"),
    ("常见症状辨病/感觉器官功能异常", "神经内科"),
    ("观察机体局部辨病/眼睛", "眼科"),
    ("观察机体局部辨病/皮肤", "皮肤科"),
    ("观察机体局部辨病/口腔", "口腔科"),
    ("观察机体局部辨病/四肢形态", "骨科"),
    ("观察机体局部辨病/脊柱", "骨科"),
    ("观察机体局部辨病/颈部", "骨科"),
    ("观察机体局部辨病/胸廓形态", "呼吸科"),
    ("观察机体局部辨病/脉搏", "心内科"),
    ("观察机体局部辨病/腹部", "消化内科"),
    ("观察机体局部辨病/头颅", "神经内科"),
    ("观察机体局部辨病/毛发", "皮肤科"),
    ("观察机体局部辨病/眉毛", "内分泌科"),
    ("观察机体局部辨病/鼻", "耳鼻喉科"),
    ("观察机体局部辨病/耳", "耳鼻喉科"),
    ("观察分泌物排泄物辨病/痰液", "呼吸科"),
    ("观察分泌物排泄物辨病/鼻涕", "耳鼻喉科"),
    ("观察分泌物排泄物辨病/大便", "消化内科"),
    ("观察分泌物排泄物辨病/小便", "泌尿科"),
    ("观察分泌物排泄物辨病/汗液异常", "内分泌科"),
    ("饮食起居辨病/失眠", "神经内科"),
    ("饮食起居辨病/嗜睡", "神经内科"),
    ("饮食起居辨病/睡眠", "神经内科"),
    ("饮食起居辨病/说话异常", "神经内科"),
    ("饮食起居辨病/运动异常", "神经内科"),
    ("饮食起居辨病/饮食", "消化内科"),
    ("妇科疾病/", "妇科"),
    ("儿童疾病/", "儿科"),
]

_PARENT_ONLY_ROUTES = {
    "常见症状辨病",
    "常见症状辨病/疼痛",
    "常见症状辨病/出血",
    "神色形态辨病",
    "观察机体局部辨病",
    "观察分泌物排泄物辨病",
    "饮食起居辨病",
    "儿童疾病",
    "妇科疾病",
}

_TERM_DEPT_RULES = {
    "体位性头晕": {"boost": {"神经内科": 3.0, "心内科": 2.5}, "suppress": {"眼科": 2.5}},
    "黑矇": {"boost": {"神经内科": 2.5, "心内科": 2.0}, "suppress": {"眼科": 2.0}},
    "尿痛": {"boost": {"泌尿科": 4.0}, "suppress": {"消化内科": 3.0, "儿科": 1.5}},
    "心悸": {"boost": {"心内科": 4.0}, "suppress": {"肾内科": 2.5}},
    "呼吸困难": {"boost": {"呼吸科": 2.0, "心内科": 1.5}, "suppress": {}},
    "发热": {"boost": {"发热门诊": 3.5, "呼吸科": 2.0, "感染科": 2.0}, "suppress": {"神经内科": 3.0, "骨科": 2.0}},
    "关节炎": {"boost": {"骨科": 3.5, "风湿免疫科": 3.0}, "suppress": {"妇科": 5.0, "神经内科": 2.0}},
    "耳痛": {"boost": {"耳鼻喉科": 4.0}, "suppress": {"神经内科": 4.0}},
    "耳鸣": {"boost": {"耳鼻喉科": 4.0}, "suppress": {"神经内科": 4.0}},
    "颈部僵硬": {"boost": {"骨科": 3.5, "康复科": 2.5}, "suppress": {"神经内科": 3.0}},
}


def triage(symptom_text: str, user_profile: dict | None = None, extra_answers: dict | None = None) -> dict:
    user_profile = user_profile or {}
    extra_answers = extra_answers or {}
    age_group = user_profile.get("age_group", "adult")
    normalized = normalize_symptoms(symptom_text)

    logger.info(f"[symptom_triage] 输入: {symptom_text[:60]}")

    if len(symptom_text.strip()) < 5 and not normalized["canonical_terms"]:
        return _need_more(
            diagnosis="信息不足，需要更多症状描述。",
            questions=[
                {"id": "symptom_detail", "question": "请详细描述您的不适症状，例如部位、性质和持续时间。"},
                {"id": "duration", "question": "症状持续多久了？"},
            ],
            routes=[],
        )

    flags = detect_emergency(symptom_text)
    if flags:
        logger.warning(f"[symptom_triage] 检测到危急症状: {flags}")
        return {
            "warning_flags": flags,
            "need_more_info": False,
            "follow_up_questions": [],
            "recommended_departments": [],
            "preliminary_diagnosis": "检测到危急症状，建议立即就近急诊或拨打 120。",
            "referenced_routes": ["常见症状辨病/疼痛/胸痛", "常见症状辨病/心悸"],
            "disclaimer": DISCLAIMER,
        }

    hits = search_knowledge(symptom_text, k=5)
    logger.info(f"[symptom_triage] 检索命中: {[(h['route'], h['score']) for h in hits]}")

    if not hits:
        return _need_more(
            diagnosis="暂未能稳定识别症状，需要进一步描述。",
            questions=[
                {"id": "symptom_location", "question": "不适的具体部位在哪里？例如头部、胸部、腹部。"},
                {"id": "symptom_nature", "question": "主要是疼痛、发热、头晕还是其他症状？"},
            ],
            routes=[],
        )

    top_route = hits[0]["route"]
    if top_route in _PARENT_ONLY_ROUTES:
        return _need_more(
            diagnosis="症状描述还不够具体，需要进一步了解。",
            questions=[
                {"id": "symptom_location", "question": "不适的具体部位在哪里？"},
                {"id": "symptom_nature", "question": "症状更像疼痛、发热、头晕还是排尿异常？"},
            ],
            routes=[h["route"] for h in hits[:3]],
        )

    departments = _rank_departments(symptom_text, hits, age_group)
    referenced = [h["route"] for h in hits[:3]]
    diagnosis = _generate_diagnosis(symptom_text, departments, hits[0], age_group)

    logger.info(f"[symptom_triage] 推荐科室: {departments}")

    return {
        "warning_flags": [],
        "need_more_info": False,
        "follow_up_questions": [],
        "recommended_departments": departments,
        "preliminary_diagnosis": diagnosis,
        "referenced_routes": referenced,
        "disclaimer": DISCLAIMER,
    }


def _route_to_dept(route: str) -> str | None:
    for prefix, dept in _ROUTE_DEPT:
        if route.startswith(prefix):
            return dept
    return None


def _rank_departments(symptom_text: str, hits: list[dict], age_group: str) -> list[str]:
    normalized = normalize_symptoms(symptom_text)
    scores: dict[str, float] = {}

    for idx, hit in enumerate(hits[:5]):
        route = hit["route"]
        if route in _PARENT_ONLY_ROUTES:
            continue
        dept = _route_to_dept(route)
        if not dept:
            continue
        weight = 3.0 if idx == 0 else 1.5 if idx == 1 else 0.8
        scores[dept] = scores.get(dept, 0.0) + weight + float(hit["score"])

    for term in normalized["canonical_terms"]:
        rule = _TERM_DEPT_RULES.get(term)
        if not rule:
            continue
        for dept, boost in rule.get("boost", {}).items():
            scores[dept] = scores.get(dept, 0.0) + boost
        for dept, suppress in rule.get("suppress", {}).items():
            scores[dept] = scores.get(dept, 0.0) - suppress

    if age_group == "child":
        scores["儿科"] = scores.get("儿科", 0.0) + 0.5

    ranked_pairs = [(dept, score) for dept, score in sorted(scores.items(), key=lambda item: item[1], reverse=True) if score > 0]
    if not ranked_pairs:
        return _hits_to_departments(hits, age_group)

    if len(ranked_pairs) == 1:
        return [ranked_pairs[0][0]]

    top_dept, top_score = ranked_pairs[0]
    second_dept, second_score = ranked_pairs[1]
    if second_score < top_score * 0.75 or top_score - second_score > 2.0:
        return [top_dept]
    return [top_dept, second_dept]


def _hits_to_departments(hits: list[dict], age_group: str) -> list[str]:
    depts = []
    for hit in hits:
        if hit["route"] in _PARENT_ONLY_ROUTES:
            continue
        dept = _route_to_dept(hit["route"])
        if dept and dept not in depts:
            depts.append(dept)

    if age_group == "child" and "儿科" not in depts:
        depts = ["儿科"] + depts

    return depts[:2]


def _generate_diagnosis(text: str, departments: list[str], top_hit: dict, age_group: str) -> str:
    main_dept = departments[0] if departments else "内科"
    route_label = top_hit["route"].replace("/", " -> ")

    diagnosis = f"根据您描述的症状，建议优先就诊【{main_dept}】。"
    diagnosis += f"（参考：{route_label}）"

    if len(departments) > 1:
        diagnosis += f" 备选可考虑【{departments[1]}】。"

    if age_group == "elderly":
        diagnosis += " 老年患者建议携带既往病史和用药清单。"
    elif age_group == "child":
        diagnosis += " 儿童就诊建议由家长陪同。"

    return diagnosis


def _need_more(diagnosis: str, questions: list[dict], routes: list[str]) -> dict:
    return {
        "warning_flags": [],
        "need_more_info": True,
        "follow_up_questions": questions,
        "recommended_departments": [],
        "preliminary_diagnosis": diagnosis,
        "referenced_routes": routes,
        "disclaimer": DISCLAIMER,
    }


def run(symptom_text: str, **kwargs) -> dict:
    return triage(
        symptom_text=symptom_text,
        user_profile=kwargs.get("user_profile"),
        extra_answers=kwargs.get("extra_answers"),
    )


if __name__ == "__main__":
    test_cases = [
        ("老人头晕失眠两周了", {"age_group": "elderly"}),
        ("最近腰不舒服，上楼梯膝盖响", {"age_group": "adult"}),
        ("剧烈胸痛，呼吸困难", {"age_group": "adult"}),
        ("拉稀水样便，肚子一阵一阵疼", {"age_group": "adult"}),
        ("小便时刺痛，尿急", {"age_group": "adult"}),
        ("心里扑腾扑腾的，喘不上气", {"age_group": "adult"}),
        ("眼前发黑，站起来头晕", {"age_group": "adult"}),
        ("痛", {"age_group": "adult"}),
    ]

    for text, profile in test_cases:
        print(f"\n=== 测试：{text} ===")
        result = triage(text, user_profile=profile)
        print(f"  危急: {result['warning_flags']}")
        print(f"  科室: {result['recommended_departments']}")
        print(f"  判断: {result['preliminary_diagnosis']}")
        print(f"  路由: {result['referenced_routes']}")
        print(f"  追问: {result['need_more_info']}")
