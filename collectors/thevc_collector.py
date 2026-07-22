"""THE VC(thevc.kr) 회사 페이지 수집 — 2단계 검증의 교차 확인 소스.

무료로 열람 가능한 회사 페이지의 제목/설명/본문 요약을 가져와
검증 프롬프트에 넣는다. 페이지 검색은 DuckDuckGo HTML(키 불필요) 사용.
모든 단계는 실패해도 빈 값을 돌려주고 파이프라인은 계속 진행된다.
"""
from __future__ import annotations

import logging
import re
import time
import urllib.parse

import requests

log = logging.getLogger(__name__)

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
FETCH_DELAY_SEC = 1.5
_last_fetch = 0.0

_DDG_LINK_RE = re.compile(r'href="//duckduckgo\.com/l/\?uddg=([^"&]+)', re.IGNORECASE)
_PLAIN_LINK_RE = re.compile(r'href="(https?://(?:www\.)?thevc\.kr/[^"]+)"', re.IGNORECASE)
_META_RE = re.compile(
    r'<meta[^>]+(?:name|property)="(?:description|og:description|og:title)"[^>]+content="([^"]*)"',
    re.IGNORECASE)
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
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


def find_company_url(name_kr: str) -> str:
    """DuckDuckGo에서 site:thevc.kr 회사 페이지 URL 탐색. 실패 시 빈 문자열."""
    query = f'site:thevc.kr "{name_kr}"'
    url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query)
    try:
        html = _throttled_get(url)
    except Exception as e:
        log.debug("DDG 검색 실패 %r: %s", query, e)
        return ""
    candidates = []
    for enc in _DDG_LINK_RE.findall(html):
        candidates.append(urllib.parse.unquote(enc))
    candidates.extend(_PLAIN_LINK_RE.findall(html))
    for u in candidates:
        path = urllib.parse.urlparse(u).path.strip("/")
        # 회사 페이지는 thevc.kr/{slug} 한 단계 경로 (search/browse 등 제외)
        if u.startswith("http") and "thevc.kr" in u and path \
                and "/" not in path and path not in ("search", "browse", "login"):
            return u.split("?")[0]
    return ""


def fetch_summary(url: str, max_chars: int = 1500) -> str:
    """회사 페이지의 title + meta 설명 + 본문 앞부분."""
    try:
        html = _throttled_get(url)
    except Exception as e:
        log.debug("THE VC 페이지 수집 실패 %s: %s", url, e)
        return ""
    parts = []
    m = _TITLE_RE.search(html)
    if m:
        parts.append(_WS_RE.sub(" ", m.group(1)).strip())
    parts.extend(c.strip() for c in _META_RE.findall(html) if c.strip())
    body = _WS_RE.sub(" ", _TAG_RE.sub(" ", html)).strip()
    if body:
        parts.append(body[:max_chars])
    # 중복 제거하며 합치기
    seen, out = set(), []
    for p in parts:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return "\n".join(out)[: max_chars + 300]


def get_block(name_kr: str) -> str:
    """검증 프롬프트 삽입용 THE VC 블록. 못 찾으면 빈 문자열."""
    url = find_company_url(name_kr)
    if not url:
        return ""
    summary = fetch_summary(url)
    if not summary:
        return ""
    return f"[THE VC 페이지 {url}]\n{summary}"
