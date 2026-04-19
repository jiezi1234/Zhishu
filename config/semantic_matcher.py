"""
semantic_matcher.py - 语义匹配器（单例）

职责：
1. 懒加载 sentence-transformers 模型（BGE 中文小模型）
2. 为 yixue_knowledge.json 构建知识库向量索引
3. 提供 search_knowledge() 和 detect_emergency() 两个公开接口

本版针对医疗分诊做了两类增强：
1. 危急识别增加规则兜底，避免短句急症被向量相似度漏掉
2. 主检索文本只使用 route / title / keywords / alias，避免长正文污染
"""

import json
import logging
import os
import sys

logger = logging.getLogger(__name__)

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_LIB_DIR = os.path.join(_BASE_DIR, "lib")
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

_cache_dir = os.path.join(
    os.environ.get("HF_HOME", os.path.expanduser("~/.cache/huggingface")),
    "hub",
)
_model_cache_exists = any(
    d.startswith("models--BAAI--bge-small-zh-v1.5")
    for d in (os.listdir(_cache_dir) if os.path.isdir(_cache_dir) else [])
)
if _model_cache_exists:
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

from sentence_transformers import SentenceTransformer
import numpy as np

_MODEL_NAME = os.environ.get("ST_MODEL", "BAAI/bge-small-zh-v1.5")
_QUERY_PREFIX = "为这个句子生成表示以用于检索相关文章："

_KNOWLEDGE_PATH = os.path.join(
    _BASE_DIR, "skills", "healthpath-symptom-triage", "yixue_knowledge.json"
)

_NORMALIZATION_RULES: list[dict] | None = None
_KNOWLEDGE: dict | None = None


def _load_knowledge() -> dict:
    """加载 yixue_knowledge.json 并缓存。医学知识数据（归一化规则、别名、关键词）集中在此文件，Python 代码不再硬编码。"""
    global _KNOWLEDGE, _NORMALIZATION_RULES
    if _KNOWLEDGE is not None:
        return _KNOWLEDGE
    with open(_KNOWLEDGE_PATH, encoding="utf-8") as f:
        _KNOWLEDGE = json.load(f)
    _NORMALIZATION_RULES = _KNOWLEDGE.get("normalize_rules", [])
    return _KNOWLEDGE


def _get_normalize_rules() -> list[dict]:
    if _NORMALIZATION_RULES is None:
        _load_knowledge()
    return _NORMALIZATION_RULES or []


def get_knowledge() -> dict:
    """对外暴露整个知识库字典，供 symptom_triage 等模块读取 route_dept / term_dept_rules 等字段。"""
    return _load_knowledge()

_EMERGENCY_ANCHORS = [
    "剧烈胸痛，压榨感，疑似心肌梗死，心脏急症发作",
    "口角歪斜，半身不遂，言语不清，疑似脑卒中中风",
    "呼吸停止，窒息，无法自主呼吸，缺氧",
    "大量出血，吐血，便血鲜红，失血过多",
    "失去意识，昏迷，叫不醒，不省人事",
    "全身抽搐，癫痫发作，惊厥",
    "休克，血压骤降，面色苍白，大汗淋漓，濒死感",
]

_EMERGENCY_RULES = [
    {
        "all_of": [
            ["胸痛", "剧烈胸痛", "胸闷", "心前区痛", "压榨样胸痛", "胸口痛", "胸口疼", "胸口剧烈", "胸部剧痛", "胸口疼痛"],
            ["呼吸困难", "喘不上气", "喘不过气", "憋气"],
        ],
        "flag": "胸痛伴呼吸困难，疑似急性心肺急症，建议立即急诊",
    },
    {
        "all_of": [
            ["胸痛", "剧烈胸痛", "胸闷", "心前区痛", "胸口痛", "胸口疼", "胸口剧烈", "胸部剧痛"],
            ["冷汗", "大汗", "面色苍白", "四肢发凉"],
        ],
        "flag": "胸痛伴冷汗或面色苍白，疑似急性冠脉综合征，建议立即急诊",
    },
    {
        "all_of": [
            ["口角歪斜", "说话不清", "言语不清", "嘴歪"],
            ["半身无力", "单侧无力", "肢体麻木", "偏瘫"],
        ],
        "flag": "疑似脑卒中，建议立即急诊",
    },
    {
        "any_of": ["昏迷", "叫不醒", "意识不清", "不省人事", "晕倒后不醒"],
        "flag": "存在意识障碍，建议立即急诊",
    },
    {
        "any_of": ["抽搐", "惊厥", "癫痫发作", "全身抖动不止"],
        "flag": "存在抽搐或惊厥，建议立即急诊",
    },
    {
        "any_of": ["大出血", "大量出血", "呕血", "便血鲜红", "咯血量大"],
        "flag": "存在大量出血风险，建议立即急诊",
    },
    {
        "any_of": ["误吞", "误食异物", "吞了个", "吞了一个", "咽下纽扣", "吞下了", "吞进去", "吞了异物"],
        "flag": "疑似误吞异物，建议立即前往急诊或儿科评估",
    },
]

_EMERGENCY_THRESHOLD = 0.75
_SEARCH_THRESHOLD = 0.40

_model: SentenceTransformer | None = None
_page_routes: list[str] | None = None
_page_vecs: np.ndarray | None = None
_page_data: dict | None = None
_emergency_vecs: np.ndarray | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        logger.info(f"[semantic_matcher] 加载模型: {_MODEL_NAME}")
        import io
        import warnings
        import logging as _logging
        # 静默 transformers LOAD REPORT 和 tqdm 进度条
        os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
        # 压制 transformers 自身的 logging（LOAD REPORT 走这条路）
        try:
            import transformers as _tf
            _tf.logging.set_verbosity_error()
        except Exception:
            pass
        _prev_level = _logging.root.level
        _logging.root.setLevel(_logging.ERROR)
        _old_stdout, _old_stderr = sys.stdout, sys.stderr
        sys.stdout = sys.stderr = io.StringIO()
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                _model = SentenceTransformer(_MODEL_NAME)
        finally:
            sys.stdout, sys.stderr = _old_stdout, _old_stderr
            _logging.root.setLevel(_prev_level)
        logger.info("[semantic_matcher] 模型加载完成")
    return _model


def _contains_any(text: str, patterns: list[str]) -> bool:
    return any(pattern in text for pattern in patterns)


def normalize_symptoms(query: str) -> dict:
    """将常见口语症状归一化为更稳定的医学短语。"""
    canonical_terms: list[str] = []
    matched_patterns: list[str] = []

    for rule in _get_normalize_rules():
        for pattern in rule["patterns"]:
            if pattern in query:
                if rule["canonical"] not in canonical_terms:
                    canonical_terms.append(rule["canonical"])
                matched_patterns.append(pattern)
                break

    return {
        "text": query,
        "canonical_terms": canonical_terms,
        "matched_patterns": matched_patterns,
    }


def _expand_query(query: str, normalized: dict) -> str:
    extras = normalized["canonical_terms"] + normalized["matched_patterns"]
    if not extras:
        return query
    return f"{query} {' '.join(extras)}"


def detect_emergency_rules(query: str, normalized: dict | None = None) -> list[str]:
    normalized = normalized or normalize_symptoms(query)
    text = _expand_query(query, normalized)
    flags: list[str] = []

    for rule in _EMERGENCY_RULES:
        matched = False
        if "all_of" in rule:
            matched = all(_contains_any(text, group) for group in rule["all_of"])
        elif "any_of" in rule:
            matched = _contains_any(text, rule["any_of"])
        if matched:
            flags.append(rule["flag"])

    return flags


def _make_doc_text(route: str, page: dict) -> str:
    kws = page.get("keywords") or []
    aliases = page.get("aliases") or []
    parts = [route, page.get("title") or ""]
    parts.extend(kws)
    parts.extend(aliases)
    return " ".join(part for part in parts if part)


def _build_index() -> None:
    global _page_routes, _page_vecs, _page_data, _emergency_vecs

    if _page_routes is not None:
        return

    logger.info("[semantic_matcher] 构建知识库索引...")
    data = _load_knowledge()

    pages = data["pages"]
    _page_data = pages

    routes = []
    doc_texts = []
    for route, page in pages.items():
        routes.append(route)
        doc_texts.append(_make_doc_text(route, page))

    model = _get_model()
    doc_vecs = model.encode(doc_texts, normalize_embeddings=True, show_progress_bar=False)
    emg_vecs = model.encode(_EMERGENCY_ANCHORS, normalize_embeddings=True, show_progress_bar=False)

    _page_routes = routes
    _page_vecs = np.array(doc_vecs)
    _emergency_vecs = np.array(emg_vecs)

    logger.info(f"[semantic_matcher] 索引完成，共 {len(routes)} 个条目")


def search_knowledge(query: str, k: int = 5) -> list[dict]:
    """
    语义检索知识库，返回最相关的 page 列表（已去除被子节点覆盖的父节点）。
    """
    _build_index()
    model = _get_model()

    normalized = normalize_symptoms(query)
    expanded_query = _expand_query(query, normalized)
    q_vec = model.encode(_QUERY_PREFIX + expanded_query, normalize_embeddings=True)
    scores: np.ndarray = _page_vecs @ q_vec

    top_n = min(k * 2, len(_page_routes))
    top_idx = scores.argsort()[::-1][:top_n]

    results = []
    for i in top_idx:
        score = float(scores[i])
        if score < _SEARCH_THRESHOLD:
            break
        results.append(
            {
                "route": _page_routes[i],
                "score": round(score, 4),
                "page": _page_data[_page_routes[i]],
            }
        )

    results = _deduplicate_by_hierarchy(results)
    return results[:k]


def detect_emergency(query: str) -> list[str]:
    """
    检测急症。优先使用规则兜底，避免危急短句漏报；向量相似度仅作补充。
    """
    normalized = normalize_symptoms(query)
    rule_flags = detect_emergency_rules(query, normalized)
    if rule_flags:
        return rule_flags

    _build_index()
    model = _get_model()

    expanded_query = _expand_query(query, normalized)
    q_vec = model.encode(_QUERY_PREFIX + expanded_query, normalize_embeddings=True)
    scores: np.ndarray = _emergency_vecs @ q_vec

    flags = []
    for anchor, score in zip(_EMERGENCY_ANCHORS, scores.tolist()):
        if score >= _EMERGENCY_THRESHOLD:
            flags.append(f"疑似急症（{anchor[:10]}…，相似度 {score:.2f}）")
    return flags


def _deduplicate_by_hierarchy(results: list[dict]) -> list[dict]:
    """
    若结果中同时包含父节点和其子节点，且子节点分数 >= 父节点分数 * 0.85，
    则丢弃父节点（子节点更精确）。
    """
    to_drop = set()
    for i, parent in enumerate(results):
        for j, child in enumerate(results):
            if i == j:
                continue
            if child["route"].startswith(parent["route"] + "/") and child["score"] >= parent["score"] * 0.85:
                to_drop.add(i)
    return [result for idx, result in enumerate(results) if idx not in to_drop]
