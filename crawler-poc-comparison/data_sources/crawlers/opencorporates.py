"""工商基础爬虫 · OpenCorporates(降级链第 2 级,v1.2)。"""
from __future__ import annotations

import time
from urllib.parse import quote

from bs4 import BeautifulSoup

from data_sources.crawlers.base import CrawlerError, fetch_html, parse_date_loose
from schemas import BasicFields, BasicResult


class OpenCorporatesCrawler:
    SOURCE_NAME = "opencorporates.com"
    BASE_URL = "https://opencorporates.com"

    async def fetch(self, company_name: str) -> BasicResult:
        start = time.time()
        def ms() -> int:
            return int((time.time() - start) * 1000)

        url = f"{self.BASE_URL}/companies?q={quote(company_name)}&jurisdiction_code=kh"
        try:
            html = await fetch_html(url)
        except CrawlerError as exc:
            return _err(self.SOURCE_NAME, exc, url, ms())
        soup = BeautifulSoup(html, "lxml")
        link = soup.select_one("li.search-result a, .companies a, a[href*='/companies/kh/']")
        if not link:
            return BasicResult(
                source=self.SOURCE_NAME, status="no_match",
                fields=BasicFields(country_region="Cambodia"), fields_filled=1,
                source_url=url, duration_ms=ms(), raw_snippet=html[:300],
            )
        href = link.get("href", "")
        detail_url = href if href.startswith("http") else self.BASE_URL + href
        try:
            dhtml = await fetch_html(detail_url)
        except CrawlerError as exc:
            return _err(self.SOURCE_NAME, exc, detail_url, ms())
        ds = BeautifulSoup(dhtml, "lxml")
        h1 = ds.select_one("h1")
        incorp = ds.select_one(".company-incorporation-date, dd.incorporation_date")
        fields = BasicFields(
            company_full_name=h1.get_text(strip=True) if h1 else None,
            country_region="Cambodia",
            established_date=parse_date_loose(incorp.get_text(strip=True) if incorp else None),
        )
        filled = sum(1 for v in fields.model_dump().values() if v is not None)
        return BasicResult(
            source=self.SOURCE_NAME, status="ok" if filled > 1 else "no_match",
            fields=fields, fields_filled=filled, source_url=detail_url, duration_ms=ms(),
        )


def _err(source: str, exc: CrawlerError, url: str, ms: int) -> BasicResult:
    status = "access_restricted" if exc.status_code in (401, 403) else (
        "timeout" if "timeout" in str(exc).lower() else "error"
    )
    return BasicResult(
        source=source, status=status, fields=BasicFields(), fields_filled=0,
        source_url=url, http_status_code=exc.status_code, duration_ms=ms,
        error_detail=str(exc)[:300],
    )
