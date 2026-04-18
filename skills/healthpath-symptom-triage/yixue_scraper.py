#!/usr/bin/env python3
"""
yixue_scraper.py — 医学知识爬虫

从 https://www.yixue.com/常见病自测/ 按 SKILL.md 中列出的固定路由抓取知识，
保存为本地 JSON 文件供 symptom_triage agent 离线查询使用。

用法:
  python skills/symptom_triage/yixue_scraper.py          # 爬取全部路由
  python skills/symptom_triage/yixue_scraper.py --dry    # 只打印将访问的 URL，不实际请求

查询接口（供其他脚本调用）:
  from skills.symptom_triage.yixue_scraper import query_knowledge, search_knowledge

  result = query_knowledge("常见症状辨病/疼痛/头痛")
  results = search_knowledge("发热", top_k=3)
"""

import json
import time
import re
import logging
import argparse
from pathlib import Path
from datetime import datetime
from urllib.parse import quote, unquote

import requests
from bs4 import BeautifulSoup

# ── 配置 ──────────────────────────────────────────────────────────────────
BASE_URL      = "https://www.yixue.com/常见病自测"
SKILL_MD      = Path(__file__).parent / "SKILL.md"
OUTPUT_FILE   = Path(__file__).parent / "yixue_knowledge.json"
REQUEST_DELAY = 1.5       # 每次请求间隔（秒），礼貌爬取
TIMEOUT       = 20

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.yixue.com/",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── 路由读取 ──────────────────────────────────────────────────────────────

def load_routes(skill_md: Path = SKILL_MD) -> list[str]:
    """
    从 SKILL.md 的 ## 路由结构 段落中读取所有路由，返回路径列表。
    例如: ["常见症状辨病", "常见症状辨病/发热", ...]
    """
    text = skill_md.read_text(encoding="utf-8")
    # 定位 ## 路由结构 之后的内容
    match = re.search(r"##\s*路由结构\s*\n(.*?)(?:\n##|\Z)", text, re.DOTALL)
    if not match:
        raise ValueError(f"在 {skill_md} 中未找到 '## 路由结构' 段落")

    routes = []
    for line in match.group(1).splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            routes.append(line)
    return routes


def route_to_url(route: str) -> str:
    """将路由路径转为完整 URL（自动编码中文）"""
    path = f"{BASE_URL}/{route}"
    return quote(path, safe="/:@")


# ── 页面解析 ──────────────────────────────────────────────────────────────

def fetch_page(url: str, session: requests.Session) -> BeautifulSoup | None:
    """请求页面，返回 BeautifulSoup；失败返回 None"""
    try:
        resp = session.get(url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or "utf-8"
        return BeautifulSoup(resp.text, "html.parser")
    except requests.RequestException as e:
        logger.warning(f"请求失败 {unquote(url)}: {e}")
        return None


def parse_content(soup: BeautifulSoup, url: str, route: str) -> dict:
    """
    提取页面标题、分节正文、医学关键词。

    返回结构:
    {
        "title":    str,
        "url":      str,
        "route":    str,        # 如 "常见症状辨病/疼痛/头痛"
        "content":  str,        # 合并后的全文
        "sections": {str: str}, # 章节标题 → 段落
        "keywords": [str],      # 自动抽取的医学词汇
    }
    """
    result = {
        "title":    "",
        "url":      unquote(url),
        "route":    route,
        "content":  "",
        "sections": {},
        "keywords": [],
    }

    # —— 标题 ——
    h1 = soup.find("h1") or soup.find("title")
    if h1:
        result["title"] = h1.get_text(strip=True).split("_")[0].strip()

    # —— 正文容器（兼容 MediaWiki 及普通站点）——
    content_div = (
        soup.find("div", id="mw-content-text")
        or soup.find("div", class_=re.compile(r"content|article|main", re.I))
        or soup.find("article")
        or soup.find("main")
        or soup.body
    )
    if not content_div:
        return result

    # 去除噪音标签
    for tag in content_div.find_all(
        ["nav", "script", "style", "aside", "footer", "header", "form"]
    ):
        tag.decompose()
    for tag in content_div.find_all(
        class_=re.compile(r"nav|menu|sidebar|ad|toc|jump|edit", re.I)
    ):
        tag.decompose()

    # —— 按标题拆分章节 ——
    current_section = "__intro__"
    section_buf: dict[str, list[str]] = {current_section: []}

    for elem in content_div.descendants:
        if not hasattr(elem, "name") or elem.name is None:
            continue
        if elem.name in ("h2", "h3", "h4", "h5"):
            current_section = elem.get_text(strip=True)
            section_buf.setdefault(current_section, [])
        elif elem.name in ("p", "li", "dd", "dt", "td", "th"):
            text = elem.get_text(" ", strip=True)
            if text and len(text) > 1:
                section_buf[current_section].append(text)

    # 合并章节
    sections: dict[str, str] = {}
    for title, lines in section_buf.items():
        merged = "\n".join(dict.fromkeys(lines))  # 去重保序
        if merged.strip():
            sections[title] = merged
    result["sections"] = sections

    # 全文
    result["content"] = "\n\n".join(
        f"【{k}】\n{v}" if k != "__intro__" else v
        for k, v in sections.items()
    )

    # —— 医学关键词抽取 ——
    all_text = content_div.get_text(" ")
    kws = re.findall(
        r'[\u4e00-\u9fa5]{2,8}(?:症|病|炎|癌|痛|热|晕|咳|喘|胀|血|汗|泻|秘|麻|肿)',
        all_text
    )
    result["keywords"] = list(dict.fromkeys(kws))[:30]

    return result


# ── 主爬取流程 ─────────────────────────────────────────────────────────────

def crawl(routes: list[str], dry_run: bool = False) -> dict[str, dict]:
    """
    按路由列表依次抓取页面，返回 {route: page_dict} 字典。
    dry_run=True 时只打印 URL 不实际请求。
    """
    session = requests.Session()
    knowledge: dict[str, dict] = {}
    total = len(routes)

    for i, route in enumerate(routes, 1):
        url = route_to_url(route)
        display = unquote(url)

        if dry_run:
            print(f"[{i}/{total}] {display}")
            continue

        logger.info(f"[{i}/{total}] {display}")
        soup = fetch_page(url, session)

        if soup is None:
            logger.warning(f"  跳过（请求失败）")
            knowledge[route] = {
                "title":    route.split("/")[-1],
                "url":      display,
                "route":    route,
                "content":  "",
                "sections": {},
                "keywords": [],
                "error":    True,
            }
        else:
            page = parse_content(soup, url, route)
            knowledge[route] = page
            content_len = len(page["content"])
            logger.info(f"  ✓ 标题: {page['title'] or '(无)'} | 正文: {content_len} 字符")

        if i < total:
            time.sleep(REQUEST_DELAY)

    return knowledge


def save(knowledge: dict[str, dict], output: Path) -> None:
    """保存知识库 JSON"""
    data = {
        "metadata": {
            "source":      "https://www.yixue.com/常见病自测/",
            "crawled_at":  datetime.now().isoformat(),
            "total_pages": len(knowledge),
            "description": "yixue.com 常见病自测医学知识库，路由来自 SKILL.md",
        },
        "pages": knowledge,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    size_kb = output.stat().st_size // 1024
    logger.info(f"知识库已保存 → {output}  ({size_kb} KB, {len(knowledge)} 页)")


# ── 查询接口（供 agent 调用）────────────────────────────────────────────────

_cache: dict | None = None


def _load(json_path: Path = OUTPUT_FILE) -> dict:
    global _cache
    if _cache is None:
        if not json_path.exists():
            raise FileNotFoundError(
                f"知识库文件不存在: {json_path}\n"
                f"请先运行: python {__file__}"
            )
        _cache = json.loads(json_path.read_text(encoding="utf-8"))
    return _cache


def query_knowledge(path: str, json_path: Path = OUTPUT_FILE) -> dict | None:
    """
    按路由路径查询，支持精确、末尾段、包含三级匹配，最后降级到全文搜索。

    参数:
        path: 路由路径，如 "常见症状辨病/疼痛/头痛" 或仅关键词 "头痛"

    示例:
        >>> r = query_knowledge("常见症状辨病/疼痛/头痛")
        >>> print(r["content"][:300])
    """
    pages: dict = _load(json_path).get("pages", {})
    keyword = path.strip("/")

    # 1. 精确路由匹配
    if keyword in pages:
        return pages[keyword]

    # 2. 路由末尾段匹配（如只传 "头痛"）
    tail_matches = [k for k in pages if k.endswith("/" + keyword) or k == keyword]
    if tail_matches:
        return pages[tail_matches[0]]

    # 3. 路由包含匹配
    partial = [k for k in pages if keyword in k]
    if partial:
        return pages[partial[0]]

    # 4. 全文搜索（按命中频次排序）
    scored = []
    for k, page in pages.items():
        score = page.get("content", "").count(keyword)
        score += page.get("title", "").count(keyword) * 5
        if score > 0:
            scored.append((score, k))
    if scored:
        scored.sort(reverse=True)
        return pages[scored[0][1]]

    return None


def search_knowledge(keyword: str,
                     top_k: int = 5,
                     json_path: Path = OUTPUT_FILE) -> list[dict]:
    """
    全文关键词搜索，返回相关度最高的 top_k 条摘要。

    示例:
        >>> for r in search_knowledge("发热", top_k=3):
        ...     print(r["title"], r["url"])
    """
    pages: dict = _load(json_path).get("pages", {})
    scored = []
    for k, page in pages.items():
        score  = page.get("content", "").count(keyword)
        score += page.get("title", "").count(keyword) * 10
        score += len([kw for kw in page.get("keywords", []) if keyword in kw]) * 3
        if score > 0:
            scored.append((score, k))
    scored.sort(reverse=True)

    results = []
    for _, k in scored[:top_k]:
        p = pages[k]
        results.append({
            "title":   p["title"],
            "route":   p["route"],
            "url":     p["url"],
            "summary": p["content"][:300].replace("\n", " "),
        })
    return results


def list_routes(json_path: Path = OUTPUT_FILE) -> list[str]:
    """返回知识库中所有已爬取的路由列表"""
    return list(_load(json_path).get("pages", {}).keys())


# ── CLI ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="yixue.com 医学知识爬虫（按 SKILL.md 路由抓取）")
    parser.add_argument("--dry",   action="store_true", help="只打印 URL，不发起请求")
    parser.add_argument("--out",   default=str(OUTPUT_FILE), help="输出 JSON 路径")
    parser.add_argument("--query", default=None, help="爬取后测试查询（如 '常见症状辨病/疼痛/头痛'）")
    args = parser.parse_args()

    routes = load_routes()
    logger.info(f"从 SKILL.md 读取到 {len(routes)} 条路由")

    output = Path(args.out)
    knowledge = crawl(routes, dry_run=args.dry)

    if not args.dry:
        save(knowledge, output)

        if args.query:
            global _cache
            _cache = None
            result = query_knowledge(args.query, json_path=output)
            if result:
                print(f"\n── 查询「{args.query}」──")
                print(f"标题 : {result['title']}")
                print(f"URL  : {result['url']}")
                print(f"内容 :\n{result['content'][:500]}")
            else:
                print(f"未找到「{args.query}」相关内容")


if __name__ == "__main__":
    main()
