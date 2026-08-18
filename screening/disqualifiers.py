"""확정 탈락 — 하드 디스퀄리파이어 체크리스트 (**config 주도**).

설계 원칙: **"확실히 아닌 건 확실히 탈락시킨다."**
프로그램이 **절대 waive 하지 않는 기준**(섹터·스테이지·언어·제품·커밋·오너십)에
**확인된 사실**이 걸리면 즉시 `확정 탈락`으로 떨군다(사유 명시). 단, **확인 안 된**
disqualifier 는 추측으로 탈락시키지 않고 `조건부(설문 필요)`로 두고 점수화는 진행한다.

config 주도(v5.1)
------------------
스테이지 정책·제외 섹터·지원 요건을 코드에 하드코딩하지 않고 **programs.PROGRAMS**
설정에서 읽는다. 프로그램이 바뀌면 programs.py 만 고치면 이 로직이 그대로 따라간다.
섹터 판정은 sectors.py 표준 분류 축을 공유한다(자유텍스트 → 표준키).

확인 신호(signals) 예: {"english":"no","product":"no","commit":"no",
"priced_conflict":"yes"}. DB 대규모 단계에선 대부분 unknown → 언어·제품·커밋은
조건부로 남고, DB 로 확인 가능한 **스테이지·섹터만 확정 탈락**을 발동한다.
"""
from __future__ import annotations

import re

from screening import programs, sectors

# 스테이지 밴드 인식(프로그램 공통) — 정책(밴드→판정)은 config 가 정한다.
_SCALEUP = re.compile(r"Series\s*[B-Z]|시리즈\s*[B-Z]|Pre-?IPO|IPO|상장|M&A")
_SERIES_A = re.compile(r"Series\s*A|시리즈\s*A")
_EARLY = re.compile(r"Seed|시드|Pre-?A|프리\s*A|Angel|엔젤")


def stage_band(stage: str) -> str:
    """스테이지 문자열 → 밴드: scaleup / series_a / early / unknown."""
    s = stage or ""
    if not s or s == "알 수 없음":
        return "unknown"
    if _SCALEUP.search(s):
        return "scaleup"
    if _SERIES_A.search(s):
        return "series_a"
    if _EARLY.search(s):
        return "early"
    return "unknown"


def _stage_reason(track: str, band: str, stage: str) -> str:
    if band == "scaleup":
        return f"스테이지 이탈: {stage} — 프리시드~시드 프로그램 대상 아님"
    if band == "series_a":
        if track == "hax":
            return "스테이지 이탈: 시리즈A — HAX 는 프리시드~시드 전용"
        return "스테이지 경계: 시리즈A — 500 시드 스위트스폿 상단"
    return f"스테이지 분류 불가: {stage}"


def stage_verdict(track: str, stage: str) -> tuple[str, str]:
    """스테이지 → (verdict, 사유). verdict ∈ FAIL/HUMAN/OK/UNKNOWN. (config 정책 반영)"""
    band = stage_band(stage)
    if band == "unknown":
        return "UNKNOWN", "스테이지 미상"
    cfg = programs.get(track)
    policy = (cfg or {}).get("stage_policy", {})
    verdict = policy.get(band, "OK")
    if verdict == "OK":
        return "OK", ""
    return verdict, _stage_reason(track, band, stage)


def _excluded_sector_hit(track: str, blob: str) -> str | None:
    """blob 에 프로그램 제외 섹터가 있고, 그 프로그램의 우선(하드테크) 섹터는 없으면
    제외 섹터 표시명 반환. (하드웨어 문맥에 SW 단어가 섞인 오탈락 방지.)"""
    excl = set(programs.excluded_sectors(track))
    if not excl:
        return None
    hits = set(sectors.classify(blob))
    bad = hits & excl
    if not bad:
        return None
    # 같은 텍스트에 이 프로그램의 우선(target) 섹터도 잡히면 확정 탈락 보류(경계로)
    good = hits & set(programs.target_sectors(track))
    if good:
        return None
    return sectors.display(sorted(bad)[0])


def check(track: str, sector: str, tech: str, desc: str, stage: str,
          signals: dict | None = None) -> dict:
    """확정 탈락 체크리스트(config 주도). 반환: {fails, humans, conds, stage_unknown}."""
    signals = signals or {}
    cfg = programs.get(track) or {}
    reqs = cfg.get("requirements", {})
    blob = " ".join((sector or "", tech or "", desc or "")).lower()
    fails, humans, conds = [], [], []
    stage_unknown = False

    # 1) 스테이지 (config stage_policy)
    sv, sr = stage_verdict(track, stage)
    if sv == "FAIL":
        fails.append(sr)
    elif sv == "HUMAN":
        humans.append(sr)
    elif sv == "UNKNOWN":
        stage_unknown = True

    # 2) 섹터 부적합 (config excluded_sectors, 표준키 기준)
    excl_hit = _excluded_sector_hit(track, blob)
    if excl_hit:
        excl_list = "·".join(sectors.display(k) if k in sectors.TAXONOMY else k
                             for k in programs.excluded_sectors(track))
        fails.append(f"섹터 부적합: {cfg.get('name', track)} 제외 섹터"
                     f"({excl_list}) — 감지: {excl_hit}")

    # 3) 언어 (영어 전용 프로그램)
    if reqs.get("language"):
        eng = signals.get("english", "unknown")
        if eng == "no":
            fails.append("언어: C레벨 영어 불가 확인 — 영어 전용 프로그램")
        elif eng != "yes":
            conds.append("언어: C레벨 영어 미확인 — 설문 필요")

    # 4) 제품 (동작 프로토타입/실물)
    if reqs.get("product"):
        if signals.get("product", "unknown") == "no":
            fails.append("제품: 동작 프로토타입/실물 없음 — 개념 단계")

    # 5) 커밋 (풀타임·이주)
    if reqs.get("commit"):
        commit = signals.get("commit", "unknown")
        if commit == "no":
            fails.append("커밋: 풀타임/이주 거부 확인")
        elif commit != "yes":
            conds.append("커밋: 풀타임/이주 미확인 — 설문 필요")

    # 6) 오너십/프라이스드 라운드 충돌 (HAX: 캡 없는 SAFE·지분10%)
    if reqs.get("priced_conflict"):
        if signals.get("priced_conflict") == "yes":
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
    """라우팅 결과 + 디스퀄리파이어 → 판정."""
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
