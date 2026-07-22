"""네이버 뉴스 검색 API — 무료 25,000회/일, 카드 등록 불필요.

developers.naver.com 에서 애플리케이션 등록 → '검색' API 사용 설정 →
Client ID/Secret 을 NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 환경변수로 설정.
키가 없으면 조용히 빈 결과를 반환하고 구글 뉴스만 사용된다.

장점: 한국 매체 커버리지가 넓고, 기사 요약(description)까지 제공되어
제목만 주는 구글 뉴스 RSS보다 판단 근거가 풍부하다.
"""
from __future__ import annotations

import email.utils
import logging
import re
import time
import urllib.parse

import requests

import config

log = logging.getLogger(__name__)

API_URL = "https://openapi.naver.com/v1/search/news.json"
FETCH_DELAY_SEC = 0.15  # 초당 10회 제한 대비
_last_fetch = 0.0

_TAG_RE = re.compile(r"</?b>|<[^>]+>")
_ENTITIES = {"&quot;": '"', "&amp;": "&", "&lt;": "<", "&gt;": ">", "&#39;": "'"}


def enabled() -> bool:
    return bool(config.NAVER_CLIENT_ID and config.NAVER_CLIENT_SECRET)


def _clean(text: str) -> str:
    text = _TAG_RE.sub("", text or "")
    for k, v in _ENTITIES.items():
        text = text.replace(k, v)
    return text.strip()


def parse_items(items: list[dict]) -> list[dict]:
    out = []
    for it in items:
        link = it.get("originallink") or it.get("link") or ""
        date = ""
        if it.get("pubDate"):
            try:
                date = email.utils.parsedate_to_datetime(it["pubDate"]).strftime("%Y-%m-%d")
            except Exception:
                date = str(it["pubDate"])[:16]
        out.append({
            "title": _clean(it.get("title", "")),
            "link": link,
            "source": urllib.parse.urlparse(link).netloc.replace("www.", ""),
            "date": date,
            "desc": _clean(it.get("description", "")),
        })
    return out


def search_news(query: str, max_items: int = 8, sort: str = "date") -> list[dict]:
    """네이버 뉴스 검색. 키 미설정/오류 시 빈 목록 (파이프라인 영향 없음)."""
    if not enabled():
        return []
    global _last_fetch
    wait = FETCH_DELAY_SEC - (time.time() - _last_fetch)
    if wait > 0:
        time.sleep(wait)
    _last_fetch = time.time()
    try:
        resp = requests.get(
            API_URL,
            params={"query": query, "display": min(max_items, 30), "sort": sort},
            headers={
                "X-Naver-Client-Id": config.NAVER_CLIENT_ID,
                "X-Naver-Client-Secret": config.NAVER_CLIENT_SECRET,
            },
            timeout=10,
        )
        resp.raise_for_status()
        return parse_items(resp.json().get("items", []))[:max_items]
    except Exception as e:
        log.warning("네이버 검색 실패 %r: %s", query, e)
        return []
