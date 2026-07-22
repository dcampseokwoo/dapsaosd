"""2단계 검증용 검색 쿼리 생성 + 후보 URL 수집 (Google Search grounding 경유)."""
from __future__ import annotations

import config


def screening_query(company) -> str:
    """1단계 쿼리: "{국문 회사명} 투자 유치" (짧은/일반명사성 이름은 업종 키워드 추가)."""
    name = company.name_kr.strip()
    q = f'"{name}" 투자 유치'
    if len(name) <= config.GENERIC_NAME_MAX_LEN and company.industry:
        kw = str(company.industry).split(",")[0].split("/")[0].strip()
        if kw:
            q = f'"{name}" {kw} 투자 유치'
    return q


def verification_queries(company, hint_stage: str = "") -> list[str]:
    """2단계 교차 확인 쿼리 2-3개 (grounding 모드용, 신뢰 소스 중심)."""
    name = company.name_kr.strip()
    queries = [
        f'"{name}" 투자 유치 시리즈 {hint_stage}'.strip(),
        f'"{name}" site:thevc.kr OR site:platum.kr OR site:wowtale.net OR site:venturesquare.net',
    ]
    if company.name_en:
        queries.append(f'"{company.name_en.strip()}" funding round Korea')
    return queries[:3]


def verification_queries_rss(company, bare_terminal: bool = False) -> list[str]:
    """2단계 교차 확인 쿼리 (구글 뉴스 RSS 모드용)."""
    name = company.name_kr.strip()
    queries = [f'"{name}" 투자 유치', f'"{name}" 시리즈 투자']
    if bare_terminal:
        # 연도 없는 M&A/IPO → 인수·상장 연도 확인이 목적
        queries.insert(0, f'"{name}" 인수 OR 상장')
    return queries[:3]
