"""확정 탈락 게이트 (config 주도, **사람검토 폐지**).

설계 원칙: **"확실히 아닌 건 확실히 탈락. 나머지는 붙잡지 말고 메일을 보낸다."**
- 프로그램이 절대 waive 안 하는 기준(스테이지 이탈·분야 부적합·언어·제품·오너십)에
  **확인된 사실**이 걸리면 → `확정 탈락`(사유 명시).
- 그 외는 전부 → `메일 대상`. 애매한 경계·설문 필요·점수화 가능 모두 메일로 흡수한다
  (사람검토 버킷을 없앤다 — 애매하다고 붙잡아두면 아무 일도 안 일어난다).

업종 ≠ 분야: 탈락 판정은 **분야(sectors.field_of)** 기준이다. 업종(CB 그룹)은 거칠어서
그것만으로 떨구지 않는다. HAX 제외는 분야가 제외축이고 하드테크 분야가 동반되지
않을 때만 발동(하드웨어에 SW 단어 섞인 오탈락 방지).

확인 신호(signals): {"english":"no","product":"no","priced_conflict":"yes"} 등.
DB 대규모 단계엔 대부분 unknown → 언어·제품은 조건부(메일 설문)로 남고, DB 로 확인
가능한 **스테이지·분야만 확정 탈락**을 발동한다.
"""
from __future__ import annotations

import re

from screening import programs, sectors

# 스테이지 밴드 인식(공통) — 정책(밴드→판정)은 config.
_SCALEUP = re.compile(r"Series\s*[B-Z]|시리즈\s*[B-Z]|Pre-?IPO|IPO|상장|M&A")
_SERIES_A = re.compile(r"Series\s*A|시리즈\s*A")
_EARLY = re.compile(r"Seed|시드|Pre-?A|프리\s*A|Angel|엔젤")

# 판정 라벨 (2갈래 + 부수)
Z_FAIL = "확정 탈락"
Z_MAIL = "메일 대상"
Z_BIO = "IndieBio 리퍼럴"
Z_OOS = "평가 대상외 (입력 없음)"


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


def stage_verdict(track: str, stage: str) -> tuple[str, str]:
    """스테이지 → (verdict, 사유). verdict ∈ FAIL/OK/UNKNOWN (config stage_policy)."""
    band = stage_band(stage)
    if band == "unknown":
        return "UNKNOWN", "스테이지 미상"
    cfg = programs.get(track) or {}
    verdict = cfg.get("stage_policy", {}).get(band, "OK")
    if verdict == "FAIL":
        if band == "scaleup":
            return "FAIL", f"스테이지 이탈: {stage} — 프리시드~시드 프로그램 대상 아님"
        return "FAIL", f"스테이지 이탈: {stage} — {cfg.get('name', track)} 는 프리시드~시드 전용"
    return "OK", ""


def _excluded_field_hit(track: str, sector: str, tech: str, desc: str,
                        svc: str = "") -> str | None:
    """분야가 프로그램 제외축이고 우선(하드테크) 분야가 동반되지 않으면 제외 분야명."""
    excl = set(programs.excluded_sectors(track))
    if not excl:
        return None
    fine = set(sectors.classify(" ".join((desc or "", tech or "", svc or "",
                                          sector or ""))))
    bad = fine & excl
    if not bad:
        return None
    good = fine & set(programs.target_sectors(track))
    if good:
        return None
    return sectors.display(sorted(bad)[0])


def check(track: str, sector: str, tech: str, desc: str, stage: str,
          signals: dict | None = None, svc: str = "") -> dict:
    """확정 탈락 체크리스트(config·분야 주도). 반환: {fails, conds, stage_unknown}."""
    signals = signals or {}
    cfg = programs.get(track) or {}
    reqs = cfg.get("requirements", {})
    fails, conds = [], []
    stage_unknown = False

    # 1) 스테이지 (config stage_policy)
    sv, sr = stage_verdict(track, stage)
    if sv == "FAIL":
        fails.append(sr)
    elif sv == "UNKNOWN":
        stage_unknown = True

    # 2) 분야 부적합 (config excluded_sectors, 분야 기준)
    hit = _excluded_field_hit(track, sector, tech, desc, svc)
    if hit:
        excl_list = "·".join(sectors.display(k) if k in sectors.TAXONOMY else k
                             for k in programs.excluded_sectors(track))
        fails.append(f"분야 부적합: {cfg.get('name', track)} 제외 분야"
                     f"({excl_list}) — 감지: {hit}")

    # 3) 언어 (영어 전용) — 확인된 불가만 탈락, 미확인은 설문(메일)
    if reqs.get("language"):
        eng = signals.get("english", "unknown")
        if eng == "no":
            fails.append("언어: C레벨 영어 불가 확인 — 영어 전용 프로그램")
        elif eng != "yes":
            conds.append("언어: C레벨 영어 미확인 — 설문 필요")

    # 4) 제품 (동작 프로토타입/실물) — 확인된 없음만 탈락
    if reqs.get("product"):
        if signals.get("product", "unknown") == "no":
            fails.append("제품: 동작 프로토타입/실물 없음 확인 — 개념 단계")

    # 5) 커밋 (풀타임·이주) — 확인된 거부만 탈락, 미확인은 설문
    if reqs.get("commit"):
        commit = signals.get("commit", "unknown")
        if commit == "no":
            fails.append("커밋: 풀타임/이주 거부 확인")
        elif commit != "yes":
            conds.append("커밋: 풀타임/이주 미확인 — 설문 필요")

    # 6) HAX 오너십/프라이스드 라운드 충돌
    if reqs.get("priced_conflict"):
        if signals.get("priced_conflict") == "yes":
            fails.append("HAX 조건: 프라이스드 라운드/지분 10% 수용 불가")

    return {"fails": fails, "conds": conds, "stage_unknown": stage_unknown}


def email_hint(zone: str, fails: list[str], conds: list[str],
               stage_unknown: bool) -> str:
    """판정 → 메일 유형(다음 단계 자동 메일용)."""
    if zone == Z_FAIL:
        return "자가진단·보완 안내"
    if zone == Z_BIO:
        return "IndieBio 안내"
    if stage_unknown or conds:
        return "설문·자료 요청"
    return "내부 검토 → 지원 안내"
