"""Phase 3 크롤러의 순수 함수(egress 불필요) 회귀 테스트.

네트워크 수집 자체는 egress 있는 환경에서만 동작하지만, 판정 품질을 좌우하는 로직
(텍스트 추출·사명 치환·언어·MISMATCH·링크 탐색)은 여기서 결정적으로 검증한다.
"""
from engine import engine_website as W


def test_extract_text_strips_script_style():
    html = ("<html><head><title>회사소개</title><style>.x{}</style></head>"
            "<body><script>var a=1</script><h1>초음파 건조기</h1>"
            "<p>산업용 세척 장비</p></body></html>")
    text, title = W.extract_text(html)
    assert "초음파 건조기" in text and "산업용 세척 장비" in text
    assert "var a=1" not in text and ".x{}" not in text
    assert title == "회사소개"


def test_detect_lang():
    assert W.detect_lang("초음파 건조기를 만드는 회사입니다 산업용 세척") == "ko"
    assert W.detect_lang("We manufacture ultrasonic drying equipment for industry") == "en"
    assert W.detect_lang("ultrasonic 초음파 dryer 건조기 mixed 혼합 text 텍스트 abc def") in ("mixed", "ko", "en")


def test_mask_entity_removes_name_pollution():
    # "로보"트리·파인유얼"뷰티" 오염 방지 — 사명이 판정 텍스트에 남으면 안 됨
    text = "주식회사 로보트리는 코딩 교육 로봇키트를 만듭니다. 로보트리의 제품은..."
    masked = W.mask_entity(text, "주식회사 로보트리", "Robotree")
    assert "로보트리" not in masked
    assert "<ENTITY_NAME>" in masked
    assert "코딩 교육 로봇키트" in masked   # 사업 내용은 보존


def test_mask_entity_english_and_service():
    text = "FineYourBeauty Inc. runs a fitness platform. FineYourBeauty helps users train."
    masked = W.mask_entity(text, "파인유얼뷰티", "FineYourBeauty", extra_names=["FYB"])
    assert "FineYourBeauty" not in masked
    assert "fitness platform" in masked


def test_classify_content_parking_and_mismatch():
    assert W.classify_content("이 도메인은 판매 중입니다", "", "메타맵") == "DOMAIN_EXPIRED"
    assert W.classify_content("Buy this domain now", "for sale", "포레") == "DOMAIN_EXPIRED"
    assert W.classify_content("짧은글", "", "포레") == "MISMATCH"           # 짧고 사명 흔적 없음
    long_ok = "포레는 업소용 제빙기를 제조합니다. " * 10
    assert W.classify_content(long_ok, "포레", "포레") == "OK"


def test_page_kind_ko_en():
    assert W._page_kind("/about", "회사소개") == "about"
    assert W._page_kind("/tech", "Technology") == "technology"
    assert W._page_kind("/cases", "적용사례") == "usecase"
    assert W._page_kind("/products", "제품") == "product"
    assert W._page_kind("/blog", "블로그") is None


def test_discover_pages_same_domain_only():
    html = ('<a href="/about">회사소개</a>'
            '<a href="https://other.com/tech">기술</a>'        # 다른 도메인 → 제외
            '<a href="/products/list">제품</a>')
    pages = W.discover_pages("https://acme.co.kr/", html)
    assert pages.get("about") == "https://acme.co.kr/about"
    assert pages.get("product") == "https://acme.co.kr/products/list"
    assert "technology" not in pages       # 다른 도메인이라 제외돼야


def test_access_status_taxonomy_complete():
    assert set(W.ACCESS) == {"OK", "NOT_FOUND", "TIMEOUT", "BLOCKED", "NO_URL",
                             "DOMAIN_EXPIRED", "MISMATCH"}


def test_crawl_aborts_when_egress_blocked(monkeypatch):
    # egress 차단 시 전량 오분류 대신 크게 실패해야 한다
    monkeypatch.setattr(W, "egress_available", lambda: False)
    try:
        W.crawl([{"name_ko": "x", "website": "https://x.co", "biz_no": "1"}], delay=0)
        assert False, "EgressBlocked 가 발생해야 함"
    except W.EgressBlocked:
        pass
