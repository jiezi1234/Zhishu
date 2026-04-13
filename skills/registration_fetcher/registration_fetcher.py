"""
registration_fetcher.py — 医院官网 URL 采集

职责（精简后）：
  1. 查询本地缓存（skills/registration_fetcher/hospital_info.json，永久有效）
  2. 缓存未命中时，访问 https://www.yixue.com/<医院名称>，
     解析"医院网站"字段，提取官方网站 URL
  3. 提供 save_to_cache() 供 Agent 在验证 URL 可用后回写缓存

URL 的可用性验证、网络搜索兜底、缓存回写 —— 均由调用方（Agent）负责，
本脚本不执行任何验证或修正，只做"查缓存 → 解析页面 → 返回"。

输入 (fetch):
  hospital_name   str   医院全称，如 "北京协和医院"

输出 dict:
  hospital_name   str   同输入
  official_url    str   从 yixue.com 或缓存中提取的官方网站 URL；
                        失败时为空字符串 ""
  from_cache      bool  True = 来自本地缓存
  timestamp       str   ISO 格式时间戳
"""

import json
import logging
import os
import re
from datetime import datetime
from typing import Optional
from urllib.parse import quote

logger = logging.getLogger(__name__)

# ── 路径常量 ──────────────────────────────────────────────────────────────
_SKILL_DIR  = os.path.dirname(os.path.abspath(__file__))
CACHE_PATH  = os.path.join(_SKILL_DIR, "hospital_info.json")

YIXUE_BASE  = "https://www.yixue.com/"


# ── 公开 API ──────────────────────────────────────────────────────────────

def fetch(hospital_name: str) -> dict:
    """
    获取医院官方网站 URL。

    流程：
      1. 查本地缓存（永久有效）
      2. 缓存未命中 → 访问 yixue.com 解析"医院网站"字段
      3. 返回结果（不做任何 URL 验证）

    Parameters
    ----------
    hospital_name : 医院全称，如 "北京协和医院"

    Returns
    -------
    dict
      hospital_name  str   同输入
      official_url   str   官方网站 URL；无法获取时为 ""
      from_cache     bool
      timestamp      str   ISO 时间戳
    """
    logger.info(f"[registration_fetcher] 查询: {hospital_name}")

    # 1. 缓存命中
    cached = _load_cache(hospital_name)
    if cached:
        logger.info(f"[registration_fetcher] 命中缓存: {hospital_name}")
        return {
            "hospital_name": hospital_name,
            "official_url":  cached.get("official_url", ""),
            "from_cache":    True,
            "timestamp":     datetime.now().isoformat(),
        }

    # 2. 从 yixue.com 解析
    yixue_url    = YIXUE_BASE + quote(hospital_name, safe="")
    official_url = _parse_official_url(yixue_url, hospital_name)

    return {
        "hospital_name": hospital_name,
        "official_url":  official_url,
        "from_cache":    False,
        "timestamp":     datetime.now().isoformat(),
    }


def save_to_cache(hospital_name: str, official_url: str) -> None:
    """
    将已验证的官网 URL 写入缓存。
    由 Agent 在确认 URL 可用后调用。

    Parameters
    ----------
    hospital_name : 医院全称
    official_url  : 经过验证的官方网站 URL
    """
    _write_cache(hospital_name, {
        "official_url": official_url,
        "timestamp":    datetime.now().isoformat(),
    })
    logger.info(f"[registration_fetcher] 已写入缓存: {hospital_name} → {official_url}")


# ── 内部函数 ──────────────────────────────────────────────────────────────

def _parse_official_url(yixue_url: str, hospital_name: str) -> str:
    """
    访问 yixue.com 医院页面，提取"医院网站"字段中的 URL。

    目标 HTML 形如：
      <li><b>医院网站</b>：<a rel="nofollow" class="external free"
          href="http://www.pumch.ac.cn">http://www.pumch.ac.cn</a></li>

    失败时返回空字符串。
    """
    try:
        import urllib.request

        req = urllib.request.Request(
            yixue_url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; HealthPathAgent/1.0)"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="replace")

        # 主模式：<b>医院网站</b> 后紧跟 href
        m = re.search(
            r'<b>医院网站</b>.*?href=["\']([^"\']+)["\']',
            html,
            re.DOTALL | re.IGNORECASE,
        )
        if m:
            url = m.group(1).strip()
            # 若解析到的 URL 以 yixue.com 自身开头，说明是无效内链，视为未找到
            if url.startswith("http://www.yixue.com") or url.startswith("https://www.yixue.com"):
                logger.warning(f"[registration_fetcher] yixue 解析到无效内链，忽略: {url}")
            else:
                logger.info(f"[registration_fetcher] yixue 解析成功: {url}")
                return url

        # 备用模式：页面中"官方网站"附近的外链
        m = re.search(
            r'官方网站.*?href=["\']([^"\']+)["\']',
            html,
            re.DOTALL | re.IGNORECASE,
        )
        if m:
            url = m.group(1).strip()
            # 同样过滤掉 yixue.com 内链
            if url.startswith("http://www.yixue.com") or url.startswith("https://www.yixue.com"):
                logger.warning(f"[registration_fetcher] yixue 备用解析到无效内链，忽略: {url}")
            else:
                logger.info(f"[registration_fetcher] yixue 备用解析: {url}")
                return url

        logger.warning(f"[registration_fetcher] yixue 页面未找到医院网站字段: {hospital_name}")
    except Exception as e:
        logger.warning(f"[registration_fetcher] 访问 yixue.com 失败: {e}")

    return ""


def _load_cache(hospital_name: str) -> Optional[dict]:
    """读缓存；缓存永久有效，仅检查条目是否存在。"""
    if not os.path.exists(CACHE_PATH):
        return None
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            cache = json.load(f)
        entry = cache.get(hospital_name)
        if not entry:
            return None
        return entry
    except Exception:
        pass
    return None


def _write_cache(hospital_name: str, data: dict) -> None:
    """向缓存文件写入（合并已有内容）。"""
    os.makedirs(_SKILL_DIR, exist_ok=True)
    cache: dict = {}
    if os.path.exists(CACHE_PATH):
        try:
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                cache = json.load(f)
        except Exception:
            pass
    cache[hospital_name] = data
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


# ── 便捷入口（AutoClaw / GLM 统一调用）────────────────────────────────────

def run(hospital_name: str, **_kwargs) -> dict:
    """AutoClaw / GLM 调用的统一入口，直接委托给 fetch()。"""
    return fetch(hospital_name=hospital_name)


# ── 命令行快速测试 ────────────────────────────────────────────────────────

if __name__ == "__main__":
    cases = ["北京协和医院", "北京朝阳医院", "北京积水潭医院"]
    for name in cases:
        print(f"\n── {name} ──")
        info = fetch(name)
        print(f"官网:     {info['official_url'] or '(未获取到)'}")
        print(f"来自缓存: {info['from_cache']}")
        print(f"时间戳:   {info['timestamp']}")
