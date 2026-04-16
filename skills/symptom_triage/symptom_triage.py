"""
symptom_triage.py — 病情预判与科室推荐（纯本地规则引擎）

基于 yixue_knowledge.json 的关键词/权重匹配，无需 LLM / 网络请求。

公开接口:
  from symptom_triage import triage

  result = triage(
      symptom_text="老人头晕失眠，有时耳鸣",
      user_profile={"age_group": "elderly"},
      extra_answers=None,       # 对追问的回答，格式：{question_id: answer_text}
  )

返回结构:
  {
    "recommended_departments": ["神经内科", "耳鼻喉科"],
    "warning_flags":           [],          # 非空 → 提示急诊/120
    "need_more_info":          False,
    "follow_up_questions":     [],          # need_more_info=True 时非空
    "preliminary_diagnosis":   "...",       # 可读的分析结论
    "referenced_routes":       ["饮食起居辨病/失眠", "常见症状辨病/感觉器官功能异常"],
    "disclaimer":              "...",
  }
"""

import json
import logging
import os
import re
from typing import Optional

logger = logging.getLogger(__name__)

# ── 路径常量 ──────────────────────────────────────────────────────────────
_SKILL_DIR     = os.path.dirname(os.path.abspath(__file__))
KNOWLEDGE_PATH = os.path.join(_SKILL_DIR, "yixue_knowledge.json")

DISCLAIMER = (
    "⚠️ 以上判断仅供参考，不构成医学诊断，不替代执业医师意见。"
    "如症状严重或突发，请立即拨打 120 或前往最近急诊。"
)

# ── 危急症状关键词（匹配任一 → 输出 emergency） ───────────────────────────
_EMERGENCY_KEYWORDS = [
    "昏迷", "意识丧失", "意识不清", "失去意识",
    "抽搐", "惊厥",
    "窒息", "呼吸停止",
    "剧烈胸痛", "胸痛剧烈",
    "突发剧烈头痛",
    "大量出血", "出血不止",
    "口角歪斜", "半身不遂", "言语不清突发",
    "突发失明", "单眼突然失明",
    "心跳停止", "心脏骤停",
]

# ── 症状 → 科室映射表（按优先级排列，取前 N 命中）─────────────────────────
# 格式：(症状关键词列表, 科室名称, 权重)
_SYMPTOM_DEPT_MAP = [
    # 循环系统
    (["胸痛", "心悸", "心跳快", "心慌", "心律不齐", "早搏", "高血压", "血压高",
      "动脉硬化", "冠心病", "心绞痛", "心肌", "心脏病"], "心内科", 10),

    # 神经系统（头晕/头痛/失眠在此权重高）
    (["头痛", "头晕", "眩晕", "偏头痛", "失眠", "记忆力下降", "记忆力差",
      "帕金森", "震颤", "手抖", "麻木", "肢体无力", "癫痫", "脑梗", "脑出血",
      "痴呆", "老年痴呆"], "神经内科", 10),

    # 骨骼肌肉
    (["腰疼", "腰痛", "腰酸", "颈椎", "颈痛", "颈部酸痛", "肩痛", "肩膀痛",
      "膝盖痛", "关节痛", "关节肿", "骨折", "扭伤", "骨质疏松", "椎间盘",
      "腰椎", "腰突", "腰肌劳损", "骨刺", "风湿", "痛风"], "骨科", 10),

    # 呼吸系统
    (["咳嗽", "咳痰", "气喘", "气短", "呼吸困难", "喘息", "哮喘", "支气管",
      "肺炎", "肺部感染", "肺结核", "咯血", "胸闷", "发热", "发烧",
      "感冒", "流感", "鼻塞", "流鼻涕"], "呼吸内科", 10),

    # 消化系统
    (["腹痛", "胃痛", "胃胀", "腹胀", "恶心", "呕吐", "腹泻", "拉肚子",
      "便秘", "消化不良", "胃炎", "胃溃疡", "肠炎", "胆囊炎", "胆结石",
      "肝炎", "肝硬化", "黄疸", "反酸", "烧心", "大便带血", "便血"], "消化内科", 10),

    # 内分泌/代谢
    (["血糖高", "糖尿病", "多饮多尿", "体重骤降", "甲状腺", "甲亢", "甲减",
      "激素异常", "痛风", "高尿酸", "代谢综合征", "肥胖症"], "内分泌科", 10),

    # 泌尿系统
    (["尿频", "尿急", "尿痛", "血尿", "尿道炎", "肾结石", "肾炎", "肾功能",
      "前列腺", "泌尿感染", "小便异常"], "泌尿外科", 10),

    # 皮肤
    (["皮疹", "皮肤痒", "皮肤红", "荨麻疹", "湿疹", "银屑病", "牛皮癣",
      "痤疮", "皮炎", "过敏性皮炎", "皮肤病", "脱发", "白癜风"], "皮肤科", 10),

    # 眼科
    (["眼睛痛", "视力下降", "视力模糊", "近视", "远视", "眼红", "眼充血",
      "白内障", "青光眼", "结膜炎", "干眼症", "飞蚊症"], "眼科", 10),

    # 耳鼻喉科（耳鸣独立权重高）
    (["耳鸣", "耳聋", "听力下降", "耳痛", "耳朵", "鼻炎", "过敏性鼻炎",
      "鼻窦炎", "咽炎", "扁桃体", "喉咙痛", "嗓子痛", "声音嘶哑"], "耳鼻喉科", 10),

    # 口腔
    (["牙痛", "牙齿", "蛀牙", "龋齿", "智齿", "口腔溃疡", "牙龈出血",
      "口臭", "牙周病"], "口腔科", 10),

    # 妇科
    (["月经", "痛经", "月经不调", "妇科", "白带", "宫颈", "卵巢",
      "乳房", "乳腺", "产检", "怀孕", "妊娠", "更年期", "子宫"], "妇科", 10),

    # 儿科（含特征词）
    (["孩子", "小孩", "宝宝", "婴儿", "幼儿", "小儿", "儿童", "小朋友",
      "发育迟缓", "疫苗", "儿科"], "儿科", 10),

    # 肿瘤
    (["肿瘤", "恶性", "癌症", "肿块", "淋巴结肿大", "化疗", "放疗"], "肿瘤科", 10),

    # 精神/心理
    (["焦虑", "抑郁", "情绪低落", "精神压力", "心理咨询", "恐惧", "强迫症",
      "睡眠障碍", "精神科", "心理问题"], "精神科", 10),

    # 普通外科
    (["阑尾炎", "疝气", "胆囊", "痔疮", "肛瘘", "肛裂", "甲状腺结节",
      "淋巴结切除"], "普外科", 10),

    # 耳鸣补充（老年人耳鸣歧义，同时推荐神经内科）
    (["耳鸣", "失眠", "头晕"], "神经内科", 5),  # 权重5，作为次推
]

# ── 追问规则 ──────────────────────────────────────────────────────────────
_FOLLOW_UP_TEMPLATES = [
    {
        "id": "symptom_location",
        "question": "请告诉我症状主要在哪个部位？（如：胸部、腹部、头部、腰部、关节…）",
    },
    {
        "id": "symptom_duration",
        "question": "这个症状持续多久了？（如：今天刚出现、几天了、超过一周…）",
    },
]


# ══════════════════════════════════════════════════════════════════════════
# 公开接口
# ══════════════════════════════════════════════════════════════════════════

def triage(symptom_text: str,
           user_profile: Optional[dict] = None,
           extra_answers: Optional[dict] = None) -> dict:
    """
    对用户症状进行本地规则匹配，返回推荐科室和分析结论。

    Parameters
    ----------
    symptom_text  : 用户自然语言描述（症状/就医需求）
    user_profile  : {"age_group": "elderly"|"adult"|"child"}
    extra_answers : 对追问的回答 {question_id: answer_text}

    Returns
    -------
    dict — 见模块级文档
    """
    user_profile = user_profile or {}
    age_group    = user_profile.get("age_group", "adult")

    # 将追问回答合并到症状文本中，扩充匹配信息
    full_text = symptom_text
    if extra_answers:
        full_text += "。" + "。".join(extra_answers.values())

    logger.info(f"[symptom_triage] 开始分诊，全文: {full_text[:80]}")

    # ── 1. 危急症状检测 ───────────────────────────────────────────────
    warning_flags = _detect_emergency(full_text)
    if warning_flags:
        logger.warning(f"[symptom_triage] 危急症状: {warning_flags}")
        return _build_result(
            departments=["急诊科"],
            warnings=warning_flags,
            need_more_info=False,
            follow_up=[],
            diagnosis="检测到危急症状，请立即就近急诊或拨打 120！",
            routes=[],
        )

    # ── 2. 年龄组特殊处理 ─────────────────────────────────────────────
    if age_group == "child":
        full_text = "儿童 " + full_text   # 触发儿科关键词
    elif age_group == "elderly":
        # 老年人头晕耳鸣优先推神经内科
        if "头晕" in full_text or "耳鸣" in full_text:
            full_text += " 老年人"

    # ── 3. 科室匹配 ───────────────────────────────────────────────────
    department_scores: dict[str, int] = {}
    matched_keywords: dict[str, list] = {}

    for keywords, dept, weight in _SYMPTOM_DEPT_MAP:
        for kw in keywords:
            if kw in full_text:
                department_scores[dept] = department_scores.get(dept, 0) + weight
                matched_keywords.setdefault(dept, []).append(kw)
                break  # 每条规则只计一次分

    # ── 4. 排序取 Top-3 ───────────────────────────────────────────────
    sorted_depts = sorted(department_scores.items(), key=lambda x: -x[1])
    top_depts    = [d for d, _ in sorted_depts[:3]] if sorted_depts else []

    # ── 5. 判断是否需要追问 ───────────────────────────────────────────
    need_more = False
    follow_up_questions = []

    if not top_depts:
        # 完全无法判断，必须追问
        need_more = True
        follow_up_questions = _FOLLOW_UP_TEMPLATES.copy()
    elif len(full_text.strip()) < 6 and not extra_answers:
        # 描述过于简短，补充一问
        need_more = True
        follow_up_questions = [_FOLLOW_UP_TEMPLATES[1]]  # 问持续时间

    # ── 6. 推断参考路由 ───────────────────────────────────────────────
    referenced_routes = _match_routes(full_text)

    # ── 7. 生成初步判断文字 ───────────────────────────────────────────
    diagnosis = _build_diagnosis(full_text, top_depts, matched_keywords, age_group)

    return _build_result(
        departments=top_depts,
        warnings=[],
        need_more_info=need_more,
        follow_up=follow_up_questions,
        diagnosis=diagnosis,
        routes=referenced_routes,
    )


# ══════════════════════════════════════════════════════════════════════════
# 内部实现
# ══════════════════════════════════════════════════════════════════════════

def _detect_emergency(text: str) -> list:
    """检测危急关键词，返回命中词列表（空列表 = 无危急）"""
    return [kw for kw in _EMERGENCY_KEYWORDS if kw in text]


def _match_routes(text: str) -> list:
    """
    根据症状文本，猜测与 yixue_knowledge.json 中最相关的路由。
    优先从本地知识库做关键词搜索，降级时直接返回推断路由。
    """
    routes = []
    route_hints = {
        "头痛":     "常见症状辨病/疼痛/头痛",
        "胸痛":     "常见症状辨病/疼痛/胸痛",
        "腹痛":     "常见症状辨病/疼痛/腹痛",
        "腰":       "常见症状辨病/疼痛/腰背痛",
        "发热":     "常见症状辨病/发热",
        "发烧":     "常见症状辨病/发热",
        "咳嗽":     "常见症状辨病/咳嗽",
        "失眠":     "饮食起居辨病/失眠",
        "耳鸣":     "常见症状辨病/感觉器官功能异常",
        "恶心":     "常见症状辨病/恶心与呕吐",
        "呕吐":     "常见症状辨病/恶心与呕吐",
        "心悸":     "常见症状辨病/心悸",
        "皮肤":     "观察机体局部辨病/皮肤",
        "浮肿":     "常见症状辨病/水肿",
        "水肿":     "常见症状辨病/水肿",
        "小便":     "观察分泌物排泄物辨病/小便",
        "大便":     "观察分泌物排泄物辨病/大便",
        "便血":     "常见症状辨病/便血",
        "月经":     "妇科疾病/月经和白带",
        "乳房":     "妇科疾病/乳房",
        "儿童":     "儿童疾病/常见症状",
        "宝宝":     "儿童疾病/常见症状",
    }
    seen = set()
    for kw, route in route_hints.items():
        if kw in text and route not in seen:
            routes.append(route)
            seen.add(route)
    return routes[:3]  # 最多返回 3 条


def _build_diagnosis(text: str, departments: list,
                     matched_kws: dict, age_group: str) -> str:
    """生成面向用户的可读分析结论"""
    if not departments:
        return "根据描述暂时无法判断具体科室，请提供更多症状细节。"

    main_dept = departments[0]
    kws = matched_kws.get(main_dept, [])
    kw_str = "、".join(kws[:3]) if kws else "相关症状"

    diagnosis = f"根据「{kw_str}」等症状描述，初步建议就诊【{main_dept}】。"

    if len(departments) > 1:
        other = "、".join(departments[1:])
        diagnosis += f"如症状涉及多方面，也可考虑同时就诊【{other}】。"

    # 老年人附加提示
    if age_group == "elderly":
        diagnosis += "（老年患者建议同时关注共病风险，就诊时请携带既往病历及检查报告。）"
    elif age_group == "child":
        diagnosis += "（儿童患者建议优先前往儿科门诊由儿科医生综合评估。）"

    return diagnosis


def _build_result(departments, warnings, need_more_info,
                  follow_up, diagnosis, routes) -> dict:
    return {
        "recommended_departments": departments,
        "warning_flags":           warnings,
        "need_more_info":          need_more_info,
        "follow_up_questions":     follow_up,
        "preliminary_diagnosis":   diagnosis,
        "referenced_routes":       routes,
        "disclaimer":              DISCLAIMER,
    }


# ══════════════════════════════════════════════════════════════════════════
# 知识库增强查询（可选，若 yixue_knowledge.json 存在则补充匹配）
# ══════════════════════════════════════════════════════════════════════════

_knowledge_cache: dict | None = None


def _load_knowledge() -> dict:
    """懒加载知识库，返回 {route: page_dict}。文件不存在时返回空字典。"""
    global _knowledge_cache
    if _knowledge_cache is not None:
        return _knowledge_cache
    if not os.path.exists(KNOWLEDGE_PATH):
        logger.warning(f"[symptom_triage] 知识库不存在: {KNOWLEDGE_PATH}，使用纯规则模式")
        _knowledge_cache = {}
        return _knowledge_cache
    try:
        with open(KNOWLEDGE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        _knowledge_cache = data.get("pages", {})
        logger.info(f"[symptom_triage] 加载知识库 {len(_knowledge_cache)} 条")
    except Exception as e:
        logger.warning(f"[symptom_triage] 知识库加载失败: {e}")
        _knowledge_cache = {}
    return _knowledge_cache


# ── CLI 快速测试 ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json as _json

    test_cases = [
        ("老人头晕失眠，有时耳鸣", {"age_group": "elderly"}),
        ("最近腰疼，想看骨科", {"age_group": "adult"}),
        ("孩子发烧38度，咳嗽两天了", {"age_group": "child"}),
        ("突然剧烈胸痛，感觉快晕倒", None),
        ("不舒服", None),
    ]

    for text, profile in test_cases:
        print(f"\n{'='*60}")
        print(f"输入: {text}")
        result = triage(symptom_text=text, user_profile=profile)
        print(f"推荐科室: {result['recommended_departments']}")
        print(f"危急标志: {result['warning_flags']}")
        print(f"需追问: {result['need_more_info']}")
        print(f"初步判断: {result['preliminary_diagnosis']}")
        if result['follow_up_questions']:
            for q in result['follow_up_questions']:
                print(f"  追问: {q['question']}")
