"""구글 뉴스 RSS 검색 — API 키/결제 불필요 (무료 검색 경로).

Gemini Google Search grounding(유료 티어 전용) 대신, 뉴스 검색을 직접 수행해
결과 목록을 Gemini(무료 티어) 프롬프트에 넣어 판단시키는 용도.
"""
from __future__ import annotations

import email.utils
import logging
import time
import urllib.parse
import xml.etree.ElementTree as ET

import requests

log = logging.getLogger(__name__)

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; StageResearchBot/1.0)"}
FETCH_DELAY_SEC = 1.0  # RSS 요청 간 예의상 딜레이
_last_fetch = 0.0


def search_news(query: str, max_items: int = 8, timeout: int = 15) -> list[dict]:
    """구글 뉴스 검색 결과 [{title, link, source, date}] (최신순, 한국 뉴스)."""
    global _last_fetch
    wait = FETCH_DELAY_SEC - (time.time() - _last_fetch)
    if wait > 0:
        time.sleep(wait)
    _last_fetch = time.time()

    url = ("https://news.google.com/rss/search?q="
           + urllib.parse.quote(query) + "&hl=ko&gl=KR&ceid=KR:ko")
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
        return parse_rss(resp.content)[:max_items]
    except Exception as e:
        log.warning("뉴스 검색 실패 %r: %s", query, e)
        return []


def parse_rss(content: bytes) -> list[dict]:
    results = []
    root = ET.fromstring(content)
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        if not title:
            continue
        source = item.findtext("source") or ""
        date = ""
        pub = item.findtext("pubDate")
        if pub:
            try:
                date = email.utils.parsedate_to_datetime(pub).strftime("%Y-%m-%d")
            except Exception:
                date = pub[:16]
        results.append({
            "title": title,
            "link": (item.findtext("link") or "").strip(),
            "source": source.strip(),
            "date": date,
        })
    return results


def format_block(results: list[dict], with_desc: bool = True) -> str:
    """검색 결과를 프롬프트 삽입용 번호 목록으로 (with_desc=False면 요약 생략, 배치용)."""
    if not results:
        return "(검색 결과 없음)"
    lines = []
    for i, r in enumerate(results, 1):
        src = f" ({r['source']})" if r.get("source") else ""
        lines.append(f"{i}. [{r['date'] or '날짜미상'}] {r['title']}{src}\n   링크: {r['link']}")
        if with_desc and r.get("desc"):
            lines.append(f"   요약: {r['desc']}")
    return "\n".join(lines)


def merge_results(*result_lists: list[dict], cap: int = 12) -> list[dict]:
    """여러 소스의 검색 결과를 제목 기준 중복 제거 후 최신순 정렬."""
    merged, seen = [], set()
    for results in result_lists:
        for r in results:
            key = (r.get("title") or "").replace(" ", "")
            if key and key not in seen:
                seen.add(key)
                merged.append(r)
    merged.sort(key=lambda r: r.get("date") or "0000", reverse=True)
    return merged[:cap]
