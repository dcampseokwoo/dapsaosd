"""AC/컨설팅 업체(Long Story Short, Upright, Intralink 등) 최신 동향 감시.

비교 시트에 있는 업체들의 웹사이트를 주기적으로 크롤링해
- 서비스/가격 변경 여부 (이전 실행 스냅샷과 diff 비교)
- 새로운 멘토/인력 영입 소식 (뉴스 검색 + 페이지 변경 내용)
을 감지하고 Gemini 로 요약해 마크다운 리포트를 만든다.

대상 목록은 config.AC_TARGETS 기본값을 쓰되, data/ac_targets.json 이 있으면
그 파일이 우선한다 (같은 구조의 JSON 배열 — URL 보강/추가는 그 파일에서).
페이지 URL 이 비어 있는 업체(예: Long Story Short)는 뉴스 검색만 수행한다.
"""
from __future__ import annotations

import json
import logging

import config
from collectors import naver_search, news_search
from extractors.investment_extractor import extract_json
from monitors import common

log = logging.getLogger(__name__)

# ---------------------------------------------------------------- 프롬프트
ANALYSIS_PROMPT = """\
당신은 한국 스타트업 지원기관(디캠프)의 리서처다. 아래는 액셀러레이터/컨설팅 업체
"{name}" 의 (1) 웹사이트 변경 diff 와 (2) 최근 뉴스 검색 결과다.
이 자료만 근거로 다음을 판단하라 — 추측 금지, 근거 없는 항목은 빈 배열로 두라.

중점 확인 사항: {watch_hints}

=== 웹사이트 변경 (이전 스냅샷 대비 diff, '-'=삭제 '+'=추가) ===
{diff_block}

=== 최근 뉴스 검색 결과 ===
{news_block}

판단 기준:
- service_changes: 서비스 구성·프로그램 신설/종료 등 실질 변경만 (단순 문구 수정 제외)
- pricing_changes: 가격·수수료·지분 조건 변경
- people_changes: 멘토·심사역·파트너 등 인력 영입/이탈 (특히 500 Global 등 유명 AC 출신)
- 날짜 표기나 저작권 연도 같은 잡음 변경은 무시하라.

다음 JSON 한 개만 출력하라 (다른 텍스트 금지):
{{
 "service_changes": [{{"what": "무엇이 바뀌었나", "evidence": "근거 (diff 인용 또는 기사)"}}],
 "pricing_changes": [{{"what": "...", "evidence": "..."}}],
 "people_changes": [{{"who": "인물/직책", "what": "영입/이탈 내용", "evidence": "..."}}],
 "other_updates": ["그 외 주목할 소식"],
 "alert": true·false — 비교 시트 갱신이 필요한 변경이 있으면 true,
 "summary": "두세 문장 요약 (변경 없으면 '특이사항 없음')"
}}
"""


def load_targets() -> list[dict]:
    """data/ac_targets.json 이 있으면 우선, 없으면 config.AC_TARGETS."""
    if config.AC_TARGETS_JSON.exists():
        try:
            targets = json.loads(config.AC_TARGETS_JSON.read_text(encoding="utf-8"))
            if isinstance(targets, list) and targets:
                log.info("대상 목록 로드: %s (%d개)", config.AC_TARGETS_JSON.name, len(targets))
                return targets
        except Exception as e:
            log.warning("ac_targets.json 파싱 실패(%s) — 기본값 사용", e)
    return config.AC_TARGETS


def _search_news(target: dict) -> list[dict]:
    results = []
    for q in target.get("news_queries", []):
        results.append(news_search.search_news(q, max_items=5))
        results.append(naver_search.search_news(q, max_items=5))
    return news_search.merge_results(*results, cap=12)


def _diff_block(page_results: list[dict]) -> str:
    parts = []
    for p in page_results:
        if p["fetch_failed"]:
            parts.append(f"### [{p['label']}] {p['url']}\n(수집 실패)")
        elif p["first_seen"]:
            parts.append(f"### [{p['label']}] {p['url']}\n(첫 수집 — 비교 기준 스냅샷 저장됨)")
        elif p["changed"]:
            parts.append(f"### [{p['label']}] {p['url']}\n{p['diff'] or '(전면 개편 수준의 변경)'}")
        else:
            parts.append(f"### [{p['label']}] {p['url']}\n(변경 없음)")
    return "\n\n".join(parts) or "(감시 중인 페이지 없음 — 뉴스만 확인)"


def check_target(target: dict, client=None, use_ai: bool = True) -> dict:
    """업체 1곳: 페이지 스냅샷 비교 + 뉴스 수집 + AI 분석."""
    name, slug = target["name"], target["slug"]
    log.info("[AC 감시] %s — 페이지 %d개, 쿼리 %d개",
             name, len(target.get("pages", {})), len(target.get("news_queries", [])))

    page_results = [common.check_page(slug, label, url)
                    for label, url in (target.get("pages") or {}).items()]
    news = _search_news(target)
    changed = [p for p in page_results if p["changed"]]

    analysis = {}
    # 볼 것이 있을 때만 AI 호출 (첫 수집만 있고 뉴스도 없으면 스킵 — 호출 절약)
    worth_ai = bool(changed or news)
    if use_ai and client is not None and worth_ai:
        try:
            ans = client.plain(ANALYSIS_PROMPT.format(
                name=name,
                watch_hints=target.get("watch_hints", "-"),
                diff_block=_diff_block(page_results),
                news_block=news_search.format_block(news),
            ), model=config.MODEL_MONITOR)
            analysis = extract_json(ans.text)
        except Exception as e:
            log.warning("[AC 감시] %s 분석 실패: %s", name, e)

    record = {
        "monitor": "ac_watch", "checked_at": common.today(),
        "name": name, "slug": slug,
        "pages": [{"label": p["label"], "url": p["url"], "changed": p["changed"],
                   "first_seen": p["first_seen"], "fetch_failed": p["fetch_failed"],
                   "diff": p["diff"]} for p in page_results],
        "news": news,
        "analysis": analysis,
    }
    common.append_jsonl(config.MONITOR_LOG_PATH, {
        "monitor": "ac_watch", "checked_at": common.today(), "name": name,
        "changed_pages": len(changed), "alert": bool(analysis.get("alert")),
    })
    return record


def run(client=None, use_ai: bool = True, only_slug: str | None = None):
    """전체 대상 순회 → 리포트 저장. 리포트 경로 반환."""
    targets = load_targets()
    if only_slug:
        targets = [t for t in targets if t["slug"] == only_slug]
        if not targets:
            raise SystemExit(f"대상 slug 없음: {only_slug} "
                             f"(가능: {', '.join(t['slug'] for t in load_targets())})")
    records = [check_target(t, client, use_ai) for t in targets]
    common.write_json("ac_watch_status", records)
    path = common.write_report("ac_watch_report", render_report(records))
    log.info("[AC 감시] 리포트 저장: %s", path)
    return path


# ---------------------------------------------------------------- 리포트
def render_report(records: list[dict]) -> str:
    checked = records[0]["checked_at"] if records else common.today()
    lines = [f"# AC 업체 동향 모니터링 리포트 ({checked})", ""]

    alerts = [r for r in records if r["analysis"].get("alert")]
    if alerts:
        lines.append("> ⚠️ **비교 시트 갱신 필요**: " + ", ".join(r["name"] for r in alerts))
        lines.append("")

    for r in records:
        a = r["analysis"]
        lines.append(f"## {r['name']}")
        if a.get("summary"):
            lines.append(f"{a['summary']}")
            lines.append("")

        sections = [
            ("서비스 변경", a.get("service_changes") or [], ("what", "evidence")),
            ("가격/조건 변경", a.get("pricing_changes") or [], ("what", "evidence")),
        ]
        for title, items, keys in sections:
            if items:
                lines.append(f"### {title}")
                for it in items:
                    lines.append(f"- {it.get(keys[0], '')} — _{it.get(keys[1], '')}_")
                lines.append("")
        people = a.get("people_changes") or []
        if people:
            lines.append("### 인력 영입/이탈")
            for it in people:
                lines.append(f"- **{it.get('who', '')}**: {it.get('what', '')} — _{it.get('evidence', '')}_")
            lines.append("")
        for other in a.get("other_updates") or []:
            lines.append(f"- (기타) {other}")

        # 페이지 상태
        lines.append("### 감시 페이지 상태")
        if not r["pages"]:
            lines.append("- 등록된 페이지 없음 — `data/ac_targets.json` 에 URL을 채우면 변경 감지가 활성화됩니다.")
        for p in r["pages"]:
            status = ("수집 실패" if p["fetch_failed"] else
                      "첫 수집(기준 저장)" if p["first_seen"] else
                      "**변경 감지**" if p["changed"] else "변경 없음")
            lines.append(f"- [{p['label']}]({p['url']}): {status}")
            if p["changed"] and p["diff"]:
                lines.append("```diff\n" + p["diff"][:2000] + "\n```")
        lines.append("")

        if r["news"]:
            lines.append("### 최근 뉴스")
            for n in r["news"][:6]:
                lines.append(f"- [{n['date'] or '날짜미상'}] [{n['title']}]({n['link']})")
            lines.append("")
    return "\n".join(lines) + "\n"
