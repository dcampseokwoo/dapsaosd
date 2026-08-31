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

순서(중요): 200 응답이면 (1) 원문 추출 → (2) **원문(치환 전)으로** MISMATCH/JS/파킹 판정 →
(3) OK 일 때만 사명 치환 후 저장. 사명 치환을 판정보다 먼저 하면 "사명 못 찾음 → MISMATCH"
오탐이 난다(v1 버그). MISMATCH 는 사명 부재가 아니라 **다른 도메인 리다이렉트 + 사명 부재**로만.

주의: 실제 네트워크 수집은 outbound egress 가 허용된 환경에서만 동작한다. 순수 함수
(extract_text·mask_entity·detect_lang·classify_content·looks_js_rendered·is_mismatch·
_page_kind·discover_pages)는 egress 없이 테스트된다(tests/test_engine_website.py, 13건).
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

ACCESS = ("OK", "NOT_FOUND", "TIMEOUT", "BLOCKED", "NO_URL", "DOMAIN_EXPIRED",
          "MISMATCH", "JS_REQUIRED", "TLS_ERROR")
# JS_REQUIRED: 200 이지만 본문이 클라이언트(JS) 렌더 — requests 로는 셸(title)만 받음. 재수집(렌더링) 필요.
# TLS_ERROR : SSL 인증서/가로채기 오류(로컬 보안 프로그램 등) — 환경 문제, 재시도 가능. DOMAIN_EXPIRED 와 구분.

CRAWLER_VERSION = "2"        # v1(파싱 버그: title만 저장·MISMATCH 오탐) 산출물은 stale 로 자동 재수집

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
        if self._in_title:                    # title 은 body 텍스트(parts)에 넣지 않는다
            self.title = (self.title + " " + s).strip()
            return
        self.parts.append(s)


def extract_text(html: str) -> tuple[str, str]:
    """HTML → (**본문**(<body> 가시 텍스트, title 제외), title). 실패해도 예외 없이 최대한.

    title 은 parts 에 섞지 않으므로, 반환된 본문 길이가 곧 '실제 콘텐츠 유무'의 지표다
    (JS 셸이면 본문이 거의 0 이 되어 JS_REQUIRED 판별이 가능해진다)."""
    p = _TextExtractor()
    try:
        p.feed(html)
    except Exception:
        pass
    text = re.sub(r"[ \t]+", " ", "\n".join(p.parts))
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text, p.title


# JS(클라이언트) 렌더 앱 신호 — 본문이 비어 있을 때 JS_REQUIRED 판별에 사용
_JS_APP = re.compile(
    r'id=["\'](root|app|__next|__nuxt|q-app)["\']|__NEXT_DATA__|__NUXT__|'
    r'window\.__|ng-version|data-reactroot|v-cloak|'
    r'(enable|turn on|활성화).{0,20}(javascript|자바스크립트)|'
    r'(javascript|자바스크립트).{0,20}(필요|required|enable)', re.I)


def looks_js_rendered(html: str, body_text: str) -> bool:
    """본문이 거의 없는데 JS 앱 신호가 있으면 클라이언트 렌더로 본다."""
    return len(body_text) < 60 and bool(_JS_APP.search(html or ""))


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


MIN_BODY = 60        # 실제 콘텐츠로 인정하는 최소 본문 길이(title 제외)


def classify_content(body_text: str, title: str, html: str = "") -> str:
    """**원문(치환 전) 본문**으로 콘텐츠 유형 판정 → OK / DOMAIN_EXPIRED / JS_REQUIRED.

    사명 존재 여부는 여기서 보지 않는다(MISMATCH 는 crawl_one 이 도메인 리다이렉트로 판정).
    영문 브랜드 사이트가 한글 등록명을 본문에 안 써서 생기던 MISMATCH 오탐을 없앤다.
    """
    if _PARKING.search(body_text) or _PARKING.search(title):
        return "DOMAIN_EXPIRED"                       # 파킹·판매·만료
    if len(body_text) < MIN_BODY:
        return "JS_REQUIRED"                          # 본문 없음 = 정적 fetch 로 못 얻음(JS/빈 셸)
    return "OK"


def _registrable(host: str) -> str:
    """도메인의 등록가능 부분(대략) — 리다이렉트가 '다른 회사'인지 판별용. 마지막 두 라벨."""
    host = (host or "").lower().split(":")[0]
    parts = [p for p in host.split(".") if p]
    # co.kr / or.kr 등 2단계 국가 도메인은 세 라벨로
    if len(parts) >= 3 and parts[-1] == "kr" and parts[-2] in ("co", "or", "ne", "go", "re", "pe"):
        return ".".join(parts[-3:])
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def is_mismatch(orig_url: str, final_url: str, body_text: str, title: str,
                name_ko: str, name_en: str = "") -> bool:
    """다른 회사로 판정: **최종 도메인이 원 도메인과 다른데(리다이렉트)** 본문·제목에 사명 흔적도 없음.
    같은 회사가 도메인만 바꾼 정상 리다이렉트(사명 존재)는 MISMATCH 아님."""
    if _registrable(urlparse(orig_url).netloc) == _registrable(urlparse(final_url).netloc):
        return False                                  # 같은 도메인 계열 → MISMATCH 아님
    variants = _name_variants(name_ko, name_en)
    has_name = any(re.search(re.escape(v), body_text + " " + title, re.I) for v in variants)
    return not has_name                               # 다른 도메인 + 사명 흔적 없음 = 다른 회사


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


def _fetch(url: str) -> dict:
    """1회 GET. 반환 dict: {code, final, text, err_class, err}. requests + 프록시 CA.

    code: HTTP 정수 / 'TIMEOUT' / 'TLS' / 'EGRESS' / 'CONN'. err 에 예외 메시지(사후 분석용)."""
    import requests
    verify = CA_BUNDLE if Path(CA_BUNDLE).exists() else True
    try:
        r = requests.get(url, timeout=TIMEOUT, allow_redirects=True,
                         headers={"User-Agent": USER_AGENT}, verify=verify)
        return {"code": r.status_code, "final": r.url, "text": r.text, "err_class": "", "err": ""}
    except requests.exceptions.Timeout as e:
        return {"code": "TIMEOUT", "final": url, "text": "", "err_class": "timeout", "err": str(e)[:300]}
    except requests.exceptions.ProxyError as e:
        return {"code": "EGRESS", "final": url, "text": "", "err_class": "proxy", "err": str(e)[:300]}
    except requests.exceptions.SSLError as e:
        # 로컬 보안 프로그램의 SSL 가로채기 등 — 환경 문제, DOMAIN_EXPIRED 와 구분(재시도 가능)
        return {"code": "TLS", "final": url, "text": "", "err_class": "ssl", "err": str(e)[:300]}
    except requests.exceptions.ConnectionError as e:
        return {"code": "CONN", "final": url, "text": "", "err_class": "conn", "err": str(e)[:300]}
    except Exception as e:
        return {"code": "CONN", "final": url, "text": "", "err_class": "other", "err": str(e)[:300]}


class EgressBlocked(RuntimeError):
    """outbound egress 가 막힌 환경 — 전량 오분류 방지 위해 크게 실패."""


def egress_available() -> bool:
    """외부 수집이 가능한 환경인지 1회 probe. 크롤 전 호출해 조용한 오분류 방지."""
    return _fetch("https://example.com/")["code"] != "EGRESS"


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
        prev = json.loads(out_path.read_text(encoding="utf-8"))
        if prev.get("crawler_version") == CRAWLER_VERSION:
            prev["_fetched"] = False                     # 캐시 skip(재개) — 네트워크 요청 없음
            return prev
        # 구버전(v1: 파싱 버그) 산출물은 stale → 재수집

    url = _normalize_url(row.get("website", ""))
    rec = {"company_id": cid, "biz_no": row.get("biz_no", ""), "crawler_version": CRAWLER_VERSION,
           "url": url, "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "access_status": "NO_URL", "pages": {}, "text_length": 0, "lang": "unknown",
           "error_class": "", "error": ""}

    def _save():
        out_path.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        rec["_fetched"] = rec["access_status"] != "NO_URL"   # NO_URL 은 요청 안 함
        return rec

    if not url:
        return _save()
    if not _robots_ok(url):
        rec["access_status"] = "BLOCKED"; rec["error_class"] = "robots"; rec["error"] = "robots.txt disallow"
        return _save()

    f = _fetch(url)
    code, final = f["code"], f["final"]
    rec["final_url"] = final
    rec["error_class"], rec["error"] = f["err_class"], f["err"]
    if code == "EGRESS":
        raise EgressBlocked("outbound egress 차단 — 웹 접근 가능한 환경/세션에서 실행하세요")
    if code == "TIMEOUT":
        rec["access_status"] = "TIMEOUT"; return _save()
    if code == "TLS":
        rec["access_status"] = "TLS_ERROR"; return _save()      # SSL 가로채기 등 환경 문제(재시도 가능)
    if code == "CONN":
        rec["access_status"] = "DOMAIN_EXPIRED"; return _save()  # DNS 실패·연결 거부
    if isinstance(code, int) and code == 404:
        rec["access_status"] = "NOT_FOUND"; return _save()
    if isinstance(code, int) and code in (401, 403):
        rec["access_status"] = "BLOCKED"; return _save()
    if isinstance(code, int) and code >= 400:
        rec["access_status"] = "DOMAIN_EXPIRED"; rec["error"] = f"http {code}"; return _save()

    # 200 — 순서: (1) 원문 추출 (2) 원문으로 MISMATCH/JS/파킹 판정 (3) OK 일 때만 치환 저장
    html = f["text"]
    name_ko, name_en, svc = row.get("name_ko", ""), row.get("name_en", ""), row.get("svc", "")
    body_text, title = extract_text(html)               # 본문(title 제외)
    if is_mismatch(url, final, body_text, title, name_ko, name_en):
        rec["access_status"] = "MISMATCH"; rec["error"] = f"redirected to {final}"; return _save()
    status = classify_content(body_text, title, html)   # OK / DOMAIN_EXPIRED / JS_REQUIRED (치환 전)
    rec["access_status"] = status
    if status == "OK":
        pages = {"main": mask_entity(body_text, name_ko, name_en, [svc])}   # ← 판정 후 치환
        for kind, purl in discover_pages(final, html).items():
            time.sleep(delay)
            f2 = _fetch(purl)
            if isinstance(f2["code"], int) and f2["code"] == 200 and f2["text"]:
                t2, _ = extract_text(f2["text"])
                if len(t2) >= MIN_BODY:
                    pages[kind] = mask_entity(t2, name_ko, name_en, [svc])
        rec["pages"] = pages
        allt = "\n".join(pages.values())
        rec["text_length"] = len(allt)
        rec["lang"] = detect_lang(allt)
    return _save()


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
        if i % progress_every == 0:
            print(f"  {i}/{len(rows)} … {dict(dist)}")
        if rec.get("_fetched"):              # 실제 네트워크 요청한 경우에만 딜레이(캐시 skip 제외)
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
    # 재시도 가치 있는 실패(환경/렌더링 문제): 재수집하면 OK 될 수 있음
    retryable = sum(dist.get(k, 0) for k in ("TIMEOUT", "TLS_ERROR", "JS_REQUIRED"))
    stale = sum(1 for r in recs if r.get("crawler_version") != CRAWLER_VERSION)
    return {
        "collected": len(recs),
        "access_status": dict(dist),
        "collection_rate_of_url": round(ok / with_url, 3) if with_url else 0,
        "retryable(TIMEOUT+TLS+JS_REQUIRED)": retryable,
        "stale_v1_needs_recollect": stale,
        "text_length_OK": {"min": lens[0] if lens else 0, "p25": pct(.25), "median": pct(.5),
                           "p75": pct(.75), "max": lens[-1] if lens else 0},
    }
