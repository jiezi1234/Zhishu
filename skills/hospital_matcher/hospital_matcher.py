"""
hospital_matcher.py — 附近医院匹配与推荐

职责：
  1. 从预处理 JSON（skills/hospital_matcher/hospitals.json）加载北京医院列表
     （hospitals.json 由项目根目录的 csv_to_json.py 生成，降级路径读原始 CSV）
  2. 调用百度地图 MCP 计算用户到各医院的距离
  3. 按科室过滤 + 距离/用户偏好排序，返回 Top-N 候选
  4. 过滤本地黑名单（skills/hospital_matcher/blacklist.json）
  5. 从 yixue.com 补充医院官方信息（URL、电话等）

输入 (task_params):
  user_location        str   用户当前地址，如 "北京市朝阳区望京街道"
  departments          list  目标科室列表，如 ["神经内科", "耳鼻喉科"]
  preferences          dict  {
                               "max_distance_km": 10,
                               "hospital_level":  "三甲"|"二甲"|"不限",
                               "time_window":      "weekend"|"this_week"|...,
                               "travel_mode":      "driving"|"transit"|"walking"
                             }
  top_n                int   返回候选数，默认 5

输出 dict:
  candidates    list[dict]  按优先级排序的医院列表，每项含：
    hospital_name   str
    level           str      医院级别
    distance_km     float
    travel_time_min int      预计出行时间（分钟）
    address         str
    phone           str
    departments     list[str]
    yixue_url       str
    map_route_url   str      百度地图直达链接
  data_sources  list[str]   使用的数据源名称
  filtered_by_blacklist int 因黑名单过滤的医院数
"""

import csv
import json
import logging
import os
import re
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# ── 路径常量 ──────────────────────────────────────────────────────────────
_ROOT          = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_SKILL_DIR     = os.path.dirname(os.path.abspath(__file__))
JSON_PATH      = os.path.join(_SKILL_DIR, "hospitals.json")   # 预处理数据，csv_to_json.py 生成
CSV_PATH       = os.path.join(_ROOT, "data", "医疗机构基本信息2023-03-29.csv")  # 降级原始 CSV
BLACKLIST_PATH = os.path.join(_SKILL_DIR, "blacklist.json")   # 用户黑名单（本 skill 私有）
# hospital_info.json 由 registration_fetcher 写入，此处只读
CACHE_PATH     = os.path.join(_ROOT, "skills", "registration_fetcher", "hospital_info.json")

# ── 医院级别关键词 ────────────────────────────────────────────────────────
LEVEL_KEYWORDS = {
    "三甲": ["三级甲等", "三甲"],
    "二甲": ["二级甲等", "二甲"],
    "一级": ["一级"],
}

YIXUE_BASE = "https://www.yixue.com/"


def match(user_location: str,
          departments: list,
          preferences: Optional[dict] = None,
          top_n: int = 5) -> dict:
    """
    根据用户位置和科室需求，返回附近医院候选列表。

    Parameters
    ----------
    user_location : 用户当前地址字符串
    departments   : 期望就诊的科室列表
    preferences   : 过滤与排序偏好
    top_n         : 返回候选医院数量

    Returns
    -------
    dict — 见模块级文档
    """
    preferences = preferences or {}
    max_dist     = preferences.get("max_distance_km", 15)
    req_level    = preferences.get("hospital_level", "不限")
    travel_mode  = preferences.get("travel_mode", "transit")

    logger.info(f"[hospital_matcher] 用户位置: {user_location}, 科室: {departments}")

    # 1. 加载本地医院数据（优先 JSON，降级 CSV）────────────────────────────
    all_hospitals = _load_hospitals()
    data_sources = [f"本地JSON-北京医疗机构2023({len(all_hospitals)}条)"]

    # 2. 过滤科室 ──────────────────────────────────────────────────────
    dept_matched = _filter_by_department(all_hospitals, departments)

    # 3. 过滤医院级别 ──────────────────────────────────────────────────
    if req_level != "不限":
        dept_matched = _filter_by_level(dept_matched, req_level)

    # 4. 过滤黑名单 ────────────────────────────────────────────────────
    blacklist = _load_blacklist()
    before_bl = len(dept_matched)
    dept_matched = [h for h in dept_matched if h["hospital_name"] not in blacklist]
    filtered_by_blacklist = before_bl - len(dept_matched)

    # 5. 计算距离（调用百度地图 MCP 或降级估算）─────────────────────────
    hospitals_with_dist = _enrich_with_distance(
        dept_matched, user_location, travel_mode
    )
    if _distance_used_baidu(hospitals_with_dist):
        data_sources.append("百度地图MCP")
    else:
        data_sources.append("距离估算-按行政区分档(非精确)")

    # 6. 过滤最大距离 ──────────────────────────────────────────────────
    hospitals_with_dist = [
        h for h in hospitals_with_dist if h["distance_km"] <= max_dist
    ]

    # 7. 排序：距离优先，再按医院级别加权 ─────────────────────────────
    hospitals_with_dist.sort(key=_sort_key)

    # 8. 取 Top-N，补充 yixue.com 信息 ────────────────────────────────
    candidates = []
    cache = _load_cache()

    for h in hospitals_with_dist[:top_n]:
        name = h["hospital_name"]
        yixue_url = YIXUE_BASE + name

        # 优先读缓存
        cached = cache.get(name, {})
        h["yixue_url"]    = cached.get("yixue_url", yixue_url)
        h["map_route_url"] = _build_map_url(user_location, h.get("address", name))
        candidates.append(h)

    logger.info(f"[hospital_matcher] 候选医院数: {len(candidates)}")

    return {
        "candidates":            candidates,
        "data_sources":          data_sources,
        "filtered_by_blacklist": filtered_by_blacklist,
        "total_before_filter":   len(all_hospitals),
        "timestamp":             datetime.now().isoformat(),
    }


# ── 内部工具函数 ──────────────────────────────────────────────────────────

def _load_hospitals() -> list:
    """
    加载医院数据。
    优先读取预处理好的 hospitals.json（由 csv_to_json.py 生成），
    JSON 缺失时降级读原始 CSV，最后兜底返回内置样本。
    """
    # ── 优先：JSON ────────────────────────────────────────────────────────
    if os.path.exists(JSON_PATH):
        try:
            with open(JSON_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            raw = data.get("all", [])
            hospitals = []
            for h in raw:
                hospitals.append({
                    "hospital_name":   h.get("name", ""),
                    "address":         h.get("address", ""),
                    "phone":           h.get("phone", ""),       # JSON 暂无电话，保留空
                    "level":           h.get("level", "其他"),
                    "level_rank":      h.get("level_rank", 99),
                    "district":        h.get("district", ""),
                    "type":            h.get("type", ""),
                    "departments":     [],
                    "distance_km":     0.0,
                    "travel_time_min": 0,
                    "yixue_url":       h.get("yixue_url", ""),
                })
            logger.info(f"[hospital_matcher] JSON 加载 {len(hospitals)} 条医院")
            return hospitals
        except Exception as e:
            logger.warning(f"[hospital_matcher] JSON 读取失败: {e}，降级读 CSV")

    # ── 降级：CSV ─────────────────────────────────────────────────────────
    return _load_csv()


def _load_csv() -> list:
    """从原始 CSV 加载（JSON 不存在时的降级路径）"""
    hospitals = []
    if not os.path.exists(CSV_PATH):
        logger.warning(f"[hospital_matcher] CSV 不存在: {CSV_PATH}，使用内置样本数据")
        return _builtin_sample()

    try:
        with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # 实际列名：医疗机构名称 / 联系地址 / 医院等级 / 医保区划 / 机构类别
                name = (row.get("医疗机构名称") or "").strip()
                if not name:
                    continue
                hospitals.append({
                    "hospital_name":   name,
                    "address":         (row.get("联系地址") or "").strip(),
                    "phone":           "",
                    "level":           _parse_level(row),
                    "level_rank":      99,
                    "district":        (row.get("医保区划") or "").strip(),
                    "type":            (row.get("机构类别") or "").strip(),
                    "departments":     [],
                    "distance_km":     0.0,
                    "travel_time_min": 0,
                    "yixue_url":       f"https://www.yixue.com/{name}",
                })
        logger.info(f"[hospital_matcher] CSV 加载 {len(hospitals)} 条医院")
    except Exception as e:
        logger.error(f"[hospital_matcher] CSV 读取失败: {e}")
        return _builtin_sample()

    return hospitals


def _parse_level(row: dict) -> str:
    """从 CSV 行中提取医院级别（降级路径专用）"""
    level_col = row.get("医院等级") or row.get("等级") or row.get("机构类别") or ""
    for level, keywords in LEVEL_KEYWORDS.items():
        for kw in keywords:
            if kw in level_col:
                return level
    return "其他"


def _filter_by_department(hospitals: list, departments: list) -> list:
    """
    过滤含目标科室的医院。
    CSV 中通常没有科室字段，此处用医院名称启发式判断（三甲综合医院视为全科）。
    精确科室数据由 registration_fetcher 在用户选定医院后补充。
    """
    if not departments:
        return hospitals

    result = []
    for h in hospitals:
        # 三甲综合医院默认认为含有大多数科室
        if h.get("level") == "三甲":
            result.append(h)
            continue
        # 若医院名称含科室关键词，保留
        name = h["hospital_name"]
        for dept in departments:
            if any(kw in name for kw in dept[:2]):   # 如"神经" "骨科" "呼吸"
                result.append(h)
                break
        else:
            # 无法判断时保守保留（避免漏掉）
            result.append(h)

    return result


def _filter_by_level(hospitals: list, req_level: str) -> list:
    """按医院级别过滤"""
    # 三甲 > 二甲 > 其他（三甲时仅保三甲，但若结果为0则放宽）
    filtered = [h for h in hospitals if h.get("level") == req_level]
    return filtered if filtered else hospitals


def _enrich_with_distance(hospitals: list, user_location: str, travel_mode: str) -> list:
    """
    调用百度地图 MCP 计算距离与出行时间。
    若 MCP 不可用，降级为基于地名的估算（不准确，但保证流程可走通）。
    """
    enriched = []
    baidu_ok = False

    for h in hospitals:
        dest = h.get("address") or h["hospital_name"] + "北京"
        dist, time_min, used_baidu = _query_baidu_map(user_location, dest, travel_mode)
        if used_baidu:
            baidu_ok = True
        h = dict(h)
        h["distance_km"]        = dist
        h["travel_time_min"]    = time_min
        h["_baidu_used"]        = used_baidu
        h["distance_is_estimated"] = not used_baidu   # True 时距离为区划粗估，非精确值
        enriched.append(h)

    return enriched


def _query_baidu_map(origin: str, dest: str, mode: str) -> tuple:
    """
    尝试调用百度地图 MCP baidu-ai-map skill。
    返回 (distance_km, travel_time_min, used_baidu_bool)
    """
    try:
        # AutoClaw 运行时，baidu-ai-map skill 通过工具调用暴露；
        # 此处尝试 import，若不在 AutoClaw 环境则捕获异常降级。
        from baidu_map_mcp import route  # type: ignore
        result = route(origin=origin, destination=dest, mode=mode)
        dist_km  = result.get("distance_km", 0)
        time_min = result.get("duration_min", 0)
        return dist_km, time_min, True
    except Exception:
        pass

    # 降级：基于行政区的分档估算（无地图 API 时）
    dist = _estimate_distance_fallback(origin, dest)
    time_min = int(dist * 5)   # 公交约 5 min/km（含候车）
    return dist, time_min, False


def _estimate_distance_fallback(origin: str, dest: str) -> float:
    """
    无地图 API 时按行政区关系估算距离（保守粗估，非精确值）。
    同区：4 km  |  相邻区：9 km  |  跨区：15 km
    """
    # 从地址中提取区名
    _DISTRICTS = [
        "东城区", "西城区", "朝阳区", "海淀区", "丰台区", "石景山区",
        "通州区", "顺义区", "昌平区", "大兴区", "房山区", "门头沟区",
        "平谷区", "怀柔区", "密云区", "延庆区",
    ]
    _ADJACENT = {
        "东城区":  {"西城区", "朝阳区", "丰台区"},
        "西城区":  {"东城区", "海淀区", "丰台区", "石景山区"},
        "朝阳区":  {"东城区", "海淀区", "丰台区", "通州区", "顺义区"},
        "海淀区":  {"西城区", "朝阳区", "丰台区", "石景山区", "昌平区"},
        "丰台区":  {"东城区", "西城区", "朝阳区", "海淀区", "石景山区", "大兴区"},
        "石景山区":{"西城区", "海淀区", "丰台区", "门头沟区"},
    }

    def _extract_district(addr: str) -> str:
        for d in _DISTRICTS:
            if d in addr:
                return d
        return ""

    o_dist = _extract_district(origin)
    d_dist = _extract_district(dest)

    if o_dist and d_dist:
        if o_dist == d_dist:
            return 4.0
        if d_dist in _ADJACENT.get(o_dist, set()):
            return 9.0
        return 15.0

    # 区划无法识别时保守返回 10 km
    return 10.0


def _distance_used_baidu(hospitals: list) -> bool:
    return any(h.get("_baidu_used") for h in hospitals)


def _sort_key(h: dict) -> tuple:
    """排序键：距离升序，三甲医院优先"""
    level_score = 0 if h.get("level") == "三甲" else (1 if h.get("level") == "二甲" else 2)
    return (round(h["distance_km"]), level_score)


def _build_map_url(origin: str, dest: str) -> str:
    """生成百度地图路线规划分享链接（公交模式）"""
    import urllib.parse
    o = urllib.parse.quote(origin)
    d = urllib.parse.quote(dest)
    return f"https://map.baidu.com/dir/?origin={o}&destination={d}&mode=transit"


def _load_blacklist() -> set:
    if not os.path.exists(BLACKLIST_PATH):
        return set()
    try:
        with open(BLACKLIST_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return set(data.get("hospitals", []))
    except Exception:
        return set()


def _load_cache() -> dict:
    if not os.path.exists(CACHE_PATH):
        return {}
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _builtin_sample() -> list:
    """内置样本数据（CSV 缺失时的兜底）"""
    return [
        {"hospital_name": "北京协和医院",       "address": "北京市东城区帅府园1号",   "phone": "010-69156114", "level": "三甲", "departments": [], "distance_km": 0, "travel_time_min": 0},
        {"hospital_name": "北京大学第一医院",    "address": "北京市西城区西什库街8号",  "phone": "010-83572211", "level": "三甲", "departments": [], "distance_km": 0, "travel_time_min": 0},
        {"hospital_name": "首都医科大学附属北京天坛医院", "address": "北京市丰台区南四环西路119号", "phone": "010-67096611", "level": "三甲", "departments": [], "distance_km": 0, "travel_time_min": 0},
        {"hospital_name": "北京朝阳医院",        "address": "北京市朝阳区工人体育场南路8号", "phone": "010-85231000", "level": "三甲", "departments": [], "distance_km": 0, "travel_time_min": 0},
        {"hospital_name": "北京友谊医院",        "address": "北京市西城区永安路95号",   "phone": "010-63138585", "level": "三甲", "departments": [], "distance_km": 0, "travel_time_min": 0},
    ]


# ── 黑名单写入工具（供 itinerary_builder 调用）───────────────────────────

def add_to_blacklist(hospital_name: str, reason: str = "") -> None:
    """将医院加入用户黑名单，持久化到 skills/hospital_matcher/blacklist.json"""
    os.makedirs(os.path.dirname(BLACKLIST_PATH), exist_ok=True)
    data = {"hospitals": []}
    if os.path.exists(BLACKLIST_PATH):
        try:
            with open(BLACKLIST_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass

    if hospital_name not in data["hospitals"]:
        data["hospitals"].append(hospital_name)
        data.setdefault("reasons", {})[hospital_name] = {
            "reason": reason,
            "added_at": datetime.now().isoformat(),
        }
        with open(BLACKLIST_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"[hospital_matcher] 已将 {hospital_name} 加入黑名单")


# ── 便捷入口 ──────────────────────────────────────────────────────────────

def run(user_location: str, departments: list, **kwargs) -> dict:
    """AutoClaw / GLM 调用的统一入口"""
    return match(
        user_location=user_location,
        departments=departments,
        preferences=kwargs.get("preferences"),
        top_n=kwargs.get("top_n", 5),
    )


if __name__ == "__main__":
    import json as _json
    result = match(
        user_location="北京市朝阳区望京街道",
        departments=["神经内科"],
        preferences={"max_distance_km": 10, "hospital_level": "三甲"},
        top_n=3,
    )
    print(_json.dumps(result, ensure_ascii=False, indent=2))
