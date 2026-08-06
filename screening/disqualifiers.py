"""v5 확정 탈락 — 하드 디스퀄리파이어 체크리스트.

설계 원칙: **"확실히 아닌 건 확실히 탈락시킨다."**
프로그램이 **절대 waive 하지 않는 기준**(섹터·스테이지·언어·제품·커밋·오너십)에
**확인된 사실**이 걸리면 즉시 `확정 탈락`으로 떨군다(사유를 명시해 운영자가 큐를
비울 수 있게). 단, **확인 안 된** disqualifier 는 추측으로 탈락시키지 않고
`조건부(설문 필요)`로 두고 점수화는 진행한다 — "모르는 것"으로 떨구지 않는다.

v4 의 '스케일업 트랙 안내'(물렁한 유보)를 **철회**한다. 시리즈B+·HAX 시리즈A 는
스케일업 안내가 아니라 **확정 탈락(스테이지 이탈)**이다 — 프리시드~시드 프로그램에
명백히 부적합하므로.

확인 신호(signals) 예: {"english": "no", "product": "no", "commit": "no",
"priced_conflict": "yes"}. DB 대규모 단계에서는 대부분 unknown → 언어·제품·커밋은
조건부로 남고, DB 로 확인 가능한 **스테이지·섹터만 확정 탈락**을 발동한다.
"""
from __future__ import annotations

import re

# 시리즈B 이상(스케일업) — 프리시드~시드 프로그램에 명백 이탈
_SCALEUP = re.compile(r"Series\s*[B-Z]|시리즈\s*[B-Z]|Pre-?IPO|IPO|상장|M&A|Series\s*E")
_SERIES_A = re.compile(r"Series\s*A|시리즈\s*A")
_EARLY = re.compile(r"Seed|시드|Pre-?A|프리\s*A|Angel|엔젤")
# HAX 절대 제외 섹터
_HAX_EXCLUDED = re.compile(
    r"핀테크|fintech|payment|결제|송금|crypto|블록체인|blockchain|nft|"
    r"보안|security|이커머스|e-?commerce|커머스|commerce|"
    r"순수\s*소프트웨어|pure\s*software")


def stage_verdict(track: str, stage: str) -> tuple[str, str]:
    """스테이지 → (verdict, 사유). verdict ∈ FAIL/HUMAN/OK/UNKNOWN."""
    s = stage or ""
    if not s or s == "알 수 없음":
        return "UNKNOWN", "스테이지 미상"
    if _SCALEUP.search(s):
        return "FAIL", f"스테이지 이탈: {s} — 프리시드~시드 프로그램 대상 아님"
    if _SERIES_A.search(s):
        if track == "hax":
            return "FAIL", "스테이지 이탈: 시리즈A — HAX 는 프리시드~시드 전용"
        return "HUMAN", "스테이지 경계: 시리즈A — 500 시드 스위트스폿 상단"
    if _EARLY.search(s):
        return "OK", ""
    return "UNKNOWN", f"스테이지 분류 불가: {s}"


def check(track: str, sector: str, tech: str, desc: str, stage: str,
          signals: dict | None = None) -> dict:
    """확정 탈락 체크리스트. 반환: {fails, humans, conds, stage_unknown}."""
    signals = signals or {}
    blob = " ".join((sector or "", tech or "", desc or "")).lower()
    fails, humans, conds = [], [], []
    stage_unknown = False

    # 1) 스테이지
    sv, sr = stage_verdict(track, stage)
    if sv == "FAIL":
        fails.append(sr)
    elif sv == "HUMAN":
        humans.append(sr)
    elif sv == "UNKNOWN":
        stage_unknown = True

    # 2) 섹터 부적합 (HAX 절대 제외 — 확인 가능한 하드 디스퀄)
    if track == "hax" and _HAX_EXCLUDED.search(blob):
        fails.append("섹터 부적합: HAX 제외 섹터(핀테크·크립토·보안·이커머스·순수SW)")

    # 3) 언어 (영어 전용 프로그램 — 공통)
    eng = signals.get("english", "unknown")
    if eng == "no":
        fails.append("언어: C레벨 영어 불가 확인 — 영어 전용 프로그램")
    elif eng != "yes":
        conds.append("언어: C레벨 영어 미확인 — 설문 필요")

    # 4) 제품 (500=동작 프로토타입 / HAX=개념 이상)
    prod = signals.get("product", "unknown")
    if prod == "no":
        fails.append("제품: 동작 프로토타입/실물 없음 — 개념 단계")

    # 5) 커밋 (500=풀타임·이주)
    if track == "500":
        commit = signals.get("commit", "unknown")
        if commit == "no":
            fails.append("커밋: 풀타임/이주 거부 확인")
        elif commit != "yes":
            conds.append("커밋: 풀타임/이주 미확인 — 설문 필요")

    # 6) HAX 오너십/프라이스드 라운드 충돌
    if track == "hax" and signals.get("priced_conflict") == "yes":
        fails.append("HAX 조건: 프라이스드 라운드/지분 10% 수용 불가")

    return {"fails": fails, "humans": humans, "conds": conds,
            "stage_unknown": stage_unknown}


# 판정 라벨
Z_FAIL = "확정 탈락"
Z_HUMAN = "사람 검토 (경계)"
Z_HOLD = "자료 요청 (스테이지 미상)"
Z_COND = "조건부 통과 → 점수화 (설문 필요)"
Z_SCORE = "점수화 대상"
Z_ROUTE = "IndieBio 라우팅"
Z_RCHECK = "라우팅 사람 확인 (신호 접전)"
Z_OOS = "평가 대상외 (입력 없음)"
Z_SHOLD = "자료 요청 (트랙 특정 불가)"


def decide(track: str, conf: str, sector: str, tech: str, desc: str,
           stage: str, signals: dict | None = None) -> dict:
    """라우팅 결과 + 디스퀄리파이어 → v5 판정."""
    if track == "대상외":
        return {"zone": Z_OOS, "reasons": ["입력 없음"], "band": "—"}
    if track == "판정 보류":
        return {"zone": Z_SHOLD, "reasons": ["신호 약함"], "band": "—"}
    if track == "bio_routing":
        return {"zone": Z_ROUTE, "reasons": ["바이오 치료제"], "band": "—"}
    if conf == "low" and track != "500":
        return {"zone": Z_RCHECK, "reasons": ["라우팅 신호 접전"], "band": "—"}

    from screening.gate_v4 import band_of
    band = band_of(stage)
    c = check(track, sector, tech, desc, stage, signals)
    if c["fails"]:                          # 확정 탈락 (사유 명시)
        return {"zone": Z_FAIL, "reasons": c["fails"], "band": band}
    if c["humans"]:                         # 경계 → 사람 검토
        return {"zone": Z_HUMAN, "reasons": c["humans"], "band": band}
    if c["stage_unknown"]:
        return {"zone": Z_HOLD, "reasons": ["스테이지 미상 — 자료 요청"], "band": band}
    if c["conds"]:                          # 미확인 disqualifier — 점수화는 진행
        return {"zone": Z_COND, "reasons": c["conds"], "band": band}
    return {"zone": Z_SCORE, "reasons": [], "band": band}
