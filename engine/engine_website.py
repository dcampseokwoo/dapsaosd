"""Phase 3 — 홈페이지 수집(크롤링). 공고 무관 영구 자산.

목적: 소개문 한 줄로는 판정이 어려운 축(end_use·tech_ownership·value_chain·regulatory·
market)을 홈페이지 본문으로 보강한다(메텔 "Smart Pillow" 4단어, 메타맵 산업용/가정용 불명,
포레 가정용/업소용 불명 → 홈페이지로 해소). 수집 결과는 Phase 4 도시에 생성의 입력.

캐시: data/cache/website/{company_id}.json (공고 무관 영구 자산). 재개 가능(있으면 skip).

■ 반드시 지키는 것
- 사명·서비스명을 <ENTITY_NAME> 으로 치환 저장(사명 오염 방지: "로보"트리·파인유얼"뷰티").
- 동일 기업 확인 실패(파킹·다른 회사) → MISMATCH. DB Website 가 낡았을 수 있음.
- robots.txt 존중, 요청 간 딜레이, 텍스트만(이미지·스크립트 제외).

■ access_status (실패 사유를 뭉뚱그리지 않음 — 재시도 가능/불가 구분)
  OK · NOT_FOUND(404) · TIMEOUT(재시도 가능) · BLOCKED(403/robots) · NO_URL ·
  DOMAIN_EXPIRED(DNS 실패·연결 거부·파킹) · MISMATCH(다른 회사)

주의: 실제 네트워크 수집은 outbound egress 가 허용된 환경에서만 동작한다. 순수 함수
(_extract_text·mask_entity·detect_lang·classify_content·_page_kind)는 egress 없이 테스트된다.
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib import robotparser

ROOT = Path(__file__).resolve().parent.parent
WEBSITE_DIR = ROOT / "data" / "cache" / "website"

ACCESS = ("OK", "NOT_FOUND", "TIMEOUT", "BLOCKED", "NO_URL", "DOMAIN_EXPIRED", "MISMATCH")

USER_AGENT = "dcamp-research/1.0 (+hardtech screening; contact via dcamp)"
DEFAULT_DELAY = 2.0          # 요청 간 딜레이(초)
TIMEOUT = 20                 # 초
CA_BUNDLE = "/root/.ccr/ca-bundle.crt"

# 수집 대상 페이지 유형 → 링크 텍스트/URL 키워드(한국어·영어 둘 다)
PAGE_KEYWORDS = {
    "about":      ["about", "회사소개", "회사 소개", "company", "소개", "개요", "who we are"],
    "product":    ["product", "제품", "products", "제품소개", "솔루션", "solution", "서비스", "제품군"],
    "technology": ["technology", "기술", "tech", "r&d", "연구개발", "기술소개", "핵심기술"],
    "usecase":    ["use case", "usecase", "cases", "고객사", "적용사례", "case study",
                   "customers", "레퍼런스", "reference", "portfolio", "적용 사례"],
}

# 도메인 파킹·만료·판매 신호(MISMATCH/DOMAIN_EXPIRED 판별)
_PARKING = re.compile(
    r"domain (is )?for sale|buy this domain|이 ?도메인.*(판매|구매)|"
    r"parked (free|domain)|도메인.*(주차|파킹)|준비 ?중입니다|"
    r"under construction|사이트 준비중|호스팅.*만료|expired",
    re.I)


# ── 순수 함수(egress 불필요, 테스트 대상) ─────────────────────────────────
class _TextExtractor(HTMLParser):
    """script·style·head 를 제외한 가시 텍스트만 수집(이미지·스크립트 제외)."""
    _SKIP = {"script", "style", "noscript", "meta", "link", "svg"}

    def __init__(self):
        super().__init__()
        self._skip_depth = 0
        self.parts: list[str] = []
        self.title = ""
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skip_depth += 1
        if tag == "title":
            self._in_title = True

    def handle_endtag(self, tag):
        if tag in self._SKIP and self._skip_depth:
            self._skip_depth -= 1
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._skip_depth:
            return
        s = data.strip()
        if not s:
            return
        if self._in_title:
            self.title = (self.title + " " + s).strip()
        self.parts.append(s)


def extract_text(html: str) -> tuple[str, str]:
    """HTML → (가시 텍스트, title). 실패해도 예외 없이 최대한."""
    p = _TextExtractor()
    try:
        p.feed(html)
    except Exception:
        pass
    text = re.sub(r"[ \t]+", " ", "\n".join(p.parts))
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text, p.title


def detect_lang(text: str) -> str:
    """한글 비율로 ko/en/mixed 판정(간이)."""
    hangul = len(re.findall(r"[가-힣]", text))
    latin = len(re.findall(r"[A-Za-z]", text))
    if hangul == 0 and latin == 0:
        return "unknown"
    r = hangul / (hangul + latin)
    return "ko" if r > 0.6 else ("en" if r < 0.2 else "mixed")


def _name_variants(name_ko: str, name_en: str = "") -> list[str]:
    """사명 치환용 변형 목록. 법인격·공백 제거형까지. 긴 것부터(부분치환 방지)."""
    out = set()
    for nm in (name_ko or "", name_en or ""):
        nm = nm.strip()
        if not nm:
            continue
        out.add(nm)
        stripped = re.sub(r"주식회사|\(주\)|㈜|\(유\)|Inc\.?|Corp\.?|Co\.?,?\s*Ltd\.?|LLC", "", nm, flags=re.I).strip()
        if stripped:
            out.add(stripped)
            out.add(stripped.replace(" ", ""))
    return sorted({v for v in out if len(v) >= 2}, key=len, reverse=True)


def mask_entity(text: str, name_ko: str, name_en: str = "",
                extra_names: list[str] | None = None) -> str:
    """사명·서비스명을 <ENTITY_NAME> 으로 치환(사명 오염 방지)."""
    variants = _name_variants(name_ko, name_en)
    for e in (extra_names or []):
        e = (e or "").strip()
        if len(e) >= 2:
            variants.append(e)
    variants = sorted(set(variants), key=len, reverse=True)
    for v in variants:
        text = re.sub(re.escape(v), "<ENTITY_NAME>", text, flags=re.I)
    return text


def classify_content(text: str, title: str, name_ko: str, name_en: str = "") -> str:
    """수집된 본문이 실제 그 회사인지 판정 → OK / MISMATCH / DOMAIN_EXPIRED.

    파킹·만료 신호 → DOMAIN_EXPIRED. 본문이 너무 짧고 사명 흔적 없음 → MISMATCH 의심.
    """
    if _PARKING.search(text) or _PARKING.search(title):
        return "DOMAIN_EXPIRED"
    variants = _name_variants(name_ko, name_en)
    has_name = any(re.search(re.escape(v), text + " " + title, re.I) for v in variants)
    if len(text) < 120 and not has_name:
        return "MISMATCH"
    return "OK"


def _page_kind(href: str, link_text: str) -> str | None:
    """링크(href·텍스트) → 수집 대상 페이지 유형 or None."""
    hay = f"{href} {link_text}".lower()
    for kind, kws in PAGE_KEYWORDS.items():
        if any(k in hay for k in kws):
            return kind
    return None


class _LinkFinder(HTMLParser):
    def __init__(self):
        super().__init__(); self.links = []; self._href=None; self._txt=[]
    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self._href = dict(attrs).get("href"); self._txt=[]
    def handle_data(self, data):
        if self._href is not None:
            self._txt.append(data)
    def handle_endtag(self, tag):
        if tag == "a" and self._href:
            self.links.append((self._href, " ".join(self._txt).strip()))
            self._href=None; self._txt=[]


def discover_pages(base_url: str, home_html: str) -> dict[str, str]:
    """홈 HTML → {page_kind: 절대 URL} (about/product/technology/usecase). 같은 도메인만."""
    lf = _LinkFinder()
    try:
        lf.feed(home_html)
    except Exception:
        pass
    base_host = urlparse(base_url).netloc
    found: dict[str, str] = {}
    for href, txt in lf.links:
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        kind = _page_kind(href, txt)
        if not kind or kind in found:
            continue
        absu = urljoin(base_url, href)
        if urlparse(absu).netloc == base_host:   # 같은 도메인만
            found[kind] = absu
    return found


# ── 네트워크(egress 필요) ────────────────────────────────────────────────
def _company_id(row: dict) -> str:
    cid = (row.get("biz_no") or row.get("uid") or row.get("name_ko") or "unknown").strip()
    return re.sub(r"[^0-9A-Za-z가-힣_-]", "_", cid)[:80]


def _normalize_url(u: str) -> str:
    u = (u or "").strip()
    if not u:
        return ""
    if not u.startswith(("http://", "https://")):
        u = "https://" + u
    return u


def _fetch(url: str):
    """(status_code, final_url, text) or ('ERR', reason, ''). requests + 프록시 CA."""
    import requests
    verify = CA_BUNDLE if Path(CA_BUNDLE).exists() else True
    try:
        r = requests.get(url, timeout=TIMEOUT, allow_redirects=True,
                         headers={"User-Agent": USER_AGENT}, verify=verify)
        return r.status_code, r.url, r.text
    except requests.exceptions.Timeout:
        return "TIMEOUT", url, ""
    except requests.exceptions.ProxyError as e:
        return "EGRESS", str(e), ""              # 프록시 egress 차단 = 환경 문제(사이트 문제 아님)
    except requests.exceptions.SSLError as e:
        return "ERR", f"ssl:{e}", ""
    except requests.exceptions.ConnectionError as e:
        return "DOMAIN_EXPIRED", str(e), ""      # DNS 실패·연결 거부 = 도메인 만료 의심
    except Exception as e:
        return "ERR", str(e), ""


class EgressBlocked(RuntimeError):
    """outbound egress 가 막힌 환경 — 전량 오분류 방지 위해 크게 실패."""


def egress_available() -> bool:
    """외부 수집이 가능한 환경인지 1회 probe. 크롤 전 호출해 조용한 오분류 방지."""
    code, _, _ = _fetch("https://example.com/")
    return not (code == "EGRESS")


def _robots_ok(base_url: str) -> bool:
    try:
        rp = robotparser.RobotFileParser()
        rp.set_url(urljoin(base_url, "/robots.txt"))
        rp.read()
        return rp.can_fetch(USER_AGENT, base_url)
    except Exception:
        return True   # robots 판독 실패 시 보수적으로 허용(딜레이는 유지)


def crawl_one(row: dict, *, delay: float = DEFAULT_DELAY, force: bool = False) -> dict:
    """기업 1곳 수집 → 레코드 dict(+파일 저장). 이미 있으면 skip(재개)."""
    WEBSITE_DIR.mkdir(parents=True, exist_ok=True)
    cid = _company_id(row)
    out_path = WEBSITE_DIR / f"{cid}.json"
    if out_path.exists() and not force:
        return json.loads(out_path.read_text(encoding="utf-8"))

    url = _normalize_url(row.get("website", ""))
    rec = {"company_id": cid, "biz_no": row.get("biz_no", ""),
           "url": url, "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "access_status": "NO_URL", "pages": {}, "text_length": 0, "lang": "unknown"}
    if not url:
        out_path.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        return rec

    if not _robots_ok(url):
        rec["access_status"] = "BLOCKED"; rec["block_reason"] = "robots.txt disallow"
        out_path.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        return rec

    code, final, html = _fetch(url)
    if code == "EGRESS":
        raise EgressBlocked("outbound egress 차단 — 웹 접근 가능한 환경/세션에서 실행하세요")
    if code == "TIMEOUT":
        rec["access_status"] = "TIMEOUT"
    elif code == "DOMAIN_EXPIRED":
        rec["access_status"] = "DOMAIN_EXPIRED"; rec["error"] = final[:200]
    elif code == "ERR":
        rec["access_status"] = "DOMAIN_EXPIRED"; rec["error"] = final[:200]
    elif isinstance(code, int) and code == 404:
        rec["access_status"] = "NOT_FOUND"
    elif isinstance(code, int) and code in (401, 403):
        rec["access_status"] = "BLOCKED"
    elif isinstance(code, int) and code >= 400:
        rec["access_status"] = "DOMAIN_EXPIRED"; rec["error"] = f"http {code}"
    else:
        # 200: 홈 + 하위 페이지 수집
        name_ko, name_en = row.get("name_ko", ""), row.get("name_en", "")
        pages = {}
        home_text, home_title = extract_text(html)
        status = classify_content(home_text, home_title, name_ko, name_en)
        rec["access_status"] = status
        if status == "OK":
            pages["main"] = mask_entity(home_text, name_ko, name_en, [row.get("svc", "")])
            for kind, purl in discover_pages(final, html).items():
                time.sleep(delay)
                c2, f2, h2 = _fetch(purl)
                if isinstance(c2, int) and c2 == 200 and h2:
                    t2, _ = extract_text(h2)
                    pages[kind] = mask_entity(t2, name_ko, name_en, [row.get("svc", "")])
        rec["pages"] = pages
        allt = "\n".join(pages.values())
        rec["text_length"] = len(allt)
        rec["lang"] = detect_lang(allt)

    out_path.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    return rec


def crawl(rows: list[dict], *, delay: float = DEFAULT_DELAY, force: bool = False,
         progress_every: int = 25) -> dict:
    """여러 기업 수집(재개 가능). 반환: access_status 분포 요약."""
    from collections import Counter
    if not egress_available():
        raise EgressBlocked("outbound egress 차단 — 전량 오분류 방지 위해 중단. "
                            "웹 접근 가능한 환경/세션에서 실행하세요.")
    dist = Counter()
    for i, row in enumerate(rows, 1):
        rec = crawl_one(row, delay=delay, force=force)
        dist[rec["access_status"]] += 1
        if rec["access_status"] not in ("NO_URL",) and not (WEBSITE_DIR / f"{_company_id(row)}.json").exists():
            pass
        if i % progress_every == 0:
            print(f"  {i}/{len(rows)} … {dict(dist)}")
        if rec.get("_skipped") is None:      # 실제 요청한 경우에만 딜레이
            time.sleep(delay)
    return {"total": len(rows), "access_status": dict(dist)}


def report() -> dict:
    """수집 캐시 요약: access_status 분포 + 텍스트 길이 분포."""
    from collections import Counter
    recs = [json.loads(p.read_text(encoding="utf-8"))
            for p in WEBSITE_DIR.glob("*.json")] if WEBSITE_DIR.exists() else []
    dist = Counter(r["access_status"] for r in recs)
    lens = sorted(r["text_length"] for r in recs if r["access_status"] == "OK")
    def pct(p):
        return lens[int(len(lens) * p)] if lens else 0
    ok = dist.get("OK", 0)
    with_url = sum(v for k, v in dist.items() if k != "NO_URL")
    return {
        "collected": len(recs),
        "access_status": dict(dist),
        "collection_rate_of_url": round(ok / with_url, 3) if with_url else 0,
        "text_length": {"min": lens[0] if lens else 0, "p25": pct(.25), "median": pct(.5),
                        "p75": pct(.75), "max": lens[-1] if lens else 0},
    }
