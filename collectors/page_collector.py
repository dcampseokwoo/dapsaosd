"""근거 기사 본문 확보 (선택적) — grounding 스니펫이 부족할 때 원문 텍스트 확인용."""
from __future__ import annotations

import logging
import re

import requests

log = logging.getLogger(__name__)

_TAG_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>|<[^>]+>", re.DOTALL | re.IGNORECASE)
_WS_RE = re.compile(r"\s+")

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; StageResearchBot/1.0)"}


def fetch_page_text(url: str, max_chars: int = 4000, timeout: int = 10) -> str:
    """URL 본문 텍스트(태그 제거, 공백 정리). 실패 시 빈 문자열 — 파이프라인 진행에 영향 없음."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
        text = _TAG_RE.sub(" ", resp.text)
        text = _WS_RE.sub(" ", text).strip()
        return text[:max_chars]
    except Exception as e:
        log.debug("페이지 수집 실패 %s: %s", url, e)
        return ""
