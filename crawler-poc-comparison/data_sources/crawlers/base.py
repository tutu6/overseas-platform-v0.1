"""爬虫基类 + 共享工具(HTTP 抓取、日期解析、负面关键词)。"""
from __future__ import annotations

import re
from datetime import date, datetime

import httpx

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml",
}

_DATE_FORMATS = ("%Y-%m-%d", "%d %B %Y", "%B %d, %Y", "%d/%m/%Y", "%Y/%m/%d")

NEGATIVE_KEYWORDS_EN = [
    "lawsuit", "sued", "fraud", "scandal", "investigation", "bankruptcy",
    "fined", "violation", "illegal", "court", "convicted", "default",
    "breach", "dispute", "litigation", "arrest", "embezzle", "corrupt",
]


class CrawlerError(Exception):
    """爬虫失败(HTTP 错误 / 超时 / DOM 结构变化)。"""


async def fetch_html(url: str, timeout: int = 20) -> str:
    """抓取页面 HTML。4xx/5xx/网络错误 → CrawlerError(含状态码,便于判 blocked)。"""
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            resp = await client.get(url, headers=_HEADERS)
            resp.raise_for_status()
            return resp.text
    except httpx.HTTPStatusError as exc:
        raise CrawlerError(f"HTTP {exc.response.status_code}") from exc
    except httpx.HTTPError as exc:
        raise CrawlerError(f"请求失败: {exc}") from exc


def is_negative(title: str, snippet: str) -> bool:
    text = (title + " " + snippet).lower()
    return any(kw in text for kw in NEGATIVE_KEYWORDS_EN)


def parse_date_loose(text: str | None) -> date | None:
    if not text:
        return None
    text = text.strip()
    m = re.search(r"\d{4}-\d{2}-\d{2}", text)
    if m:
        try:
            return date.fromisoformat(m.group())
        except ValueError:
            pass
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def abs_url(base_url: str, href: str) -> str:
    if not href:
        return ""
    if href.startswith("http"):
        return href
    return base_url.rstrip("/") + ("" if href.startswith("/") else "/") + href
