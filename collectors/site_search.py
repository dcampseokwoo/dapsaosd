"""신뢰 소스(플래텀·벤처스퀘어·와우테일) 사이트 내 검색 + 기사 본문 수집.

2단계 검증에서 뉴스 제목만으로 라운드를 추측하는 환각을 막기 위해,
기사 원문(라운드명이 실제로 등장하는지)과 게시 일자를 직접 확보한다.
모든 단계는 실패 시 빈 값 반환 — 파이프라인은 계속 진행.
"""
from __future__ import annotations

import logging
import re
import time
import urllib.parse

import requests

log = logging.getLogger(__name__)

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
FETCH_DELAY_SEC = 1.0
_last_fetch = 0.0

SITES = [
    ("platum.kr", "https://platum.kr/?s={q}"),
    ("venturesquare.net", "https://www.venturesquare.net/?s={q}"),
    ("wowtale.net", "https://wowtale.net/?s={q}"),
]

_A_RE = re.compile(r'<a[^>]+href="(https?://[^"#]+)"[^>]*>(.*?)</a>',
                   re.DOTALL | re.IGNORECASE)
_DATE_META_RE = re.compile(
    r'<meta[^>]+property="article:published_time"[^>]+content="(\d{4}-\d{2}-\d{2})',
    re.IGNORECASE)
_DATETIME_RE = re.compile(r'datetime="(\d{4}-\d{2}-\d{2})')
_TAG_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>|<[^>]+>", re.DOTALL | re.IGNORECASE)
_WS_RE = re.compile(r"\s+")


def _throttled_get(url: str, timeout: int = 12) -> str:
    global _last_fetch
    wait = FETCH_DELAY_SEC - (time.time() - _last_fetch)
    if wait > 0:
        time.sleep(wait)
    _last_fetch = time.time()
    resp = requests.get(url, headers=HEADERS, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def _strip(html: str) -> str:
    return _WS_RE.sub(" ", _TAG_RE.sub(" ", html)).strip()


def search_site(domain: str, url_tpl: str, name: str, per_site: int = 2) -> list[dict]:
    """사이트 내 검색 결과에서 회사명이 제목에 포함된 기사 링크 추출."""
    try:
        html = _throttled_get(url_tpl.format(q=urllib.parse.quote(name)))
    except Exception as e:
        log.debug("사이트 검색 실패 %s %r: %s", domain, name, e)
        return []
    key = name.replace(" ", "").lower()
    out, seen = [], set()
    for url, inner in _A_RE.findall(html):
        title = _strip(inner)
        if (domain in url and url not in seen and len(title) > len(name) + 2
                and key in title.replace(" ", "").lower()):
            seen.add(url)
            out.append({"url": url.split("?")[0], "title": title})
            if len(out) >= per_site:
                break
    return out


def fetch_article(url: str, max_chars: int = 1800) -> dict:
    """기사 게시 일자 + 본문 앞부분."""
    try:
        html = _throttled_get(url)
    except Exception as e:
        log.debug("기사 수집 실패 %s: %s", url, e)
        return {"url": url, "date": "", "text": ""}
    m = _DATE_META_RE.search(html) or _DATETIME_RE.search(html)
    return {"url": url, "date": m.group(1) if m else "", "text": _strip(html)[:max_chars]}


def collect_articles(name: str, max_articles: int = 3) -> list[dict]:
    """신뢰 소스 3곳 검색 → 상위 기사 본문 수집, 최신순 정렬."""
    hits: list[dict] = []
    for domain, tpl in SITES:
        hits.extend(search_site(domain, tpl, name))
    articles = []
    for h in hits[:max_articles]:
        art = fetch_article(h["url"])
        if art["text"]:
            art["title"] = h["title"]
            articles.append(art)
    articles.sort(key=lambda a: a["date"] or "0000", reverse=True)
    return articles


def format_block(articles: list[dict]) -> str:
    if not articles:
        return "(수집된 기사 없음)"
    parts = []
    for i, a in enumerate(articles, 1):
        parts.append(f"{i}. [{a['date'] or '날짜미상'}] {a.get('title', '')}\n"
                     f"   URL: {a['url']}\n   본문: {a['text']}")
    return "\n".join(parts)
