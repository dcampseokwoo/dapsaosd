"""프롬프트 템플릿 + Gemini 응답(JSON) 파서.

1단계 스크리닝: 검색 1회 → verdict 4분류 (changed/unchanged/no_info/ambiguous)
2단계 정밀 검증: 검색 2-3회 교차 확인 → new_stage/confidence/evidence/source_url
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

import config

VERDICTS = ("changed", "unchanged", "no_info", "ambiguous")


@dataclass
class ScreeningResult:
    verdict: str                 # changed / unchanged / no_info / ambiguous
    new_stage: str = ""          # verdict=changed일 때 후보 스테이지
    note: str = ""
    sources: list[dict] = field(default_factory=list)


@dataclass
class VerificationResult:
    new_stage: str               # 분류 체계 표기
    confidence: str              # high / medium / low
    evidence: str                # 날짜+금액+출처 한 문장
    source_url: str = ""
    note: str = ""               # 폐업/동명기업 등 특이사항
    round_quote: str = ""        # 라운드명이 등장하는 기사 원문 인용
    article_date: str = ""       # 근거 기사 날짜


# ---------------------------------------------------------------- 프롬프트
_STAGE_LIST = ", ".join(config.STAGES[:-1]) + ", IPO('YY), M&A('YY), 알 수 없음"

SCREENING_PROMPT = """\
당신은 한국 스타트업 투자 DB 관리자다. Google 검색 결과만 근거로 판단하라.

회사: {name_kr} ({name_en})
업종: {industry} / 웹사이트: {website}
DB에 기록된 현재 투자 스테이지: {stage}

"{query}" 를 검색해 이 회사의 최신 투자 라운드를 확인하고, 아래 중 하나로만 분류하라.
- changed: DB 기록과 다른 라운드(상향/하향/IPO/M&A)가 명확한 기사로 확인됨
- unchanged: 최신 확인 가능한 라운드가 DB 기록과 일치
- no_info: 투자 관련 정보를 찾지 못함
- ambiguous: 소스 간 상충, 동명 기업 혼동, 라운드명 불명확 등

주의: 업종·웹사이트·서비스명이 일치하는 동일 회사인지 반드시 확인하라.
"누적 투자 N억" 기사만으로 스테이지를 단정하지 마라(라운드명 명시 기사 필요).

다음 JSON 한 개만 출력하라 (다른 텍스트 금지):
{{"verdict": "changed|unchanged|no_info|ambiguous", "new_stage": "변경 시 후보 스테이지({stages}) 아니면 빈 문자열", "note": "한 문장 요약"}}
"""

VERIFICATION_PROMPT = """\
당신은 한국 스타트업 투자 스테이지 검증 담당자다. Google 검색 결과만 근거로 판단하라.

회사: {name_kr} ({name_en})
업종: {industry} / 웹사이트: {website}
DB 기록 스테이지: {stage}
1차 스크리닝 소견: {hint}

{focus} 를 검색해 교차 확인하라. 우선 소스: 플래텀, 벤처스퀘어, 와우테일, 더벨,
THE VC(thevc.kr), 혁신의숲, 주요 경제지. 2024~2026년 자료 우선, 상충 시 최신 기사 우선.
동명 기업 주의 — 업종·웹사이트·서비스명으로 동일성 확인 후에만 채택하라.

규칙:
- 최종 스테이지는 반드시 다음 표기만 사용: {stages}
- IPO/M&A는 연도 필수: IPO('25), M&A('24) 형식
- Pre-A = 프리시리즈A 브릿지. 엔젤/시드 언급은 Seed.
- 기록이 과대 기재됐고 명시적 기사 근거가 있으면 하향도 보고하라.
- "누적 N억" 기사만으로 단정 금지 — 라운드명이 명시된 기사가 필요.
- 폐업/영업종료 발견 시 note에 기록 (스테이지는 최종 확인 단계 유지).
- confidence: high=복수 소스 또는 명확한 단일 공신력 기사 / medium=단일 간접 근거 / low=확인 불가

다음 JSON 한 개만 출력하라 (다른 텍스트 금지):
{{"new_stage": "...", "confidence": "high|medium|low", "evidence": "날짜+금액+출처 한 문장", "source_url": "가장 신뢰할 수 있는 기사 URL", "note": "특이사항(없으면 빈 문자열)"}}
"""


SCREENING_PROMPT_RSS = """\
당신은 한국 스타트업 투자 DB 관리자다. 아래 제공된 뉴스 검색 결과만 근거로 판단하라.

회사: {name_kr} ({name_en})
업종: {industry} / 웹사이트: {website}
DB에 기록된 현재 투자 스테이지: {stage}

"{query}" 구글 뉴스 검색 결과:
{search_block}

위 결과로 이 회사의 최신 투자 라운드를 확인하고, 아래 중 하나로만 분류하라.
- changed: DB 기록과 다른 라운드(상향/하향/IPO/M&A)가 명확한 기사 제목으로 확인됨
- unchanged: 최신 확인 가능한 라운드가 DB 기록과 일치
- no_info: 이 회사의 투자 관련 기사가 없음
- ambiguous: 기사 간 상충, 동명 기업 혼동 가능성, 라운드명 불명확 등

주의: 업종·서비스명이 일치하는 동일 회사 기사인지 반드시 확인하라.
"누적 투자 N억" 제목만으로 스테이지를 단정하지 마라(라운드명 명시 필요).

다음 JSON 한 개만 출력하라 (다른 텍스트 금지):
{{"verdict": "changed|unchanged|no_info|ambiguous", "new_stage": "변경 시 후보 스테이지({stages}) 아니면 빈 문자열", "note": "한 문장 요약"}}
"""

VERIFICATION_PROMPT_RSS = """\
당신은 한국 스타트업 투자 스테이지 검증 담당자다. 아래 제공된 뉴스 검색 결과만 근거로 판단하라.

회사: {name_kr} ({name_en})
업종: {industry} / 웹사이트: {website}
DB 기록 스테이지: {stage}
1차 스크리닝 소견: {hint}

신뢰 소스 기사 본문 발췌 (최신순):
{articles_block}

구글 뉴스 교차 검색 결과 (여러 쿼리 통합, 최신순):
{search_block}

THE VC(투자 DB) 회사 페이지 내용:
{thevc_block}

신뢰 우선 소스: 플래텀, 벤처스퀘어, 와우테일, 더벨, THE VC, 혁신의숲, 주요 경제지.
동명 기업 주의 — 업종·서비스명 일치 확인 후에만 채택.

규칙 (반드시 지켜라):
- **최신 우선**: 같은 회사 기사가 여러 개면 가장 최신 기사를 최우선 근거로 삼아라.
  더 최신 기사가 목록에 있는데 옛 기사를 근거로 들면 안 된다.
- **라운드명 명시 필수**: 기사 제목/본문에 라운드명이 문자 그대로(예: "시리즈A", "프리A",
  "시드") 등장할 때만 그 스테이지를 보고하라. "후속 투자", "추가 투자", "누적 N억"
  같은 표현만으로 다음 라운드를 추정하는 것은 절대 금지.
- round_quote에는 라운드명이 등장하는 기사 문구를 원문 그대로 짧게 인용하라.
  인용할 문구가 없으면 빈 문자열로 두고 confidence는 low로 하라.
- 최종 스테이지는 반드시 다음 표기만 사용: {stages}
- IPO/M&A는 연도 필수: IPO('25), M&A('24) 형식
- Pre-A = 프리시리즈A 브릿지. 엔젤/시드 언급은 Seed.
- 기록이 과대 기재됐고 명시적 기사 근거가 있으면 하향도 보고하라.
- 폐업/영업종료 정황은 note에 기록.
- confidence: high=라운드명 명시 기사 복수 또는 명확한 공신력 기사 1건 /
  medium=단일 간접 근거 / low=확인 불가·인용 불가
- source_url은 위 목록의 링크 중 근거 기사 URL을 선택하라.

다음 JSON 한 개만 출력하라 (다른 텍스트 금지):
{{"new_stage": "...", "confidence": "high|medium|low", "evidence": "날짜+금액+출처 한 문장", "round_quote": "라운드명이 등장하는 기사 원문 문구", "article_date": "근거 기사 날짜(YYYY-MM 또는 YYYY-MM-DD)", "source_url": "...", "note": "특이사항(없으면 빈 문자열)"}}
"""


SCREENING_PROMPT_BATCH = """\
[배치 스크리닝] 당신은 한국 스타트업 투자 DB 관리자다. 아래 여러 회사 각각에 대해,
제공된 뉴스 검색 결과만 근거로 최신 투자 라운드를 확인하고 4분류하라.

각 회사 블록:
{company_blocks}

분류 기준(각 회사 독립 판단):
- changed: DB 기록과 다른 라운드가 명확한 기사 제목으로 확인됨
- unchanged: 최신 확인 가능한 라운드가 DB 기록과 일치
- no_info: 그 회사의 투자 관련 기사가 없음
- ambiguous: 기사 상충·동명 기업 혼동 가능·라운드명 불명확
주의: 업종/서비스명이 일치하는 동일 회사인지 확인. "누적 N억"만으로 단정 금지.

정확히 {n}개 회사에 대해, 아래 형식의 **JSON 배열 하나만** 출력하라 (다른 텍스트 금지):
[{{"id": 1, "verdict": "changed|unchanged|no_info|ambiguous", "new_stage": "변경 시 후보 스테이지({stages}) 아니면 빈 문자열", "note": "한 문장"}}, ...]
"""


def build_screening_prompt(company, query: str) -> str:
    return SCREENING_PROMPT.format(
        name_kr=company.name_kr, name_en=company.name_en or "-",
        industry=company.industry or "-", website=company.website or "-",
        stage=company.stage or "(공란)", query=query, stages=_STAGE_LIST,
    )


def build_verification_prompt(company, hint: str, focus_query: str) -> str:
    return VERIFICATION_PROMPT.format(
        name_kr=company.name_kr, name_en=company.name_en or "-",
        industry=company.industry or "-", website=company.website or "-",
        stage=company.stage or "(공란)", hint=hint or "-",
        focus=focus_query, stages=_STAGE_LIST,
    )


def build_screening_prompt_batch(items: list[dict]) -> str:
    """items: [{id, company, query, search_block}, ...] → 배치 스크리닝 프롬프트."""
    blocks = []
    for it in items:
        c = it["company"]
        blocks.append(
            f"### 회사 {it['id']}: {c.name_kr} ({c.name_en or '-'}) | "
            f"업종: {c.industry or '-'} | 웹사이트: {c.website or '-'} | "
            f"DB기록 스테이지: {c.stage or '(공란)'}\n"
            f'검색어 "{it["query"]}" 뉴스 결과:\n{it["search_block"]}'
        )
    return SCREENING_PROMPT_BATCH.format(
        company_blocks="\n\n".join(blocks), n=len(items), stages=_STAGE_LIST,
    )


def build_screening_prompt_rss(company, query: str, search_block: str) -> str:
    return SCREENING_PROMPT_RSS.format(
        name_kr=company.name_kr, name_en=company.name_en or "-",
        industry=company.industry or "-", website=company.website or "-",
        stage=company.stage or "(공란)", query=query,
        search_block=search_block, stages=_STAGE_LIST,
    )


def build_verification_prompt_rss(company, hint: str, search_block: str,
                                  thevc_block: str = "",
                                  articles_block: str = "") -> str:
    return VERIFICATION_PROMPT_RSS.format(
        name_kr=company.name_kr, name_en=company.name_en or "-",
        industry=company.industry or "-", website=company.website or "-",
        stage=company.stage or "(공란)", hint=hint or "-",
        search_block=search_block, thevc_block=thevc_block or "(확인 안 됨)",
        articles_block=articles_block or "(수집된 기사 없음)",
        stages=_STAGE_LIST,
    )


# ---------------------------------------------------------------- JSON 파싱
def extract_json(text: str) -> dict:
    """응답 텍스트에서 첫 JSON 오브젝트를 관대하게 추출."""
    text = text.strip()
    # ```json ... ``` 펜스 제거
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    start = text.find("{")
    if start == -1:
        raise ValueError(f"JSON 없음: {text[:200]!r}")
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start : i + 1])
    raise ValueError(f"JSON 미완결: {text[:200]!r}")


def extract_json_array(text: str) -> list:
    """응답 텍스트에서 첫 JSON 배열을 관대하게 추출."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    start = text.find("[")
    if start == -1:
        raise ValueError(f"JSON 배열 없음: {text[:200]!r}")
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "[":
            depth += 1
        elif text[i] == "]":
            depth -= 1
            if depth == 0:
                return json.loads(text[start : i + 1])
    raise ValueError(f"JSON 배열 미완결: {text[:200]!r}")


def parse_screening_batch(answer, n: int) -> dict:
    """배치 응답 → {id(int): ScreeningResult}. 파싱 실패 시 빈 dict."""
    try:
        arr = extract_json_array(answer.text)
    except (ValueError, json.JSONDecodeError):
        return {}
    out = {}
    for el in arr:
        if not isinstance(el, dict):
            continue
        try:
            i = int(el.get("id"))
        except (TypeError, ValueError):
            continue
        verdict = str(el.get("verdict", "")).strip().lower()
        if verdict not in VERDICTS:
            verdict = "ambiguous"
        out[i] = ScreeningResult(
            verdict=verdict,
            new_stage=str(el.get("new_stage", "") or "").strip(),
            note=str(el.get("note", "") or "").strip(),
        )
    return out


def parse_screening(answer) -> ScreeningResult:
    data = extract_json(answer.text)
    verdict = str(data.get("verdict", "")).strip().lower()
    if verdict not in VERDICTS:
        verdict = "ambiguous"
    return ScreeningResult(
        verdict=verdict,
        new_stage=str(data.get("new_stage", "") or "").strip(),
        note=str(data.get("note", "") or "").strip(),
        sources=answer.sources,
    )


def parse_verification(answer) -> VerificationResult:
    data = extract_json(answer.text)
    conf = str(data.get("confidence", "low")).strip().lower()
    if conf not in ("high", "medium", "low"):
        conf = "low"
    source_url = str(data.get("source_url", "") or "").strip()
    if not source_url and answer.sources:
        source_url = answer.sources[0]["url"]
    return VerificationResult(
        new_stage=str(data.get("new_stage", "") or "").strip(),
        confidence=conf,
        evidence=str(data.get("evidence", "") or "").strip(),
        source_url=source_url,
        note=str(data.get("note", "") or "").strip(),
        round_quote=str(data.get("round_quote", "") or "").strip(),
        article_date=str(data.get("article_date", "") or "").strip(),
    )
