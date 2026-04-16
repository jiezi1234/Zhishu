"""
registration_fetcher.py — 医院挂号平台查询

职责：
  对用户选定的医院，找到最合适的网络预约挂号入口，包括：
    1. 本地已知医院挂号 URL 库（直接命中，最准确）
    2. 城市/省级卫健委预约平台（按城市匹配）
    3. 从医院官网抓取预约入口链接
    4. 通用第三方平台兜底

输出字段：
  hospital_name        str   医院名称
  registration_url     str   挂号预约直达链接（写入 PDF 的核心字段）
  registration_platform str  平台名称，如 "京医通"、"健康广东"
  official_url         str   医院官方网站
  booking_note         str   挂号提示（放号时间、注意事项）
  from_cache           bool  True = 命中本地缓存
  timestamp            str   ISO 时间戳
"""

import json
import logging
import os
import re
import urllib.request
from datetime import datetime
from typing import Optional
from urllib.parse import quote

logger = logging.getLogger(__name__)

_SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_PATH = os.path.join(_SKILL_DIR, "hospital_info.json")
YIXUE_BASE = "https://www.yixue.com/"


# ══════════════════════════════════════════════════════════════════════════
# 数据库 1：知名医院直达挂号 URL
# ══════════════════════════════════════════════════════════════════════════

HOSPITAL_REGISTRATION_DB: dict[str, dict] = {
    # ── 北京 ──────────────────────────────────────────
    "北京协和医院": {
        "registration_url":      "https://www.bjguahao.gov.cn/hp/appoint/10.htm",
        "registration_platform": "京医通",
        "booking_note":          "周一 00:00 放下周号，微信搜索「京医通」小程序可挂",
    },
    "北京大学第一医院": {
        "registration_url":      "https://www.bjguahao.gov.cn/hp/appoint/14.htm",
        "registration_platform": "京医通",
        "booking_note":          "提前 7 天放号，需实名认证",
    },
    "北京大学人民医院": {
        "registration_url":      "https://www.bjguahao.gov.cn/hp/appoint/13.htm",
        "registration_platform": "京医通",
        "booking_note":          "提前 7 天放号",
    },
    "北京天坛医院": {
        "registration_url":      "https://www.bjguahao.gov.cn/hp/appoint/30.htm",
        "registration_platform": "京医通",
        "booking_note":          "神经科较热门，建议提前 7 天抢号",
    },
    "北京朝阳医院": {
        "registration_url":      "https://www.bjguahao.gov.cn/hp/appoint/28.htm",
        "registration_platform": "京医通",
        "booking_note":          "急诊全天候，普通号提前 7 天",
    },
    "北京友谊医院": {
        "registration_url":      "https://www.bjguahao.gov.cn/hp/appoint/15.htm",
        "registration_platform": "京医通",
        "booking_note":          "提前 7 天放号",
    },
    "北京积水潭医院": {
        "registration_url":      "https://www.bjguahao.gov.cn/hp/appoint/19.htm",
        "registration_platform": "京医通",
        "booking_note":          "骨科全国知名，提前 7 天放号",
    },
    "中日友好医院": {
        "registration_url":      "https://www.bjguahao.gov.cn/hp/appoint/36.htm",
        "registration_platform": "京医通",
        "booking_note":          "提前 7 天放号，支持微信挂号",
    },
    "北京大学第六医院": {
        "registration_url":      "https://www.bjguahao.gov.cn/hp/appoint/316.htm",
        "registration_platform": "京医通",
        "booking_note":          "精神科专科医院，号源紧张，建议早抢",
    },
    # ── 广东 ──────────────────────────────────────────
    "中山大学附属第一医院": {
        "registration_url":      "https://www.guahao.cn/hospital/4401020034/department",
        "registration_platform": "健康广东",
        "booking_note":          "广东省三甲，支持微信/支付宝预约",
    },
    "中山大学孙逸仙纪念医院": {
        "registration_url":      "https://www.guahao.cn/hospital/4401020035/department",
        "registration_platform": "健康广东",
        "booking_note":          "孙逸仙医院，提前 7 天放号",
    },
    "广州中医药大学第一附属医院": {
        "registration_url":      "https://www.guahao.cn/hospital/4401020026/department",
        "registration_platform": "健康广东",
        "booking_note":          "中医特色，骨科、内科知名",
    },
    "南方医科大学南方医院": {
        "registration_url":      "https://www.guahao.cn/hospital/4401010031/department",
        "registration_platform": "健康广东",
        "booking_note":          "提前 7 天放号",
    },
    "广东省人民医院": {
        "registration_url":      "https://www.guahao.cn/hospital/4401010003/department",
        "registration_platform": "健康广东",
        "booking_note":          "心内科、肿瘤科知名",
    },
    # ── 上海 ──────────────────────────────────────────
    "复旦大学附属中山医院": {
        "registration_url":      "https://www.jkzj.sh.gov.cn/",
        "registration_platform": "健康云（上海）",
        "booking_note":          "提前 7 天放号，推荐「健康云」App 预约",
    },
    "上海瑞金医院": {
        "registration_url":      "https://www.jkzj.sh.gov.cn/",
        "registration_platform": "健康云（上海）",
        "booking_note":          "提前 7 天放号",
    },
    "上海华山医院": {
        "registration_url":      "https://www.jkzj.sh.gov.cn/",
        "registration_platform": "健康云（上海）",
        "booking_note":          "神经内科、皮肤科知名",
    },
    # ── 浙江 ──────────────────────────────────────────
    "浙江大学医学院附属第一医院": {
        "registration_url":      "https://menzhen.zy1ds.com/",
        "registration_platform": "浙大一院官网预约",
        "booking_note":          "肝胆外科全国知名，微信公众号可预约",
    },
    "浙江大学医学院附属第二医院": {
        "registration_url":      "https://www.z2yy.com/",
        "registration_platform": "浙大二院官网预约",
        "booking_note":          "提前 7 天放号",
    },
}


# ══════════════════════════════════════════════════════════════════════════
# 数据库 2：城市/省份 → 区域预约平台
# ══════════════════════════════════════════════════════════════════════════

CITY_PLATFORM_DB: dict[str, dict] = {
    # 直辖市
    "北京":  {"platform": "京医通",          "url": "https://www.bjguahao.gov.cn/",     "note": "支持微信搜索「京医通」小程序预约"},
    "上海":  {"platform": "健康云（上海）",   "url": "https://www.jkzj.sh.gov.cn/",      "note": "下载「健康云」App 实名认证后预约"},
    "天津":  {"platform": "天津预约挂号平台", "url": "https://www.tjguahao.com/",        "note": "支持微信/App 预约"},
    "重庆":  {"platform": "重庆市预约挂号",   "url": "https://www.cqyywsfw.com/",        "note": "重庆市卫健委官方平台"},
    # 省份（用省级平台 URL）
    "广东":  {"platform": "健康广东",         "url": "https://www.guahao.cn/",           "note": "搜索医院名 + 点击预约即可"},
    "浙江":  {"platform": "浙里办·医疗",     "url": "https://www.zjzwfw.gov.cn/",       "note": "支付宝搜索「浙里办」→ 健康 → 预约挂号"},
    "江苏":  {"platform": "健康江苏",         "url": "https://www.jssq.net.cn/",         "note": "支持微信/支付宝"},
    "湖北":  {"platform": "湖北省预约挂号",   "url": "https://www.hbyy.net.cn/",         "note": "武汉市可使用「武汉预约挂号」"},
    "四川":  {"platform": "四川省预约挂号",   "url": "https://his.sc120.com/",           "note": "支持微信小程序"},
    "陕西":  {"platform": "陕西省预约挂号",   "url": "https://yy.sxwsjs.com/",          "note": "西安市医院较多"},
    "山东":  {"platform": "好大夫在线·山东", "url": "https://www.haodf.com/",           "note": "可搜索医生/医院直接预约"},
    "河南":  {"platform": "河南省预约挂号",   "url": "https://www.hn120.com/",           "note": "郑州市主要三甲均支持"},
    "湖南":  {"platform": "湖南省预约挂号",   "url": "https://www.hnyy120.net/",         "note": "长沙市主要医院均支持"},
    "福建":  {"platform": "福建预约挂号",     "url": "https://www.fjyy120.com/",         "note": "支持微信小程序"},
    "安徽":  {"platform": "安徽省预约挂号",   "url": "https://www.ahehealth.cn/",        "note": "支持合肥市主要三甲"},
    # 通用兜底
    "__default__": {"platform": "好大夫在线", "url": "https://www.haodf.com/",           "note": "可直接搜索医院或医生姓名预约"},
}

# 医院名称关键词 → 省份推断
_HOSPITAL_PROVINCE_HINTS = {
    "协和": "北京", "北大": "北京", "北京": "北京", "首医": "北京", "天坛": "北京",
    "复旦": "上海", "瑞金": "上海", "华山": "上海", "仁济": "上海", "上海": "上海",
    "中山大学": "广东", "南方医科": "广东", "广东": "广东", "广医": "广东",
    "浙大": "浙江", "浙江": "浙江",
    "西京": "陕西", "唐都": "陕西",
    "华西": "四川", "四川": "四川",
    "湘雅": "湖南", "中南大学": "湖南",
    "同济": "湖北", "协和武汉": "湖北",
    "中科大": "安徽", "安徽": "安徽",
    "齐鲁": "山东", "山东": "山东",
}


# ══════════════════════════════════════════════════════════════════════════
# 公开 API
# ══════════════════════════════════════════════════════════════════════════

def fetch(hospital_name: str,
          department: Optional[str] = None,
          user_location: Optional[str] = None,
          yixue_url: Optional[str] = None) -> dict:
    """
    查询医院挂号平台信息，按优先级：
      1. 本地已知医院 DB（精确命中）
      2. 本地缓存（之前已查询过的）
      3. 城市/省份平台匹配（按用户城市）
      4. 从 yixue.com 解析官网 → 在官网找预约入口
      5. 通用好大夫在线兜底

    Parameters
    ----------
    hospital_name   医院全称
    department      目标科室（未来扩展用）
    user_location   用户地址（用于推断省级平台）
    yixue_url       yixue.com 的医院页面 URL

    Returns
    -------
    dict 含 registration_url, registration_platform, official_url,
          booking_note, from_cache, timestamp
    """
    logger.info(f"[registration_fetcher] 查询: {hospital_name}")

    # ── 1. 已知医院 DB 直接命中 ────────────────────────────────────────
    for known_name, info in HOSPITAL_REGISTRATION_DB.items():
        if known_name in hospital_name or hospital_name in known_name:
            logger.info(f"[registration_fetcher] DB 命中: {known_name}")
            official_url = _get_official_url_from_cache(hospital_name)
            return _build_result(
                hospital_name     = hospital_name,
                registration_url  = info["registration_url"],
                platform          = info["registration_platform"],
                official_url      = official_url,
                booking_note      = info["booking_note"],
                from_cache        = True,
            )

    # ── 2. 本地缓存命中 ────────────────────────────────────────────────
    cached = _load_cache_entry(hospital_name)
    if cached and cached.get("registration_url"):
        logger.info(f"[registration_fetcher] 缓存命中: {hospital_name}")
        return _build_result(
            hospital_name     = hospital_name,
            registration_url  = cached["registration_url"],
            platform          = cached.get("registration_platform", ""),
            official_url      = cached.get("official_url", ""),
            booking_note      = cached.get("booking_note", ""),
            from_cache        = True,
        )

    # ── 3. 城市/省份平台匹配 ────────────────────────────────────────
    platform_info = _match_platform(hospital_name, user_location)
    registration_url  = platform_info["url"]
    registration_platform = platform_info["platform"]
    booking_note      = platform_info["note"]

    # ── 4. 从 yixue.com 或缓存获取官网 URL ──────────────────────────
    official_url = cached.get("official_url", "") if cached else ""
    if not official_url:
        yixue_page = yixue_url or (YIXUE_BASE + quote(hospital_name, safe=""))
        official_url = _parse_official_url(yixue_page, hospital_name)

    # ── 5. 如果官网存在，尝试从官网找预约入口 ───────────────────────
    if official_url and official_url != registration_url:
        guahao_url = _find_registration_on_official_site(official_url)
        if guahao_url:
            registration_url      = guahao_url
            registration_platform = "医院官网预约"
            booking_note          = f"在 {official_url} 找到预约入口，建议官网确认"
            logger.info(f"[registration_fetcher] 从官网找到预约入口: {guahao_url}")

    # ── 写缓存 ─────────────────────────────────────────────────────
    _write_cache(hospital_name, {
        "official_url":         official_url,
        "registration_url":     registration_url,
        "registration_platform": registration_platform,
        "booking_note":         booking_note,
    })

    return _build_result(
        hospital_name     = hospital_name,
        registration_url  = registration_url,
        platform          = registration_platform,
        official_url      = official_url,
        booking_note      = booking_note,
        from_cache        = False,
    )


def save_to_cache(hospital_name: str, registration_url: str,
                  official_url: str = "", platform: str = "") -> None:
    """将已验证的挂号 URL 写入缓存（供 Agent 在确认后调用）"""
    _write_cache(hospital_name, {
        "official_url":         official_url,
        "registration_url":     registration_url,
        "registration_platform": platform,
    })
    logger.info(f"[registration_fetcher] 缓存写入: {hospital_name} → {registration_url}")


def run(hospital_name: str, **kwargs) -> dict:
    """AutoClaw / GLM 统一入口"""
    return fetch(
        hospital_name  = hospital_name,
        department     = kwargs.get("department"),
        user_location  = kwargs.get("user_location"),
        yixue_url      = kwargs.get("yixue_url"),
    )


# ══════════════════════════════════════════════════════════════════════════
# 内部实现
# ══════════════════════════════════════════════════════════════════════════

def _match_platform(hospital_name: str, user_location: Optional[str]) -> dict:
    """根据医院名关键词或用户地址推断最合适的省级/城市挂号平台。"""
    # 从医院名推断省份
    for kw, province in _HOSPITAL_PROVINCE_HINTS.items():
        if kw in hospital_name:
            info = CITY_PLATFORM_DB.get(province) or CITY_PLATFORM_DB["__default__"]
            logger.info(f"[registration_fetcher] 从医院名推断省份: {province}")
            return info

    # 从用户地址推断城市/省份
    if user_location:
        for city_key in CITY_PLATFORM_DB:
            if city_key != "__default__" and city_key in user_location:
                logger.info(f"[registration_fetcher] 从地址推断平台: {city_key}")
                return CITY_PLATFORM_DB[city_key]

    logger.info("[registration_fetcher] 使用默认兜底平台")
    return CITY_PLATFORM_DB["__default__"]


def _parse_official_url(yixue_url: str, hospital_name: str) -> str:
    """访问 yixue.com 医院页面，提取「医院网站」字段的外链 URL。"""
    try:
        req = urllib.request.Request(
            yixue_url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; HealthPathAgent/2.0)"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="replace")

        # 主模式：<b>医院网站</b> 后紧跟 href
        m = re.search(
            r'<b>医院网站</b>.*?href=["\']([^"\']+)["\']',
            html, re.DOTALL | re.IGNORECASE,
        )
        if m:
            url = m.group(1).strip()
            if not url.startswith("http://www.yixue.com") and \
               not url.startswith("https://www.yixue.com"):
                logger.info(f"[registration_fetcher] yixue 解析官网: {url}")
                return url
    except Exception as e:
        logger.warning(f"[registration_fetcher] yixue 访问失败: {e}")
    return ""


def _find_registration_on_official_site(official_url: str) -> str:
    """
    访问医院官网，在首页 HTML 里寻找预约/挂号入口链接。
    命中率约 40-60%（取决于医院网站结构）。
    """
    _GUAHAO_PATTERNS = [
        r'href=["\']([^"\']*(?:guahao|yuyue|appointment|reserve|booking|预约|挂号)[^"\']*)["\']',
    ]
    try:
        req = urllib.request.Request(
            official_url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; HealthPathAgent/2.0)"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="replace")[:80000]  # 只读前 80KB

        for pattern in _GUAHAO_PATTERNS:
            matches = re.findall(pattern, html, re.IGNORECASE)
            for url in matches:
                # 过滤掉无意义锚点
                if url.startswith("#") or len(url) < 5:
                    continue
                # 补全相对路径
                if url.startswith("/"):
                    from urllib.parse import urlparse
                    parsed = urlparse(official_url)
                    url = f"{parsed.scheme}://{parsed.netloc}{url}"
                elif not url.startswith("http"):
                    url = official_url.rstrip("/") + "/" + url
                logger.info(f"[registration_fetcher] 官网预约入口: {url}")
                return url
    except Exception as e:
        logger.warning(f"[registration_fetcher] 官网访问失败 {official_url}: {e}")
    return ""


def _build_result(hospital_name, registration_url, platform,
                  official_url, booking_note, from_cache) -> dict:
    return {
        "hospital_name":         hospital_name,
        "registration_url":      registration_url,
        "registration_platform": platform,
        "official_url":          official_url,
        "booking_note":          booking_note,
        "from_cache":            from_cache,
        "timestamp":             datetime.now().isoformat(),
    }


def _get_official_url_from_cache(hospital_name: str) -> str:
    entry = _load_cache_entry(hospital_name)
    return (entry or {}).get("official_url", "")


def _load_cache_entry(hospital_name: str) -> Optional[dict]:
    if not os.path.exists(CACHE_PATH):
        return None
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            cache = json.load(f)
        return cache.get(hospital_name)
    except Exception:
        return None


def _write_cache(hospital_name: str, data: dict) -> None:
    os.makedirs(_SKILL_DIR, exist_ok=True)
    cache: dict = {}
    if os.path.exists(CACHE_PATH):
        try:
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                cache = json.load(f)
        except Exception:
            pass
    cache[hospital_name] = {**cache.get(hospital_name, {}), **data,
                            "updated_at": datetime.now().isoformat()}
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


# ── CLI 快速测试 ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    test_cases = [
        ("北京协和医院", None, "北京市东城区"),
        ("广州中医药大学第一附属医院", "骨科", "广州市天河区"),
        ("成都市第三人民医院", "内科", "四川省成都市"),
        ("暨南大学附属第一医院", "骨科", "广州市天河区"),
    ]
    for name, dept, loc in test_cases:
        print(f"\n{'='*60}")
        print(f"医院: {name}")
        r = fetch(hospital_name=name, department=dept, user_location=loc)
        print(f"挂号平台: {r['registration_platform']}")
        print(f"挂号链接: {r['registration_url']}")
        print(f"官网:     {r['official_url']}")
        print(f"提示:     {r['booking_note']}")
        print(f"来自缓存: {r['from_cache']}")
