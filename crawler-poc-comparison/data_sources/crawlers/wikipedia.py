"""工商基础爬虫 · Wikipedia(降级链第 3 级,v1.2)。解析 infobox。"""
from __future__ import annotations

import time
from urllib.parse import quote

from bs4 import BeautifulSoup

from data_sources.crawlers.base import CrawlerError, fetch_html, parse_date_loose
from schemas import BasicFields, BasicResult


class WikipediaCrawler:
    SOURCE_NAME = "en.wikipedia.org"
    BASE_URL = "https://en.wikipedia.org"

    async def fetch(self, company_name: str) -> BasicResult:
        start = time.time()
        def ms() -> int:
            return int((time.time() - start) * 1000)

        url = f"{self.BASE_URL}/wiki/{quote(company_name.replace(' ', '_'))}"
        try:
            html = await fetch_html(url)
        except CrawlerError as exc:
            if exc.status_code == 404:
                return BasicResult(
                    source=self.SOURCE_NAME, status="no_match", fields=BasicFields(),
                    fields_filled=0, source_url=url, http_status_code=404,
                    duration_ms=ms(), error_detail="无对应词条",
                )
            status = "access_restricted" if exc.status_code in (401, 403) else "error"
            return BasicResult(
                source=self.SOURCE_NAME, status=status, fields=BasicFields(),
                fields_filled=0, source_url=url, http_status_code=exc.status_code,
                duration_ms=ms(), error_detail=str(exc)[:300],
            )

        soup = BeautifulSoup(html, "lxml")
        infobox = soup.select_one("table.infobox")
        if not infobox:
            return BasicResult(
                source=self.SOURCE_NAME, status="no_match",
                fields=BasicFields(country_region="Cambodia"), fields_filled=1,
                source_url=url, duration_ms=ms(), raw_snippet=html[:300],
            )

        def ibrow(label: str) -> str | None:
            for th in infobox.select("th"):
                if label.lower() in th.get_text(strip=True).lower():
                    td = th.find_next_sibling("td")
                    return td.get_text(" ", strip=True) if td else None
            return None

        h1 = soup.select_one("h1")
        fields = BasicFields(
            company_full_name=h1.get_text(strip=True) if h1 else None,
            country_region="Cambodia",
            established_date=parse_date_loose(ibrow("Founded")),
            business_scope=ibrow("Industry"),
        )
        filled = sum(1 for v in fields.model_dump().values() if v is not None)
        return BasicResult(
            source=self.SOURCE_NAME, status="ok" if filled > 1 else "no_match",
            fields=fields, fields_filled=filled, source_url=url, duration_ms=ms(),
        )
