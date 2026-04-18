"""
symptom_triage.py — 病情预判与科室推荐

基于本地 yixue_knowledge.json 知识库，通过关键词匹配实现：
  1. 危急症状检测（胸痛、卒中、大出血等）
  2. 科室推荐（基于症状关键词映射）
  3. 信息不足追问

输入：
  symptom_text   str   用户症状描述
  user_profile   dict  {"age_group": "elderly"|"adult"|"child"}
  extra_answers  dict  对追问的回答 {question_id: answer}

输出：
  {
    "warning_flags":           list  危急提示
    "need_more_info":          bool  是否需追问
    "follow_up_questions":     list  [{id, question}]
    "recommended_departments": list  推荐科室（第一项为主科室）
    "preliminary_diagnosis":   str   初步判断
    "referenced_routes":       list  参考的知识库路由
    "disclaimer":              str   免责声明
  }
"""

import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

_SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
KNOWLEDGE_PATH = os.path.join(_SKILL_DIR, "yixue_knowledge.json")

# ── 危急症状关键词（来自 yixue 知识库内容）──────────────────────────
EMERGENCY_KEYWORDS = [
    "剧烈胸痛", "胸痛", "心肌梗塞", "心梗",
    "脑卒中", "口角歪斜", "半身不遂", "突然晕倒",
    "呼吸停止", "呼吸困难", "窒息",
    "大出血", "大量出血", "吐血", "便血鲜红",
    "失去意识", "昏迷", "意识不清",
    "抽搐", "癫痫发作",
    "休克", "血压骤降",
]

# ── 症状→科室映射（基于 yixue 知识库路由）──────────────────────────
SYMPTOM_DEPT_MAP = [
    # 骨科
    (["腰痛", "腰疼", "腰背痛", "颈椎", "背痛", "骨折", "关节痛", "关节", "骨头"], "骨科"),
    # 神经内科
    (["头痛", "头疼", "头晕", "眩晕", "失眠", "睡眠", "记忆力", "手脚麻木"], "神经内科"),
    # 心内科
    (["心悸", "心跳", "心慌", "胸闷"], "心内科"),
    # 呼吸科
    (["咳嗽", "咳痰", "呼吸", "哮喘", "气喘", "痰"], "呼吸科"),
    # 消化内科
    (["腹痛", "腹泻", "恶心", "呕吐", "胃痛", "胃", "消化", "拉肚子", "便秘"], "消化内科"),
    # 感染科/内科
    (["发热", "发烧", "体温", "高烧", "低烧"], "感染科"),
    # 耳鼻喉科
    (["鼻出血", "流鼻血", "耳鸣", "耳朵", "听力", "咽喉", "喉咙"], "耳鼻喉科"),
    # 皮肤科
    (["皮肤", "皮疹", "痒", "红疹", "湿疹"], "皮肤科"),
    # 泌尿科
    (["尿频", "尿急", "尿痛", "小便", "排尿"], "泌尿科"),
    # 妇科
    (["月经", "白带", "阴道", "妇科", "例假"], "妇科"),
    # 儿科
    (["儿童", "小孩", "宝宝", "婴儿", "孩子"], "儿科"),
    # 眼科
    (["眼睛", "视力", "眼", "看不清"], "眼科"),
]

DISCLAIMER = "⚠️ 以上判断仅供参考，不构成医学诊断，不替代执业医师意见。如症状严重或突发，请立即拨打 120 或前往最近急诊。"


def triage(symptom_text: str,
           user_profile: Optional[dict] = None,
           extra_answers: Optional[dict] = None) -> dict:
    """
    病情预判与科室推荐主函数。

    Returns
    -------
    dict — 见模块级文档
    """
    user_profile = user_profile or {}
    extra_answers = extra_answers or {}
    age_group = user_profile.get("age_group", "adult")

    logger.info(f"[symptom_triage] 输入: {symptom_text[:50]}")

    # ── Step 1: 危急检测 ──────────────────────────────────────────
    warning_flags = _detect_emergency(symptom_text)
    if warning_flags:
        logger.warning(f"[symptom_triage] 检测到危急症状: {warning_flags}")
        return {
            "warning_flags": warning_flags,
            "need_more_info": False,
            "follow_up_questions": [],
            "recommended_departments": [],
            "preliminary_diagnosis": "检测到危急症状，建议立即就近急诊或拨打 120！",
            "referenced_routes": ["常见症状辨病/疼痛/胸痛", "常见症状辨病/心悸"],
            "disclaimer": DISCLAIMER,
        }

    # ── Step 2: 信息不足检测 ──────────────────────────────────────
    if len(symptom_text.strip()) < 5:
        return {
            "warning_flags": [],
            "need_more_info": True,
            "follow_up_questions": [
                {"id": "symptom_detail", "question": "请详细描述您的不适症状（如疼痛部位、持续时间等）"},
                {"id": "duration", "question": "症状持续多久了？"},
            ],
            "recommended_departments": [],
            "preliminary_diagnosis": "信息不足，需要更多症状描述",
            "referenced_routes": [],
            "disclaimer": DISCLAIMER,
        }

    # ── Step 3: 科室推荐 ──────────────────────────────────────────
    departments = _match_departments(symptom_text, age_group)

    if not departments:
        # 无匹配 → 追问
        return {
            "warning_flags": [],
            "need_more_info": True,
            "follow_up_questions": [
                {"id": "symptom_location", "question": "不适的具体部位在哪里？（如头部、胸部、腹部等）"},
                {"id": "symptom_nature", "question": "是疼痛、发热、还是其他症状？"},
            ],
            "recommended_departments": [],
            "preliminary_diagnosis": "症状描述不够明确，需要进一步了解",
            "referenced_routes": ["常见症状辨病"],
            "disclaimer": DISCLAIMER,
        }

    # ── Step 4: 生成初步判断 ──────────────────────────────────────
    diagnosis = _generate_diagnosis(symptom_text, departments, age_group)
    referenced = _get_referenced_routes(departments)

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


# ── 内部函数 ──────────────────────────────────────────────────────

def _detect_emergency(text: str) -> list:
    """检测危急症状关键词"""
    flags = []
    for keyword in EMERGENCY_KEYWORDS:
        if keyword in text:
            flags.append(f"检测到「{keyword}」，可能为急症")
    return flags


def _match_departments(text: str, age_group: str) -> list:
    """
    基于关键词匹配推荐科室。
    返回最多 3 个科室，按匹配度排序。
    """
    matches = []

    # 儿童优先儿科
    if age_group == "child":
        for keywords, dept in SYMPTOM_DEPT_MAP:
            if dept == "儿科":
                matches.append((dept, 10))  # 高优先级
                break

    # 关键词匹配
    for keywords, dept in SYMPTOM_DEPT_MAP:
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            matches.append((dept, score))

    # 去重并排序
    dept_scores = {}
    for dept, score in matches:
        dept_scores[dept] = dept_scores.get(dept, 0) + score

    sorted_depts = sorted(dept_scores.items(), key=lambda x: x[1], reverse=True)
    return [dept for dept, _ in sorted_depts[:3]]


def _generate_diagnosis(text: str, departments: list, age_group: str) -> str:
    """生成用户可读的初步判断"""
    main_dept = departments[0] if departments else "内科"

    diagnosis = f"根据您描述的症状，建议优先就诊【{main_dept}】。"

    if len(departments) > 1:
        others = "、".join(departments[1:])
        diagnosis += f" 也可考虑【{others}】。"

    if age_group == "elderly":
        diagnosis += " 老年人如有多种慢性病，建议携带既往病历和用药清单。"
    elif age_group == "child":
        diagnosis += " 儿童就诊建议由家长陪同，携带疫苗接种记录。"

    return diagnosis


def _get_referenced_routes(departments: list) -> list:
    """根据科室返回对应的知识库路由"""
    route_map = {
        "骨科": ["常见症状辨病/疼痛/腰背痛"],
        "神经内科": ["常见症状辨病/疼痛/头痛", "饮食起居辨病/失眠"],
        "心内科": ["常见症状辨病/心悸", "常见症状辨病/疼痛/胸痛"],
        "呼吸科": ["常见症状辨病/咳嗽"],
        "消化内科": ["常见症状辨病/疼痛/腹痛", "常见症状辨病/恶心与呕吐"],
        "感染科": ["常见症状辨病/发热"],
        "儿科": ["儿童疾病/常见症状"],
    }

    routes = []
    for dept in departments:
        routes.extend(route_map.get(dept, []))

    return routes[:3]  # 最多返回 3 条


# ── 便捷入口（AutoClaw / GLM 统一调用）────────────────────────────

def run(symptom_text: str, **kwargs) -> dict:
    """AutoClaw / GLM 调用的统一入口"""
    return triage(
        symptom_text=symptom_text,
        user_profile=kwargs.get("user_profile"),
        extra_answers=kwargs.get("extra_answers"),
    )


# ── 命令行快速测试 ────────────────────────────────────────────────

if __name__ == "__main__":
    test_cases = [
        ("老人头晕失眠两周了", {"age_group": "elderly"}),
        ("最近腰疼，想看骨科", {"age_group": "adult"}),
        ("剧烈胸痛，呼吸困难", {"age_group": "adult"}),
        ("咳嗽", {"age_group": "adult"}),
    ]

    for text, profile in test_cases:
        print(f"\n── 测试：{text} ──")
        result = triage(text, user_profile=profile)
        print(f"危急: {result['warning_flags']}")
        print(f"科室: {result['recommended_departments']}")
        print(f"判断: {result['preliminary_diagnosis']}")
        print(f"追问: {result['need_more_info']}")
