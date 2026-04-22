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

from semantic_matcher import detect_emergency, get_knowledge, normalize_symptoms, search_knowledge

logger = logging.getLogger(__name__)

DISCLAIMER = (
    "⚠️ 以上判断仅供参考，不构成医学诊断，不替代执业医师意见。"
    "如症状严重或突发，请立即拨打 120 或前往最近急诊。"
)

_LOW_CONF_ABS = 0.45
_LOW_CONF_SOFT_NO_CANON = 0.60
_LOW_CONF_SOFT_WITH_CANON = 0.50
_LOW_CONF_GAP = 0.03

_ROUTE_DEPT: list[tuple[str, str]] | None = None
_PARENT_ONLY_ROUTES: set[str] | None = None
_TERM_DEPT_RULES: dict | None = None


def _ensure_rules() -> None:
    """首次使用时从 yixue_knowledge.json 加载路由/科室映射与打分规则。"""
    global _ROUTE_DEPT, _PARENT_ONLY_ROUTES, _TERM_DEPT_RULES
    if _ROUTE_DEPT is not None:
        return
    kb = get_knowledge()
    _ROUTE_DEPT = [(entry[0], entry[1]) for entry in kb.get("route_dept", [])]
    _PARENT_ONLY_ROUTES = set(kb.get("parent_only_routes", []))
    _TERM_DEPT_RULES = kb.get("term_dept_rules", {}) or {}


def triage(symptom_text: str, user_profile: dict | None = None, extra_answers: dict | None = None) -> dict:
    user_profile = user_profile or {}
    extra_answers = extra_answers or {}
    age_group = user_profile.get("age_group", "adult")
    _ensure_rules()
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

    top_score = hits[0]["score"]
    gap = top_score - (hits[1]["score"] if len(hits) > 1 else 0.0)
    soft_thresh = _LOW_CONF_SOFT_WITH_CANON if normalized["canonical_terms"] else _LOW_CONF_SOFT_NO_CANON
    if top_score < _LOW_CONF_ABS or (top_score < soft_thresh and gap < _LOW_CONF_GAP):
        logger.info(f"[symptom_triage] 低置信度 top={top_score:.3f} gap={gap:.3f} canon={normalized['canonical_terms']}，转追问")
        return _need_more(
            diagnosis="症状描述不够清晰，暂无法稳定判断科室，请补充更多信息。",
            questions=[
                {"id": "symptom_location", "question": "不适的具体部位在哪里？例如头部、胸部、腹部、四肢。"},
                {"id": "symptom_nature", "question": "症状更像疼痛、酸胀、发热、头晕、排尿异常还是其他？"},
                {"id": "duration", "question": "症状持续多久了？是否伴随其他不适？"},
            ],
            routes=[h["route"] for h in hits[:3]],
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
    referenced = _referenced_routes(hits, departments)
    top_for_diag = {"route": referenced[0]} if referenced else hits[0]
    diagnosis = _generate_diagnosis(symptom_text, departments, top_for_diag, age_group)

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
    _ensure_rules()
    for prefix, dept in _ROUTE_DEPT:
        if route.startswith(prefix):
            return dept
    return None


def _referenced_routes(hits: list[dict], departments: list[str]) -> list[str]:
    """展示的参考路由：只保留与最终推荐科室一致的 hits，避免被压制的误匹配路由误导用户。"""
    _ensure_rules()
    dept_set = set(departments)
    out: list[str] = []
    for h in hits:
        if h["route"] in _PARENT_ONLY_ROUTES:
            continue
        if _route_to_dept(h["route"]) in dept_set and h["route"] not in out:
            out.append(h["route"])
        if len(out) >= 3:
            break
    if not out:
        return [h["route"] for h in hits[:3]]
    return out


def _rank_departments(symptom_text: str, hits: list[dict], age_group: str) -> list[str]:
    _ensure_rules()
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
    _ensure_rules()
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
