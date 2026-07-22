"""모니터링 공통 유틸 — 페이지 수집, 스냅샷 저장/비교(diff), 리포트 저장.

기존 파이프라인의 page_collector 를 확장:
- 페이지당 수집 상한을 크게(PAGE_MAX_CHARS) 잡고
- 이전 실행 스냅샷과 비교해 "무엇이 바뀌었는지" diff 를 만든다.
모든 단계는 실패 시 빈 값 반환 — 모니터는 계속 진행한다.
"""
from __future__ import annotations

import datetime as dt
import difflib
import hashlib
import json
import logging
import re
import time

import requests

import config

log = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept-Language": "ko,en;q=0.8",
}
FETCH_DELAY_SEC = 1.5
_last_fetch = 0.0

_TAG_RE = re.compile(r"<(script|style|noscript)[^>]*>.*?</\1>|<[^>]+>",
                     re.DOTALL | re.IGNORECASE)
_WS_RE = re.compile(r"[ \t\r\f\v]+")
_NL_RE = re.compile(r"\n{3,}")


def today() -> str:
    return dt.date.today().isoformat()


def fetch_page_text(url: str, max_chars: int | None = None, timeout: int = 20) -> str:
    """URL 본문 텍스트 (태그 제거, 줄 구조는 대략 보존). 실패 시 빈 문자열."""
    global _last_fetch
    wait = FETCH_DELAY_SEC - (time.time() - _last_fetch)
    if wait > 0:
        time.sleep(wait)
    _last_fetch = time.time()
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
        html = resp.text
    except Exception as e:
        log.warning("페이지 수집 실패 %s: %s", url, e)
        return ""
    # 블록 태그를 줄바꿈으로 바꿔 diff 가 줄 단위로 의미를 갖게 한다
    html = re.sub(r"(?i)<(br|/p|/div|/li|/h[1-6]|/tr)[^>]*>", "\n", html)
    text = _TAG_RE.sub(" ", html)
    text = _WS_RE.sub(" ", text)
    text = "\n".join(line.strip() for line in text.split("\n"))
    text = _NL_RE.sub("\n\n", text).strip()
    return text[: max_chars or config.PAGE_MAX_CHARS]


# ---------------------------------------------------------------- 스냅샷
def _snapshot_path(slug: str, label: str):
    d = config.SNAPSHOT_DIR / slug
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{label}.json"


def load_snapshot(slug: str, label: str) -> dict:
    path = _snapshot_path(slug, label)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        log.warning("스냅샷 손상 — 새로 저장: %s", path)
        return {}


def save_snapshot(slug: str, label: str, url: str, text: str) -> None:
    path = _snapshot_path(slug, label)
    path.write_text(json.dumps({
        "url": url,
        "fetched_at": dt.datetime.now().isoformat(timespec="seconds"),
        "sha1": hashlib.sha1(text.encode("utf-8")).hexdigest(),
        "text": text,
    }, ensure_ascii=False, indent=1), encoding="utf-8")


def diff_texts(old: str, new: str, max_lines: int = 120) -> str:
    """이전/현재 스냅샷의 unified diff (변경 없으면 빈 문자열)."""
    if old == new:
        return ""
    lines = list(difflib.unified_diff(
        old.splitlines(), new.splitlines(),
        fromfile="이전", tofile="현재", lineterm="", n=1,
    ))
    body = [l for l in lines[2:] if l and l[0] in "+-" ]  # 변경 줄만
    if not body:
        return ""
    if len(body) > max_lines:
        body = body[:max_lines] + [f"... (변경 줄 {len(body) - max_lines}개 생략)"]
    return "\n".join(body)


def check_page(slug: str, label: str, url: str) -> dict:
    """페이지 수집 → 스냅샷 비교 → 저장.

    반환: {url, label, text, changed(bool), first_seen(bool), diff}
    """
    text = fetch_page_text(url)
    prev = load_snapshot(slug, label)
    result = {
        "label": label, "url": url, "text": text,
        "changed": False, "first_seen": not prev, "diff": "",
        "fetch_failed": not text,
    }
    if not text:
        return result  # 실패 시 스냅샷을 덮어쓰지 않음 (오탐 방지)
    if prev and prev.get("text") != text:
        result["changed"] = True
        result["diff"] = diff_texts(prev.get("text", ""), text)
    save_snapshot(slug, label, url, text)
    return result


# ---------------------------------------------------------------- 로그/리포트
def append_jsonl(path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_jsonl(path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _output_dir(subdir: str):
    d = config.OUTPUT_DIR / subdir if subdir else config.OUTPUT_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def write_report(name: str, text: str, subdir: str = ""):
    """output/{subdir}/{name}_{YYMMDD}.md 저장, 경로 반환 (모니터별 폴더 분리)."""
    path = _output_dir(subdir) / f"{name}_{dt.date.today().strftime('%y%m%d')}.md"
    path.write_text(text, encoding="utf-8")
    return path


def write_json(name: str, data, subdir: str = ""):
    """output/{subdir}/{name}_{YYMMDD}.json 저장, 경로 반환."""
    path = _output_dir(subdir) / f"{name}_{dt.date.today().strftime('%y%m%d')}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def make_gemini_client(max_calls: int | None = None, no_ai: bool = False):
    """(client, use_ai) — 키가 없거나 --no-ai 면 AI 없이 수집만 진행."""
    if no_ai:
        return None, False
    try:
        from ai.gemini import GeminiClient
        return GeminiClient(max_calls=max_calls), True
    except RuntimeError as e:
        log.warning("%s — AI 분석 없이 수집만 진행합니다 (--no-ai 와 동일).", e)
        return None, False
