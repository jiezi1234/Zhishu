"""
registration_fetcher.py — 医院官网/挂号链接采集

职责：
  1. 查询本地缓存（skills/healthpath-registration-fetcher/hospital_info.json）
  2. 缓存未命中时，访问 yixue.com 解析医院官网 URL
  3. yixue.com 失败时，使用 WebSearch 从网上搜索医院官网
  4. 返回统一挂号信息结构
"""

import json
import logging
import os
import re
from datetime import datetime
from typing import Optional
from urllib.parse import quote

logger = logging.getLogger(__name__)

_SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_PATH = os.path.join(_SKILL_DIR, "hospital_info.json")
YIXUE_BASE = "https://www.yixue.com/"


def fetch(hospital_name: str, **kwargs) -> dict:
    """获取医院官网/挂号信息，兼容主流程调用参数。"""
    department = kwargs.get("department", "")

    cached = _load_cache(hospital_name)
    if cached:
        official_url = (cached.get("official_url") or "").strip()
        registration_url = (cached.get("registration_url") or official_url).strip()
        return {
            "hospital_name": hospital_name,
            "department": department,
            "official_url": official_url,
            "registration_url": registration_url,
            "registration_platform": cached.get("registration_platform", "医院官网"),
            "booking_note": cached.get("booking_note", "请以医院官网最新放号信息为准。"),
            "from_cache": True,
            "timestamp": datetime.now().isoformat(),
        }

    yixue_url = kwargs.get("yixue_url") or (YIXUE_BASE + quote(hospital_name, safe=""))
    official_url = _parse_official_url(yixue_url, hospital_name)

    # 如果 yixue.com 获取失败，使用 WebSearch 搜索
    if not official_url:
        logger.info(f"[registration_fetcher] yixue.com 未找到 {hospital_name} 官网，尝试域名匹配和网络搜索")
        official_url = _search_official_url_via_web(hospital_name)

    registration_url = official_url

    # 明确的提示信息
    if registration_url:
        booking_note = "请以医院官网最新放号信息为准。"
        platform = "医院官网"
    else:
        booking_note = f"暂时未查询到 {hospital_name} 的挂号链接，建议：\n1. 拨打医院电话咨询\n2. 使用京医通/健康广东等当地挂号平台\n3. 前往医院现场挂号"
        platform = ""
        logger.warning(f"[registration_fetcher] 最终未获取到 {hospital_name} 的官网链接")

    return {
        "hospital_name": hospital_name,
        "department": department,
        "official_url": official_url,
        "registration_url": registration_url,
        "registration_platform": platform,
        "booking_note": booking_note,
        "from_cache": False,
        "timestamp": datetime.now().isoformat(),
    }


def save_to_cache(hospital_name: str, official_url: str, **kwargs) -> None:
    payload = {
        "official_url": official_url,
        "registration_url": kwargs.get("registration_url", official_url),
        "registration_platform": kwargs.get("registration_platform", "医院官网"),
        "booking_note": kwargs.get("booking_note", "请以医院官网最新放号信息为准。"),
        "updated_at": datetime.now().isoformat(),
    }
    _write_cache(hospital_name, payload)


def _parse_official_url(yixue_url: str, hospital_name: str) -> str:
    try:
        import urllib.request

        req = urllib.request.Request(
            yixue_url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; HealthPathAgent/1.0)"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="replace")

        m = re.search(r'<b>医院网站</b>.*?href=["\']([^"\']+)["\']', html, re.DOTALL | re.IGNORECASE)
        if m:
            url = m.group(1).strip()
            if not _is_yixue_inner_url(url):
                return url

        m = re.search(r'官方网站.*?href=["\']([^"\']+)["\']', html, re.DOTALL | re.IGNORECASE)
        if m:
            url = m.group(1).strip()
            if not _is_yixue_inner_url(url):
                return url

        logger.warning("[registration_fetcher] 页面未找到医院官网字段: %s", hospital_name)
    except Exception as e:
        logger.warning("[registration_fetcher] 访问 yixue 失败: %s", e)
    return ""


def _is_yixue_inner_url(url: str) -> bool:
    return url.startswith("http://www.yixue.com") or url.startswith("https://www.yixue.com")


def _search_official_url_via_web(hospital_name: str) -> str:
    """
    使用网络搜索查找医院官网链接。

    策略：
      1. 尝试常见的医院官网域名模式
      2. 使用百度搜索 API（如果可用）
      3. 返回第一个有效链接或空字符串
    """
    try:
        import urllib.request
        import urllib.parse

        logger.info(f"[registration_fetcher] 尝试搜索医院官网: {hospital_name}")

        # 策略 1: 尝试常见的域名模式
        # 例如：北京协和医院 -> pumch.cn, 北京大学第一医院 -> pkufh.com
        common_patterns = _guess_hospital_domain(hospital_name)
        for url in common_patterns:
            if _validate_url(url):
                logger.info(f"[registration_fetcher] 通过域名模式找到官网: {url}")
                return url

        # 策略 2: 使用百度搜索（更稳定，国内访问快）
        query = f"{hospital_name} 官网"
        search_url = f"https://www.baidu.com/s?wd={urllib.parse.quote(query)}"

        req = urllib.request.Request(
            search_url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            },
        )

        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        # 提取百度搜索结果中的链接
        # 百度结果格式: <a ... href="http://www.baidu.com/link?url=..." ...>
        # 实际链接在 data-url 或直接在 href 中
        pattern = r'<a[^>]+href="(https?://[^"]+)"[^>]*class="[^"]*c-showurl[^"]*"'
        matches = re.findall(pattern, html)

        # 也尝试提取 data-url
        pattern2 = r'data-url="(https?://[^"]+)"'
        matches.extend(re.findall(pattern2, html))

        # 过滤候选链接
        candidates = []
        for url in matches:
            # 跳过百度自身的链接
            if "baidu.com" in url.lower():
                continue
            # 跳过明显不是官网的链接
            if any(x in url.lower() for x in ["wikipedia", "baike", "zhihu", "weibo", "douban"]):
                continue
            # 跳过挂号平台（我们要的是医院官网）
            if any(x in url.lower() for x in ["guahao", "haodf", "114yygh"]):
                continue

            candidates.append(url)
            if len(candidates) >= 3:  # 只检查前3个候选
                break

        # 验证候选链接
        for url in candidates:
            if _validate_url(url):
                logger.info(f"[registration_fetcher] 通过搜索找到官网: {url}")
                return url

        logger.warning(f"[registration_fetcher] 未找到有效官网: {hospital_name}")
        return ""

    except Exception as e:
        logger.warning(f"[registration_fetcher] 搜索失败: {e}")
        return ""


def _guess_hospital_domain(hospital_name: str) -> list:
    """
    根据医院名称猜测可能的官网域名。

    常见模式：
      - 北京协和医院 -> pumch.cn (Peking Union Medical College Hospital)
      - 北京大学第一医院 -> pkufh.com (PKU First Hospital)
      - 中山大学附属第一医院 -> gzsums.edu.cn
    """
    candidates = []

    # 知名医院的域名映射（手动维护常见医院）
    known_domains = {
        # 北京
        "北京协和医院": ["https://www.pumch.cn/", "http://www.pumch.cn/"],
        "北京大学第一医院": ["https://www.bddyyy.com.cn/", "http://www.bddyyy.com.cn/"],
        "北京大学第三医院": ["https://www.puh3.net.cn/", "http://www.puh3.net.cn/"],
        "中日友好医院": ["https://www.zryhyy.com.cn/", "http://www.zryhyy.com.cn/"],
        "北京天坛医院": ["https://www.bjtth.org/", "http://www.bjtth.org/"],
        "北京朝阳医院": ["https://www.bjcyh.com.cn/", "http://www.bjcyh.com.cn/"],
        "北京友谊医院": ["https://www.bfh.com.cn/", "http://www.bfh.com.cn/"],

        # 上海
        "上海交通大学医学院附属瑞金医院": ["https://www.rjh.com.cn/", "http://www.rjh.com.cn/"],
        "复旦大学附属华山医院": ["https://www.huashan.org.cn/", "http://www.huashan.org.cn/"],
        "上海市第一人民医院": ["https://www.firsthospital.cn/", "http://www.firsthospital.cn/"],
        "上海交通大学医学院附属仁济医院": ["https://www.renji.com/", "http://www.renji.com/"],
        "复旦大学附属中山医院": ["https://www.zs-hospital.sh.cn/", "http://www.zs-hospital.sh.cn/"],

        # 广州
        "中山大学附属第一医院": ["https://www.gzsums.edu.cn/", "http://www.gzsums.edu.cn/"],
        "中山大学附属第三医院": ["https://www.zssy.com.cn/", "http://www.zssy.com.cn/"],
        "广州市第一人民医院": ["https://www.gzsy.org/", "http://www.gzsy.org/"],
        "南方医科大学南方医院": ["https://www.nfyy.com/", "http://www.nfyy.com/"],
        "广东省人民医院": ["https://www.gdghospital.org.cn/", "http://www.gdghospital.org.cn/"],

        # 成都
        "四川大学华西医院": ["https://www.wchscu.cn/", "http://www.wchscu.cn/"],
        "四川省人民医院": ["https://www.samsph.com/", "http://www.samsph.com/"],

        # 杭州
        "浙江大学医学院附属第一医院": ["https://www.zy91.com/", "http://www.zy91.com/"],
        "浙江大学医学院附属第二医院": ["https://www.z2hospital.com/", "http://www.z2hospital.com/"],

        # 西安
        "西安交通大学第一附属医院": ["https://www.dyyy.xjtu.edu.cn/", "http://www.dyyy.xjtu.edu.cn/"],
        "西安交通大学第二附属医院": ["https://www.2yuan.xjtu.edu.cn/", "http://www.2yuan.xjtu.edu.cn/"],

        # 武汉
        "华中科技大学同济医学院附属协和医院": ["https://www.whuh.com/", "http://www.whuh.com/"],
        "华中科技大学同济医学院附属同济医院": ["https://www.tjh.com.cn/", "http://www.tjh.com.cn/"],

        # 南京
        "南京鼓楼医院": ["https://www.njglyy.com/", "http://www.njglyy.com/"],
        "江苏省人民医院": ["https://www.jsph.net/", "http://www.jsph.net/"],
    }

    if hospital_name in known_domains:
        candidates.extend(known_domains[hospital_name])

    return candidates


def _validate_url(url: str) -> bool:
    """验证 URL 是否可访问（HTTP 200）"""
    try:
        import urllib.request

        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; HealthPathAgent/1.0)"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except Exception:
        return False


def _load_cache(hospital_name: str) -> Optional[dict]:
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
    cache = {}
    if os.path.exists(CACHE_PATH):
        try:
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                cache = json.load(f)
        except Exception:
            pass
    cache[hospital_name] = data
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def run(hospital_name: str, **kwargs) -> dict:
    return fetch(hospital_name=hospital_name, **kwargs)
