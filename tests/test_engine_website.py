"""Phase 3 크롤러 순수 함수 회귀 테스트 (egress 불필요).

버그 수정 검증:
  ① 본문 추출: <body> 텍스트를 실제로 뽑고, JS 셸(title만)은 JS_REQUIRED 로 구분.
  ② MISMATCH: 원문(치환 전)으로 판정하고, '다른 도메인 리다이렉트 + 사명 부재'로만 판정
     (영문 브랜드가 한글 등록명을 본문에 안 써서 생기던 45% 오탐 제거).
실물 사이트를 못 받는 환경이라 대표 HTML 픽스처를 쓴다(bioplus/speedfloor/castwin = JS 셸 유형).
"""
from engine import engine_website as W


# ── 대표 픽스처 ──────────────────────────────────────────────────────────
STATIC_HTML = ("<html><head><title>초음파세정 | 대양</title><style>.a{}</style></head>"
               "<body><nav>메뉴</nav><h1>초음파 세척 장비</h1>"
               "<p>대양은 산업용 정밀 세척 장비를 자체 설계·제조하는 기업입니다. "
               "반도체·디스플레이 공정에 초음파 세정 시스템을 공급하며, 세정 공정 자동화와 "
               "친환경 용제 순환 설비를 함께 개발합니다.</p>"
               "<script>var x=1</script></body></html>")

# JS 셸: 본문은 root div 뿐, title 만 존재(= bioplus/speedfloor/castwin 이 보인 증상)
JS_SHELL_HTML = ("<html><head><title>바이오플러스(주)</title></head>"
                 "<body><div id=\"root\"></div>"
                 "<noscript>JavaScript를 활성화해 주세요</noscript></body></html>")

PARKING_HTML = ("<html><head><title>도메인</title></head>"
                "<body><h1>이 도메인은 판매 중입니다</h1></body></html>")


# ── ① 본문 추출 ─────────────────────────────────────────────────────────
def test_extract_body_not_just_title():
    body, title = W.extract_text(STATIC_HTML)
    assert "초음파 세척 장비" in body and "산업용 정밀 세척" in body
    assert "반도체·디스플레이 공정" in body
    assert title == "초음파세정 | 대양"
    assert "초음파세정" not in body           # title 은 본문에 섞이지 않는다
    assert "var x=1" not in body and ".a{}" not in body


def test_js_shell_has_no_body():
    body, title = W.extract_text(JS_SHELL_HTML)
    assert title == "바이오플러스(주)"
    assert len(body) < W.MIN_BODY             # 본문 사실상 없음
    assert W.looks_js_rendered(JS_SHELL_HTML, body) is True


def test_classify_static_ok():
    body, title = W.extract_text(STATIC_HTML)
    assert W.classify_content(body, title, STATIC_HTML) == "OK"


def test_classify_js_shell_is_js_required():
    body, title = W.extract_text(JS_SHELL_HTML)
    assert W.classify_content(body, title, JS_SHELL_HTML) == "JS_REQUIRED"


def test_classify_parking_is_domain_expired():
    body, title = W.extract_text(PARKING_HTML)
    assert W.classify_content(body, title, PARKING_HTML) == "DOMAIN_EXPIRED"


def test_three_failing_urls_now_classified_honestly():
    """bioplus/speedfloor/castwin 유형(JS 셸) → OK-빈껍데기가 아니라 JS_REQUIRED 로."""
    for title in ("<ENTITY_NAME>(주)", "A | B", "회사명"):
        html = f"<html><head><title>{title}</title></head><body><div id='app'></div></body></html>"
        body, t = W.extract_text(html)
        assert W.classify_content(body, t, html) == "JS_REQUIRED"


# ── ② MISMATCH: 원문 기준 + 도메인 리다이렉트로만 ──────────────────────────
def test_mismatch_only_on_redirect_to_other_domain():
    # 같은 도메인 → MISMATCH 아님
    assert W.is_mismatch("https://acme.co.kr/", "https://acme.co.kr/main",
                         "산업용 장비", "acme", "에이크미") is False
    # 다른 도메인 + 사명 없음 → MISMATCH
    assert W.is_mismatch("https://acme.co.kr/", "https://parkingpage.com/",
                         "전혀 다른 내용", "", "에이크미") is True
    # 다른 도메인이지만 본문에 사명 있음(정상 이전) → MISMATCH 아님
    assert W.is_mismatch("https://old.co.kr/", "https://newacme.com/",
                         "에이크미는 초음파 장비를 만듭니다", "", "에이크미") is False


def test_mismatch_not_from_name_absence_alone():
    # 영문 브랜드: 같은 도메인이면 한글 등록명이 본문에 없어도 MISMATCH 아님(과거 오탐)
    assert W.is_mismatch("https://bioplus.co.kr/", "https://bioplus.co.kr/",
                         "We develop biomaterials", "", "바이오플러스") is False


# ── 치환은 판정 뒤(순서) ──────────────────────────────────────────────────
def test_mask_after_classify_semantics():
    body, title = W.extract_text(STATIC_HTML)
    assert W.classify_content(body, title, STATIC_HTML) == "OK"   # 원문으로 판정
    masked = W.mask_entity(body, "대양")                          # 그 다음 치환
    assert "대양" not in masked and "<ENTITY_NAME>" in masked
    assert "초음파 세척 장비" in masked                            # 사업 내용 보존


def test_access_status_taxonomy_complete():
    assert set(W.ACCESS) == {"OK", "NOT_FOUND", "TIMEOUT", "BLOCKED", "NO_URL",
                             "DOMAIN_EXPIRED", "MISMATCH", "JS_REQUIRED", "TLS_ERROR"}


def test_crawl_aborts_when_egress_blocked(monkeypatch):
    monkeypatch.setattr(W, "egress_available", lambda: False)
    try:
        W.crawl([{"name_ko": "x", "website": "https://x.co", "biz_no": "1"}], delay=0)
        assert False, "EgressBlocked 가 발생해야 함"
    except W.EgressBlocked:
        pass


def test_detect_lang():
    assert W.detect_lang("초음파 건조기를 만드는 회사입니다 산업용 세척") == "ko"
    assert W.detect_lang("We manufacture ultrasonic drying equipment for industry") == "en"


def test_mask_entity_removes_name_pollution():
    text = "주식회사 로보트리는 코딩 교육 로봇키트를 만듭니다. 로보트리의 제품은..."
    masked = W.mask_entity(text, "주식회사 로보트리", "Robotree")
    assert "로보트리" not in masked and "<ENTITY_NAME>" in masked
    assert "코딩 교육 로봇키트" in masked
