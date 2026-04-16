"""
hospital_matcher.py — 附近医院匹配与推荐

职责：
  优先路径（有 BAIDU_MAP_AUTH_TOKEN）：
    调用百度地图 Agent Plan Place API，实现全国任意城市医院搜索
  降级路径（无 Token）：
    从本地 hospitals.json（北京 4311 家）加载，按区划估算距离

输入 (match):
  user_location        str   用户当前地址，如 "广州市天河区体育西路"
  departments          list  目标科室列表，如 ["骨科", "神经内科"]
  preferences          dict  {
                               "max_distance_km": 10,
                               "hospital_level":  "三甲"|"二甲"|"不限",
                               "travel_mode":      "driving"|"transit"|"walking"
                             }
  top_n                int   返回候选数，默认 5

输出 dict:
  candidates    list[dict]  按优先级排序的医院列表
  data_sources  list[str]   使用的数据源
  filtered_by_blacklist int 因黑名单过滤的医院数
"""

import csv
import json
import logging
import os
import re
import requests
import urllib.parse
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# ── 路径常量 ──────────────────────────────────────────────────────────────
_ROOT          = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_SKILL_DIR     = os.path.dirname(os.path.abspath(__file__))
JSON_PATH      = os.path.join(_SKILL_DIR, "hospitals.json")
CSV_PATH       = os.path.join(_ROOT, "data", "医疗机构基本信息2023-03-29.csv")
BLACKLIST_PATH = os.path.join(_SKILL_DIR, "blacklist.json")
CACHE_PATH     = os.path.join(_ROOT, "skills", "registration_fetcher", "hospital_info.json")

YIXUE_BASE = "https://www.yixue.com/"

LEVEL_KEYWORDS = {
    "三甲": ["三级甲等", "三甲"],
    "二甲": ["二级甲等", "二甲"],
    "一级": ["一级"],
}

BAIDU_PLACE_URL    = "https://api.map.baidu.com/agent_plan/v1/place"
BAIDU_GEOCODE_URL  = "https://api.map.baidu.com/agent_plan/v1/geocoding"


# ══════════════════════════════════════════════════════════════════════════
# 公开接口
# ══════════════════════════════════════════════════════════════════════════

def match(user_location: str,
          departments: list,
          preferences: Optional[dict] = None,
          top_n: int = 5) -> dict:
    """
    根据用户位置和科室需求，返回附近医院候选列表。

    优先使用百度地图 Place API（全国覆盖），
    无 Token 或请求失败时降级到本地 JSON（仅北京）。
    """
    preferences = preferences or {}
    max_dist    = preferences.get("max_distance_km", 15)
    req_level   = preferences.get("hospital_level", "三甲")
    travel_mode = preferences.get("travel_mode", "transit")
    blacklist   = _load_blacklist()

    logger.info(f"[hospital_matcher] 用户位置: {user_location}, 科室: {departments}")

    # ── 路径 A：百度 Place API（全国，有 Token 时优先）────────────────────
    token = _get_baidu_token()
    if token:
        logger.info("[hospital_matcher] 使用百度 Place API 搜索医院（全国模式）")
        candidates, data_sources = _search_via_baidu_place(
            user_location=user_location,
            departments=departments,
            req_level=req_level,
            top_n=top_n,
            token=token,
        )
        if candidates:
            before_bl  = len(candidates)
            candidates = [h for h in candidates if h["hospital_name"] not in blacklist]
            return {
                "candidates":            candidates,
                "data_sources":          data_sources,
                "filtered_by_blacklist": before_bl - len(candidates),
                "total_before_filter":   before_bl,
                "timestamp":             datetime.now().isoformat(),
            }
        logger.warning("[hospital_matcher] Place API 返回空结果，降级到本地 JSON")

    # ── 路径 B：本地 JSON 降级（仅北京）──────────────────────────────────
    logger.info("[hospital_matcher] 使用本地 JSON 数据（仅北京）")
    all_hospitals = _load_hospitals()
    data_sources  = [f"本地JSON-北京医疗机构2023({len(all_hospitals)}条)"]

    dept_matched = _filter_by_department(all_hospitals, departments)
    if req_level != "不限":
        dept_matched = _filter_by_level(dept_matched, req_level)

    before_bl    = len(dept_matched)
    dept_matched = [h for h in dept_matched if h["hospital_name"] not in blacklist]
    filtered_by_blacklist = before_bl - len(dept_matched)

    hospitals_with_dist = _enrich_with_distance(dept_matched, user_location, travel_mode)
    data_sources.append(
        "百度地图MCP" if _distance_used_baidu(hospitals_with_dist)
        else "距离估算-按行政区分档(非精确)"
    )

    hospitals_with_dist = [h for h in hospitals_with_dist if h["distance_km"] <= max_dist]
    hospitals_with_dist.sort(key=_sort_key)

    cache      = _load_cache()
    candidates = []
    for h in hospitals_with_dist[:top_n]:
        name = h["hospital_name"]
        cached = cache.get(name, {})
        h["yixue_url"]     = cached.get("official_url") or YIXUE_BASE + name
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


# ══════════════════════════════════════════════════════════════════════════
# 百度地图 Agent Plan — 全国医院搜索
# ══════════════════════════════════════════════════════════════════════════

def _get_baidu_token() -> str:
    """从 .env / 环境变量读取百度地图 Token。"""
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(_ROOT, ".env"), override=False)
    except ImportError:
        pass
    return os.environ.get("BAIDU_MAP_AUTH_TOKEN", "")


def _search_via_baidu_place(user_location: str, departments: list,
                             req_level: str, top_n: int,
                             token: str) -> tuple:
    """
    调用百度地图 Agent Plan Place API 搜索附近医院。

    Returns (candidates: list, data_sources: list)
    """
    dept_str = departments[0] if departments else "综合"
    level_kw = "三甲" if req_level == "三甲" else ""
    query    = f"{level_kw}医院 {dept_str}科".strip()

    # 先地理编码获取坐标（用于 distance 排序）
    coords = _geocode(user_location, token)

    city = _extract_city(user_location)
    params: dict = {
        "user_raw_request": f"帮我找{user_location}附近的{query}，按距离排序",
        "region":           city or user_location,
        "sort":             "distance" if coords else "relevance",
    }
    if coords:
        params["center"] = f"{coords['lat']},{coords['lng']}"

    headers = {"Authorization": f"Bearer {token}"}
    try:
        resp = requests.get(BAIDU_PLACE_URL, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        logger.info(f"[hospital_matcher] Place API status={data.get('status')}, "
                    f"keys={list(data.keys())}")
    except Exception as e:
        logger.warning(f"[hospital_matcher] Place API 请求失败: {e}")
        return [], []

    candidates   = _parse_place_response(data, user_location, top_n)
    data_sources = [f"百度地图PlaceAPI-{city or user_location}（全国）"]
    return candidates, data_sources


def _geocode(address: str, token: str) -> Optional[dict]:
    """地理编码：地址字符串 → {lat, lng}。失败返回 None。"""
    try:
        resp = requests.get(
            BAIDU_GEOCODE_URL,
            params={"address": address},
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        loc  = (data.get("result") or {}).get("location") or {}
        if loc.get("lat") and loc.get("lng"):
            logger.info(f"[hospital_matcher] 地理编码: {address} → {loc['lat']},{loc['lng']}")
            return {"lat": loc["lat"], "lng": loc["lng"]}
    except Exception as e:
        logger.warning(f"[hospital_matcher] 地理编码失败: {e}")
    return None


def _parse_place_response(data: dict, user_location: str, top_n: int) -> list:
    """
    将 Place API 响应解析为统一 candidate 格式。
    兼容 data["results"] / data["result"]["places"] 等多种结构。
    """
    cache = _load_cache()

    # 兼容多种响应结构
    places = (
        data.get("results")
        or (data.get("result") or {}).get("places")
        or (data.get("result") or {}).get("results")
        or []
    )

    if not isinstance(places, list):
        logger.warning(f"[hospital_matcher] Place API 响应结构未识别: {list(data.keys())}")
        return []

    candidates = []
    for p in places[:top_n]:
        name    = p.get("name") or p.get("title", "")
        address = p.get("address") or p.get("addr", "")
        phone   = p.get("telephone") or p.get("tel", "")

        # 距离
        detail  = p.get("detail_info") or {}
        dist_m  = detail.get("distance") or p.get("distance") or 0
        dist_km = round(dist_m / 1000, 2) if dist_m else 5.0

        # 级别推断
        tags  = " ".join(p.get("tags", []) if isinstance(p.get("tags"), list) else [])
        level = ("三甲" if ("三甲" in name or "三甲" in tags) else
                 "二甲" if "二甲" in name else "其他")

        cached    = cache.get(name, {})
        yixue_url = cached.get("official_url") or YIXUE_BASE + name
        map_url   = _build_map_url(user_location, address or name)

        candidates.append({
            "hospital_name":         name,
            "address":               address,
            "phone":                 phone,
            "level":                 level,
            "level_rank":            1 if level == "三甲" else (2 if level == "二甲" else 99),
            "district":              "",
            "type":                  "",
            "departments":           [],
            "distance_km":           dist_km,
            "travel_time_min":       int(dist_km * 4),
            "distance_is_estimated": dist_m == 0,
            "yixue_url":             yixue_url,
            "map_route_url":         map_url,
            "_baidu_used":           True,
        })
        logger.info(f"[hospital_matcher] Place 结果: {name} | {dist_km} km")

    return candidates


def _extract_city(location: str) -> str:
    """
    从位置字符串提取城市名，用作 Place API 的 region 参数。
    '北京市朝阳区望京' → '北京市'，'广州天河区' → '广州市'
    """
    for city in ["北京", "上海", "天津", "重庆"]:
        if city in location:
            return city + "市"
    m = re.search(r'([\u4e00-\u9fa5]{2,5}市)', location)
    if m:
        return m.group(1)
    return ""


# ══════════════════════════════════════════════════════════════════════════
# 本地数据加载（降级路径）
# ══════════════════════════════════════════════════════════════════════════

def _load_hospitals() -> list:
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
                    "phone":           h.get("phone", ""),
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
            logger.warning(f"[hospital_matcher] JSON 读取失败: {e}")
    return _load_csv()


def _load_csv() -> list:
    hospitals = []
    if not os.path.exists(CSV_PATH):
        logger.warning(f"[hospital_matcher] CSV 不存在，使用内置样本数据")
        return _builtin_sample()
    try:
        with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
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
    level_col = row.get("医院等级") or row.get("等级") or row.get("机构类别") or ""
    for level, keywords in LEVEL_KEYWORDS.items():
        for kw in keywords:
            if kw in level_col:
                return level
    return "其他"


def _filter_by_department(hospitals: list, departments: list) -> list:
    if not departments:
        return hospitals
    result = []
    for h in hospitals:
        if h.get("level") == "三甲":
            result.append(h)
            continue
        name = h["hospital_name"]
        for dept in departments:
            if any(kw in name for kw in dept[:2]):
                result.append(h)
                break
        else:
            result.append(h)
    return result


def _filter_by_level(hospitals: list, req_level: str) -> list:
    filtered = [h for h in hospitals if h.get("level") == req_level]
    return filtered if filtered else hospitals


def _enrich_with_distance(hospitals: list, user_location: str, travel_mode: str) -> list:
    enriched = []
    for h in hospitals:
        dest = h.get("address") or h["hospital_name"] + "北京"
        dist, time_min, used_baidu = _query_baidu_map(user_location, dest, travel_mode)
        h = dict(h)
        h["distance_km"]           = dist
        h["travel_time_min"]       = time_min
        h["_baidu_used"]           = used_baidu
        h["distance_is_estimated"] = not used_baidu
        enriched.append(h)
    return enriched


def _query_baidu_map(origin: str, dest: str, mode: str) -> tuple:
    try:
        from baidu_map_mcp import route  # type: ignore
        result   = route(origin=origin, destination=dest, mode=mode)
        dist_km  = result.get("distance_km", 0)
        time_min = result.get("duration_min", 0)
        return dist_km, time_min, True
    except Exception:
        pass
    dist     = _estimate_distance_fallback(origin, dest)
    time_min = int(dist * 5)
    return dist, time_min, False


def _estimate_distance_fallback(origin: str, dest: str) -> float:
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
        "石景山区": {"西城区", "海淀区", "丰台区", "门头沟区"},
    }

    def _d(addr):
        for d in _DISTRICTS:
            if d in addr:
                return d
        return ""

    o, d = _d(origin), _d(dest)
    if o and d:
        if o == d:
            return 4.0
        if d in _ADJACENT.get(o, set()):
            return 9.0
        return 15.0
    return 10.0


def _distance_used_baidu(hospitals: list) -> bool:
    return any(h.get("_baidu_used") for h in hospitals)


def _sort_key(h: dict) -> tuple:
    level_score = 0 if h.get("level") == "三甲" else (1 if h.get("level") == "二甲" else 2)
    return (round(h["distance_km"]), level_score)


def _build_map_url(origin: str, dest: str) -> str:
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
    return [
        {"hospital_name": "北京协和医院",        "address": "北京市东城区帅府园1号",       "phone": "010-69156114", "level": "三甲", "departments": [], "distance_km": 0, "travel_time_min": 0},
        {"hospital_name": "北京大学第一医院",     "address": "北京市西城区西什库街8号",      "phone": "010-83572211", "level": "三甲", "departments": [], "distance_km": 0, "travel_time_min": 0},
        {"hospital_name": "北京天坛医院",         "address": "北京市丰台区南四环西路119号",   "phone": "010-67096611", "level": "三甲", "departments": [], "distance_km": 0, "travel_time_min": 0},
        {"hospital_name": "北京朝阳医院",         "address": "北京市朝阳区工人体育场南路8号", "phone": "010-85231000", "level": "三甲", "departments": [], "distance_km": 0, "travel_time_min": 0},
        {"hospital_name": "北京友谊医院",         "address": "北京市西城区永安路95号",       "phone": "010-63138585", "level": "三甲", "departments": [], "distance_km": 0, "travel_time_min": 0},
    ]


# ── 黑名单写入（供 itinerary_builder 调用）───────────────────────────────

def add_to_blacklist(hospital_name: str, reason: str = "") -> None:
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
            "reason": reason, "added_at": datetime.now().isoformat()
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
    # 测试广州（验证全国搜索）
    result = match(
        user_location="广州市天河区体育西路",
        departments=["骨科"],
        preferences={"max_distance_km": 10, "hospital_level": "三甲"},
        top_n=3,
    )
    print(_json.dumps(
        {k: v for k, v in result.items() if k != "candidates"},
        ensure_ascii=False, indent=2
    ))
    print(f"\n候选医院:")
    for c in result["candidates"]:
        print(f"  {c['hospital_name']} | {c['distance_km']}km | {c['level']}")
