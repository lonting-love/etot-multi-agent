"""可插拔 Web 搜索工具。

DeepSeek 不支持 OpenAI 的 {"type": "web_search"} 内建工具，这里改为普通 function tool：
按环境变量选择 Tavily / Serper / Bocha，均未配置时回退到 ddgs（需 pip install ddgs）。
"""

from __future__ import annotations

import requests
from langchain_core.tools import tool

from modules.config import BOCHA_API_KEY, SEARCH_PROVIDER, SERPER_API_KEY, TAVILY_API_KEY
from modules.observability import trace

TIMEOUT_SECONDS = 20
MAX_QUERY_CHARS = 200
DEFAULT_RESULTS = 6


def _clean(results: list[dict], limit: int) -> list[dict]:
    cleaned, seen = [], set()
    for item in results:
        url = str(item.get("url") or "").strip()
        if not url.startswith(("http://", "https://")) or url in seen:
            continue
        seen.add(url)
        cleaned.append(
            {
                "title": str(item.get("title") or "").strip()[:200],
                "url": url,
                "snippet": " ".join(str(item.get("snippet") or "").split())[:500],
                "date": str(item.get("date") or "").strip()[:40],
            }
        )
        if len(cleaned) >= limit:
            break
    return cleaned


def _tavily(query: str, limit: int) -> list[dict]:
    resp = requests.post(
        "https://api.tavily.com/search",
        json={
            "api_key": TAVILY_API_KEY,
            "query": query,
            "max_results": limit,
            "search_depth": "basic",
            "include_answer": False,
        },
        timeout=TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    data = resp.json()
    return [
        {
            "title": item.get("title"),
            "url": item.get("url"),
            "snippet": item.get("content"),
            "date": item.get("published_date"),
        }
        for item in data.get("results", [])
    ]


def _serper(query: str, limit: int) -> list[dict]:
    resp = requests.post(
        "https://google.serper.dev/search",
        headers={"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"},
        json={"q": query, "num": limit, "hl": "zh-cn", "gl": "cn"},
        timeout=TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    data = resp.json()
    return [
        {
            "title": item.get("title"),
            "url": item.get("link"),
            "snippet": item.get("snippet"),
            "date": item.get("date"),
        }
        for item in data.get("organic", [])
    ]


def _bocha(query: str, limit: int) -> list[dict]:
    resp = requests.post(
        "https://api.bochaai.com/v1/web-search",
        headers={"Authorization": f"Bearer {BOCHA_API_KEY}", "Content-Type": "application/json"},
        json={"query": query, "count": limit, "summary": True},
        timeout=TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    pages = (((resp.json().get("data") or {}).get("webPages") or {}).get("value")) or []
    return [
        {
            "title": item.get("name"),
            "url": item.get("url"),
            "snippet": item.get("summary") or item.get("snippet"),
            "date": item.get("datePublished") or item.get("dateLastCrawled"),
        }
        for item in pages
    ]


def _ddgs(query: str, limit: int) -> list[dict]:
    try:
        from ddgs import DDGS
    except ImportError:
        from duckduckgo_search import DDGS  # 兼容旧包名
    rows = DDGS().text(query, max_results=limit, region="cn-zh")
    return [
        {"title": row.get("title"), "url": row.get("href"), "snippet": row.get("body"), "date": row.get("date")}
        for row in rows
    ]


def _providers() -> list[tuple[str, object]]:
    configured = []
    if TAVILY_API_KEY:
        configured.append(("tavily", _tavily))
    if SERPER_API_KEY:
        configured.append(("serper", _serper))
    if BOCHA_API_KEY:
        configured.append(("bocha", _bocha))
    configured.append(("ddgs", _ddgs))
    if SEARCH_PROVIDER != "auto":
        ordered = [item for item in configured if item[0] == SEARCH_PROVIDER]
        return ordered or configured
    return configured


@tool("web_search")
def web_search(query: str, max_results: int = DEFAULT_RESULTS) -> str:
    """联网搜索最新信息。输入查询词，返回标题、链接、日期与摘要列表。"""
    query = " ".join(str(query).split())[:MAX_QUERY_CHARS]
    if not query:
        return "搜索词为空，请提供具体的关键词。"
    limit = max(1, min(int(max_results or DEFAULT_RESULTS), 10))

    attempts: list[str] = []
    for name, handler in _providers():
        try:
            results = _clean(handler(query, limit), limit)
        except Exception as exc:  # noqa: BLE001 - 逐个降级，最终统一返回失败原因
            attempts.append(f"{name}: {type(exc).__name__}")
            trace("search.error", provider=name, query=query, error=str(exc)[:200])
            continue
        trace("search.ok", provider=name, query=query, results=len(results))
        if not results:
            attempts.append(f"{name}: 无结果")
            continue
        lines = [f"共找到 {len(results)} 条结果（来源: {name}）"]
        for index, item in enumerate(results, 1):
            lines.append(f"{index}. {item['title'] or '(无标题)'}")
            lines.append(f"   链接: {item['url']}")
            if item["date"]:
                lines.append(f"   日期: {item['date']}")
            if item["snippet"]:
                lines.append(f"   摘要: {item['snippet']}")
        return "\n".join(lines)

    return "未检索到有效来源（" + "; ".join(attempts) + "）。请更换关键词，或配置 TAVILY_API_KEY / SERPER_API_KEY / 安装 ddgs。"
