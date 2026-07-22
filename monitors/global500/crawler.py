"""① 500 Global 프로그램 최신 정보 크롤러 (실행: monitor_500global.py).

500.co 공식 사이트(플래그십 AC 요강·프로그램·포트폴리오·블로그)를 수집해
- 지원 요건 / 다음 배치 지원 마감일 / 배치 일정
- 최근 선발 포트폴리오사 리스트
- 과거 선발 기업들의 공통점(어떤 프로필이 잘 뽑히는지) 분석
을 Gemini 로 구조화 추출하고 마크다운 리포트를 만든다.

500.co 는 JS 렌더링 페이지가 많아 원문 텍스트가 빈약할 수 있다.
→ 구글 뉴스 RSS(+네이버) 교차 검색으로 보완하고,
  유료 티어라면 --search-mode grounding 으로 Gemini 검색을 직접 쓴다.

마감일은 checkpoints/global500_deadline.jsonl 에 이력을 남겨
새 마감일 발견/변경 시 리포트 상단에 알림을 표기한다.
"""
from __future__ import annotations

import datetime as dt
import logging

import config as root_config
from collectors import naver_search, news_search
from extractors.investment_extractor import extract_json
from monitors import common
from monitors.global500 import config as cfg

log = logging.getLogger(__name__)

# ---------------------------------------------------------------- 프롬프트
PROGRAM_PROMPT = """\
당신은 한국 스타트업 지원기관(디캠프)의 리서처다. 아래 제공된 500 Global 공식
사이트 페이지 텍스트와 뉴스 검색 결과만 근거로, 500 Global 액셀러레이터
(특히 Flagship Accelerator) 지원 정보를 구조화하라. 근거 없는 값은 빈 문자열로 두라.

오늘 날짜: {today}
지원 접수 페이지: {apply_url}

=== 500.co 페이지 텍스트 ===
{pages_block}

=== 뉴스 검색 결과 ===
{news_block}

다음 JSON 한 개만 출력하라 (다른 텍스트 금지):
{{
 "next_deadline": "다음 배치 지원 마감일 YYYY-MM-DD (확인 불가 시 빈 문자열)",
 "next_deadline_note": "마감일 근거 한 문장 (rolling admission 여부 포함)",
 "batches": [{{"name": "예: Batch 37", "deadline": "YYYY-MM-DD 또는 미상", "start": "시작 시기", "location": "장소"}}],
 "requirements": ["지원 요건 항목별 (MVP, 유료 고객, 법인 요건 등)"],
 "funding_terms": "투자 조건 (예: $150K for 6% 등, 확인된 것만)",
 "program_format": "기간·형태 (예: 4개월 실리콘밸리 상주)",
 "notes": "그 외 특이사항 한두 문장"
}}
"""

PORTFOLIO_PROMPT = """\
당신은 한국 스타트업 지원기관(디캠프)의 리서처다. 아래 제공된 500 Global
포트폴리오/블로그 페이지 텍스트와 뉴스 검색 결과만 근거로,
(1) 최근 배치에 선발된 포트폴리오사를 목록화하고
(2) 선발 기업들의 공통점을 분석하라 — 어떤 프로필이 잘 뽑히는지가 목적이다.
근거가 없는 회사를 지어내지 마라. 확인된 것만 담아라.

=== 페이지 텍스트 ===
{pages_block}

=== 뉴스 검색 결과 ===
{news_block}

다음 JSON 한 개만 출력하라 (다른 텍스트 금지):
{{
 "recent_companies": [{{"name": "...", "batch": "배치명(미상 가능)", "country": "...", "sector": "...", "one_liner": "한 줄 설명"}}],
 "common_traits": {{
   "sectors": "잘 뽑히는 섹터 경향",
   "stage": "선발 시점 스테이지/트랙션 경향 (매출·유저 등)",
   "geography": "지역 분포 경향 (한국/APAC 포함 여부)",
   "business_model": "B2B/B2C·SaaS 등 모델 경향",
   "team": "팀 프로필 경향 (연쇄창업·글로벌 경험 등)"
 }},
 "fit_advice": "한국 스타트업이 지원할 때 유리한 프로필 요약 2-3문장",
 "evidence_note": "근거의 한계 (페이지 수집 실패·정보 부족 등) 한 문장"
}}
"""

GROUNDING_PROGRAM_QUERY = """\
Search for the latest 500 Global Flagship Accelerator information as of {today}:
application deadline for the next batch, batch schedule, eligibility requirements,
funding terms. Also check https://500.co/founders/flagship .
"""

GROUNDING_PORTFOLIO_QUERY = """\
Search for the most recent 500 Global Flagship Accelerator batch announcements
(selected startups / cohort list) and summarize common traits of selected companies.
"""


def _search_news() -> list[dict]:
    results = []
    for q in cfg.NEWS_QUERIES:
        results.append(news_search.search_news(q, max_items=6))
        results.append(naver_search.search_news(q, max_items=6))
    return news_search.merge_results(*results, cap=20)


def _pages_block(pages: list[dict], per_page: int = 5000) -> str:
    parts = []
    for p in pages:
        status = "수집 실패(JS 렌더링 또는 차단)" if p["fetch_failed"] else ""
        parts.append(f"### [{p['label']}] {p['url']} {status}\n{p['text'][:per_page]}")
    return "\n\n".join(parts) or "(수집된 페이지 없음)"


# ---------------------------------------------------------------- 마감일 추적
def track_deadline(deadline: str, note: str) -> dict:
    """마감일 이력 기록 + 이전 값과 비교.

    반환: {deadline, d_day, changed, first_found, prev}
    - first_found: 이전 기록이 없거나 빈 값이었는데 이번에 마감일이 확인됨
    - changed: 이전에 확인된 마감일과 다른 값이 확인됨 (둘 다 비어있지 않을 때만)
    """
    history = common.read_jsonl(cfg.DEADLINE_LOG)
    prev = history[-1]["deadline"] if history else ""
    first_found = bool(deadline) and not prev
    changed = bool(prev) and bool(deadline) and prev != deadline
    d_day = None
    if deadline:
        try:
            d_day = (dt.date.fromisoformat(deadline) - dt.date.today()).days
        except ValueError:
            pass
    common.append_jsonl(cfg.DEADLINE_LOG, {
        "checked_at": common.today(), "deadline": deadline,
        "d_day": d_day, "note": note,
    })
    return {"deadline": deadline, "d_day": d_day, "changed": changed,
            "first_found": first_found, "prev": prev}


# ---------------------------------------------------------------- 실행
def run(client=None, use_ai: bool = True):
    """수집 → (AI 추출) → 리포트 저장. 리포트 경로 반환."""
    log.info("[500 Global] 공식 페이지 %d개 수집", len(cfg.PAGES))
    pages = [common.check_page(cfg.SLUG, label, url)
             for label, url in cfg.PAGES.items()]
    changed_pages = [p for p in pages if p["changed"]]
    if changed_pages:
        log.info("[500 Global] 변경 감지: %s", ", ".join(p["label"] for p in changed_pages))

    news = _search_news()
    news_block = news_search.format_block(news)

    program, portfolio = {}, {}
    if use_ai and client is not None:
        grounding = root_config.SEARCH_MODE == "grounding"
        try:
            prompt = PROGRAM_PROMPT.format(
                today=common.today(), apply_url=cfg.APPLY_URL,
                pages_block=_pages_block(pages), news_block=news_block)
            if grounding:
                prompt = GROUNDING_PROGRAM_QUERY.format(today=common.today()) + "\n\n" + prompt
                ans = client.grounded(prompt, model=root_config.MODEL_MONITOR)
            else:
                ans = client.plain(prompt, model=root_config.MODEL_MONITOR)
            program = extract_json(ans.text)
        except Exception as e:
            log.warning("[500 Global] 프로그램 정보 추출 실패: %s", e)
        try:
            port_pages = [p for p in pages if p["label"] in cfg.PORTFOLIO_PAGE_LABELS]
            prompt = PORTFOLIO_PROMPT.format(
                pages_block=_pages_block(port_pages), news_block=news_block)
            if grounding:
                prompt = GROUNDING_PORTFOLIO_QUERY + "\n\n" + prompt
                ans = client.grounded(prompt, model=root_config.MODEL_MONITOR)
            else:
                ans = client.plain(prompt, model=root_config.MODEL_MONITOR)
            portfolio = extract_json(ans.text)
        except Exception as e:
            log.warning("[500 Global] 포트폴리오 분석 실패: %s", e)

    deadline_info = track_deadline(
        str(program.get("next_deadline", "") or ""),
        str(program.get("next_deadline_note", "") or ""),
    )

    data = {
        "checked_at": common.today(),
        "deadline": deadline_info,
        "program": program,
        "portfolio": portfolio,
        "changed_pages": [{"label": p["label"], "url": p["url"], "diff": p["diff"]}
                          for p in changed_pages],
        "news": news,
        "fetch_failed": [p["label"] for p in pages if p["fetch_failed"]],
    }
    common.write_json("global500_status", data, subdir=cfg.REPORT_SUBDIR)
    common.append_jsonl(root_config.MONITOR_LOG_PATH, {
        "monitor": "global500", "checked_at": common.today(),
        "deadline": deadline_info["deadline"], "changed_pages": len(changed_pages),
    })
    path = common.write_report("global500_report", render_report(data),
                               subdir=cfg.REPORT_SUBDIR)
    log.info("[500 Global] 리포트 저장: %s", path)
    return path


# ---------------------------------------------------------------- 리포트
def _dday_label(d_day: int | None) -> str:
    if d_day is None:
        return ""
    if d_day >= 0:
        return f" (D-{d_day})"
    return f" (마감 지남 {-d_day}일)"


def render_report(data: dict) -> str:
    dl = data["deadline"]
    program = data.get("program") or {}
    portfolio = data.get("portfolio") or {}
    lines = [f"# 500 Global 프로그램 모니터링 리포트 ({data['checked_at']})", ""]

    # 마감일
    lines.append("## 다음 배치 지원 마감일")
    if dl["deadline"]:
        lines.append(f"- **{dl['deadline']}**{_dday_label(dl['d_day'])}")
    else:
        lines.append("- 확인 불가 (rolling admission 이거나 페이지에서 미확인)")
    if program.get("next_deadline_note"):
        lines.append(f"- 근거: {program['next_deadline_note']}")
    if dl["changed"]:
        lines.append(f"- ⚠️ **마감일 변경 감지**: `{dl['prev']}` → `{dl['deadline']}`")
    elif dl.get("first_found"):
        lines.append("- 🆕 **새 마감일 확인** (이전 실행까지는 미확인)")
    lines.append(f"- 지원 접수: {cfg.APPLY_URL}")
    lines.append("")

    # 배치 일정
    batches = program.get("batches") or []
    if batches:
        lines.append("## 배치 일정")
        lines.append("| 배치 | 마감 | 시작 | 장소 |")
        lines.append("|---|---|---|---|")
        for b in batches:
            lines.append(f"| {b.get('name','')} | {b.get('deadline','')} | "
                         f"{b.get('start','')} | {b.get('location','')} |")
        lines.append("")

    # 지원 요건
    reqs = program.get("requirements") or []
    if reqs or program.get("funding_terms") or program.get("program_format"):
        lines.append("## 지원 요건 / 조건")
        for r in reqs:
            lines.append(f"- {r}")
        if program.get("funding_terms"):
            lines.append(f"- 투자 조건: {program['funding_terms']}")
        if program.get("program_format"):
            lines.append(f"- 프로그램 형태: {program['program_format']}")
        if program.get("notes"):
            lines.append(f"- 비고: {program['notes']}")
        lines.append("")

    # 최근 포트폴리오
    companies = portfolio.get("recent_companies") or []
    if companies:
        lines.append("## 최근 선발 포트폴리오사")
        lines.append("| 회사 | 배치 | 국가 | 섹터 | 설명 |")
        lines.append("|---|---|---|---|---|")
        for c in companies:
            lines.append(f"| {c.get('name','')} | {c.get('batch','')} | {c.get('country','')} "
                         f"| {c.get('sector','')} | {c.get('one_liner','')} |")
        lines.append("")

    # 공통점 분석
    traits = portfolio.get("common_traits") or {}
    if traits:
        lines.append("## 선발 기업 공통점 분석 (어떤 프로필이 잘 뽑히는가)")
        labels = {"sectors": "섹터", "stage": "스테이지/트랙션", "geography": "지역",
                  "business_model": "비즈니스 모델", "team": "팀 프로필"}
        for k, label in labels.items():
            if traits.get(k):
                lines.append(f"- **{label}**: {traits[k]}")
        if portfolio.get("fit_advice"):
            lines.append(f"\n> 💡 {portfolio['fit_advice']}")
        if portfolio.get("evidence_note"):
            lines.append(f"\n_근거 한계: {portfolio['evidence_note']}_")
        lines.append("")

    # 페이지 변경
    if data.get("changed_pages"):
        lines.append("## 공식 페이지 변경 감지")
        for p in data["changed_pages"]:
            lines.append(f"### {p['label']} — {p['url']}")
            if p["diff"]:
                lines.append("```diff\n" + p["diff"] + "\n```")
        lines.append("")

    # 뉴스
    if data.get("news"):
        lines.append("## 관련 뉴스")
        for n in data["news"][:10]:
            lines.append(f"- [{n['date'] or '날짜미상'}] [{n['title']}]({n['link']})")
        lines.append("")

    if data.get("fetch_failed"):
        lines.append(f"_수집 실패 페이지(JS 렌더링/차단 가능): {', '.join(data['fetch_failed'])}"
                     f" — grounding 모드(`--search-mode grounding`) 사용을 권장_")
    return "\n".join(lines) + "\n"
