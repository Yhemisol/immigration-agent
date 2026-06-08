"""Crawlers for USCIS, SEVP, State Department, and Federal Register."""
import re
import time
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterator

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; ImmigrationBot/1.0; +https://github.com/immigration-agent)"
    )
}
TIMEOUT = 30


@dataclass
class RawItem:
    source: str
    url: str
    title: str
    content: str


def _get(url: str, retries: int = 3) -> httpx.Response | None:
    for attempt in range(retries):
        try:
            r = httpx.get(url, headers=HEADERS, timeout=TIMEOUT, follow_redirects=True)
            r.raise_for_status()
            return r
        except Exception as exc:
            logger.warning("GET %s attempt %d failed: %s", url, attempt + 1, exc)
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
    return None


def _text(soup: BeautifulSoup, selector: str) -> str:
    el = soup.select_one(selector)
    return el.get_text(" ", strip=True) if el else ""


# ---------------------------------------------------------------------------
# USCIS News & Alerts
# ---------------------------------------------------------------------------

USCIS_NEWS_URL = "https://www.uscis.gov/newsroom/news-releases"
USCIS_ALERTS_URL = "https://www.uscis.gov/newsroom/alerts"
USCIS_POLICY_URL = "https://www.uscis.gov/policy-manual/updates"


def _crawl_uscis_listing(url: str, source_tag: str) -> Iterator[RawItem]:
    resp = _get(url)
    if not resp:
        return
    soup = BeautifulSoup(resp.text, "html.parser")
    links = soup.select("div.views-row a[href]")[:20]
    for a in links:
        href = a["href"]
        if not href.startswith("http"):
            href = "https://www.uscis.gov" + href
        title = a.get_text(strip=True)
        detail = _get(href)
        if not detail:
            continue
        dsoup = BeautifulSoup(detail.text, "html.parser")
        body = _text(dsoup, "div.field--name-body") or _text(dsoup, "article")
        if body:
            yield RawItem(source=source_tag, url=href, title=title, content=body[:4000])
        time.sleep(0.5)


def crawl_uscis() -> list[RawItem]:
    items: list[RawItem] = []
    for url, tag in [
        (USCIS_NEWS_URL, "USCIS News"),
        (USCIS_ALERTS_URL, "USCIS Alert"),
        (USCIS_POLICY_URL, "USCIS Policy"),
    ]:
        items.extend(_crawl_uscis_listing(url, tag))
    return items


# ---------------------------------------------------------------------------
# SEVP (Study in the States)
# ---------------------------------------------------------------------------

SEVP_URL = "https://studyinthestates.dhs.gov/students"


def crawl_sevp() -> list[RawItem]:
    resp = _get(SEVP_URL)
    if not resp:
        return []
    soup = BeautifulSoup(resp.text, "html.parser")
    items: list[RawItem] = []
    for article in soup.select("article")[:15]:
        a = article.select_one("a[href]")
        if not a:
            continue
        href = a["href"]
        if not href.startswith("http"):
            href = "https://studyinthestates.dhs.gov" + href
        title = a.get_text(strip=True)
        detail = _get(href)
        if not detail:
            continue
        dsoup = BeautifulSoup(detail.text, "html.parser")
        body = _text(dsoup, "div.field--name-body") or _text(dsoup, "main")
        if body:
            items.append(RawItem(source="SEVP", url=href, title=title, content=body[:4000]))
        time.sleep(0.5)
    return items


# ---------------------------------------------------------------------------
# State Department (Travel / Visa Bulletin)
# ---------------------------------------------------------------------------

STATE_VISA_BULLETIN_URL = "https://travel.state.gov/content/travel/en/legal/visa-law0/visa-bulletin.html"
STATE_ALERTS_URL = "https://travel.state.gov/content/travel/en/News/visalaw.html"


def crawl_state_dept() -> list[RawItem]:
    items: list[RawItem] = []
    for url, tag in [
        (STATE_VISA_BULLETIN_URL, "Visa Bulletin"),
        (STATE_ALERTS_URL, "State Dept Alert"),
    ]:
        resp = _get(url)
        if not resp:
            continue
        soup = BeautifulSoup(resp.text, "html.parser")
        links = soup.select("div.tsg-rwd-main-copy-body a[href]")[:15]
        for a in links:
            href = a["href"]
            if not href.startswith("http"):
                href = "https://travel.state.gov" + href
            title = a.get_text(strip=True) or href
            detail = _get(href)
            if not detail:
                continue
            dsoup = BeautifulSoup(detail.text, "html.parser")
            body = _text(dsoup, "div.tsg-rwd-main-copy-body") or _text(dsoup, "main")
            if body:
                items.append(RawItem(source=tag, url=href, title=title, content=body[:4000]))
            time.sleep(0.5)
    return items


# ---------------------------------------------------------------------------
# Federal Register
# ---------------------------------------------------------------------------

FEDERAL_REGISTER_API = (
    "https://www.federalregister.gov/api/v1/articles.json"
    "?conditions[agencies][]=homeland-security"
    "&conditions[agencies][]=state-department"
    "&conditions[term]=visa+immigration"
    "&order=newest"
    "&per_page=20"
    "&fields[]=title,abstract,html_url,publication_date,document_number"
)

# Also grab recent days
def _fr_url_with_dates() -> str:
    cutoff = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")
    return FEDERAL_REGISTER_API + f"&conditions[publication_date][gte]={cutoff}"


def crawl_federal_register() -> list[RawItem]:
    resp = _get(_fr_url_with_dates())
    if not resp:
        return []
    try:
        data = resp.json()
    except Exception:
        return []
    items: list[RawItem] = []
    for doc in data.get("results", []):
        url = doc.get("html_url", "")
        title = doc.get("title", "")
        abstract = doc.get("abstract", "") or title
        if url and title:
            items.append(RawItem(source="Federal Register", url=url, title=title, content=abstract[:4000]))
    return items


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------

def crawl_all() -> list[RawItem]:
    all_items: list[RawItem] = []
    for name, fn in [
        ("USCIS", crawl_uscis),
        ("SEVP", crawl_sevp),
        ("State Dept", crawl_state_dept),
        ("Federal Register", crawl_federal_register),
    ]:
        logger.info("Crawling %s ...", name)
        try:
            results = fn()
            logger.info("  -> %d items", len(results))
            all_items.extend(results)
        except Exception as exc:
            logger.error("Crawler %s failed: %s", name, exc)
    return all_items
