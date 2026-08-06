"""v4 게이트 — 스테이지 뉘앙스 + 라우팅 신뢰도 반영.

v1~v3 게이트의 문제: 스테이지가 시리즈A 이상이면 500 은 전부 `사람 검토`, HAX 는
전부 `탈락`으로 뭉뚱그렸다. 그래서 '경계(시리즈A — 아직 시드 인접)'와 '명백히 늦음
(시리즈B+ — 스케일업 단계)'이 같은 버킷에 섞여 사람 검토가 과다했다.

v4 의 변경:
  1. **스테이지 3분할**
       프리시드~시드 초기  → 프로그램 타깃, 점수화
       프리A~시리즈A       → 경계 → `사람 검토`(아직 지원 여지)
       시리즈B 이상/IPO/M&A → 명백한 스테이지 이탈 → `스케일업 트랙 안내`
                              (사람 검토가 아니라 별도 조치 — 큐를 비운다)
  2. **라우팅 불안정 반영** — router_v4 가 `low` 신뢰로 라우팅했으면 게이트도
     `라우팅 사람 확인`으로 표시(조용한 오분류가 점수까지 가지 않게).
  3. **입력 상태 3분할** — 대상외(입력 없음) / 판정 보류(신호 약함) / 정상.

라벨 비의존: 스테이지 컷은 프로그램 공식 대상 단계(500·HAX 모두 프리시드~시드)에서
나온 것이지 합불 분포에서 나온 것이 아니다.
"""
from __future__ import annotations

import re

from screening import rules

# 스테이지 문자열 → 밴드 3분류
_SCALEUP = re.compile(r"Series\s*[B-Z]|시리즈\s*[B-Z]|Pre-?IPO|IPO|상장|M&A|Series\s*E")
_BORDER = re.compile(r"Series\s*A|시리즈\s*A|Pre-?A|프리\s*A")
_EARLY = re.compile(r"Seed|시드|Angel|엔젤")


def band_of(stage: str) -> str:
    s = stage or ""
    if not s or s in ("알 수 없음",):
        return "미상"
    if _SCALEUP.search(s):
        return "스케일업"            # 시리즈B+ — 명백한 이탈
    if re.search(r"Series\s*A|시리즈\s*A", s):
        return "A 이후"              # 시리즈A — 경계
    if re.search(r"Pre-?A|프리\s*A", s):
        return "시드 후기"
    if _EARLY.search(s):
        return "시드 초기"
    return "미상"


ZONE = {
    "SCORE": "점수화 대상",
    "HUMAN": "사람 검토 (경계 스테이지/보류)",
    "SCALEUP": "스케일업 트랙 안내 (스테이지 명백 이탈)",
    "FAIL": "게이트 탈락",
    "ROUTE": "IndieBio 라우팅",
    "RCHECK": "라우팅 사람 확인 (신호 접전)",
    "HOLD": "자료 요청 (스테이지 미상)",
    "OOS": "평가 대상외 (입력 없음)",
    "SHOLD": "자료 요청 (트랙 특정 불가)",
}


def gate(route_result: dict, stage: str) -> dict:
    """router_v4 결과 + 스테이지 → v4 판정."""
    track = route_result["track"]
    conf = route_result.get("confidence")
    if track == "대상외":
        return {"zone": ZONE["OOS"], "band": "—", "track": track}
    if track == "판정 보류":
        return {"zone": ZONE["SHOLD"], "band": "—", "track": track}
    if track == "bio_routing":
        return {"zone": ZONE["ROUTE"], "band": "—", "track": track}

    band = band_of(stage)
    # 라우팅이 불안정하면 점수 이전에 사람 확인 (조용한 오분류 차단)
    if conf == "low" and track != "500":
        z = ZONE["RCHECK"]
    elif band == "미상":
        z = ZONE["HOLD"]
    elif band == "스케일업":
        # HAX·500 모두 시리즈B+ 는 프로그램 대상이 아님 → 스케일업 안내(별도 큐)
        z = ZONE["SCALEUP"]
    elif band == "A 이후":
        # 시리즈A = 경계. HAX 는 프라이스드 라운드 충돌 소지 → 사람 검토(탈락 아님)
        z = ZONE["HUMAN"]
    else:
        z = ZONE["SCORE"]
    return {"zone": z, "band": band, "track": track}
