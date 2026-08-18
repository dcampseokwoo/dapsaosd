"""라우터 — **섹터 최우선** 다신호 가중 + 자기불확실성 플래그.

왜 섹터 최우선(v4.2)
--------------------
미국(500·HAX)은 VC 성격상 섹터로 먼저 가른다(일본은 기업 우선). v4 초판은 사업
소개(desc)를 1순위로 뒀는데, 이를 뒤집는다: **업종(sector) 필드를 최상위 가중**으로
올리고, 소개·기술은 보정 신호로 쓴다. 섹터 판정은 sectors.py 의 표준 분류 축을
공유한다(자유텍스트를 표준키로 정규화 → 같은 업종은 항상 같은 트랙).

가중치: 섹터 1.5 > 소개 1.0 > 기술 0.7 > 영문명 0.4
  - 트랙별 점수 = Σ (각 필드에서 매칭된 표준 섹터 수 × 필드 가중치)
  - 1·2위 점수 차 < CONF_MARGIN → '라우팅 불안정'(사람 확인). 조용한 오분류 방지.

바이오 치료제(→ IndieBio)는 sectors.BIO_BLOCK 으로 디지털·진단·기기·SW 오분류를 차단.

이 층은 라벨을 보지 않는다. 트랙 매핑은 프로그램 정의(sectors.TAXONOMY)에서 나온다.
"""
from __future__ import annotations

import re

from screening import sectors

# 필드 가중치 — 섹터 최우선
W_SECTOR, W_DESC, W_TECH, W_NAME = 1.5, 1.0, 0.7, 0.4
CONF_MARGIN = 2.0   # 1·2위 점수 차가 이 값 미만이면 저신뢰(라우팅 불안정)

# 트랙 표시 키 (route 반환의 scores 키). 내부 트랙 'bio' → 'bio_routing'.
_TRACK_OUT = {"bio": "bio_routing", "hax": "hax", "500": "500"}


def route(sector: str, tech: str, desc: str, name_en: str = "") -> dict:
    """섹터 최우선 다신호 라우팅. 반환: track, confidence, scores, reason, sector(표준키)."""
    sector_s, tech_s, desc_s = sector or "", tech or "", desc or ""
    name_s = name_en or ""
    if not (sector_s or tech_s or desc_s or name_s).strip():
        return {"track": "대상외", "confidence": "none", "scores": {},
                "sector": None, "reason": "입력 없음 (업종·기술·소개 공란)"}

    # 필드별 트랙 점수(섹터 최우선 가중 합산) — 근거·폴백용
    agg = {"hax": 0.0, "500": 0.0, "bio": 0.0}
    for text, w in ((sector_s, W_SECTOR), (desc_s, W_DESC),
                    (tech_s, W_TECH), (name_s, W_NAME)):
        ts = sectors.track_scores(text)
        for k in agg:
            agg[k] += ts[k] * w

    blob = " ".join((sector_s, tech_s, desc_s)).lower()
    # 바이오 섹터 가산(치료제 문맥일 때만) / 디지털·진단·기기·SW 면 바이오 차단
    if sectors._BIO_SECTOR.search(sector_s.lower()) and not sectors.BIO_BLOCK.search(blob):
        agg["bio"] += 1.5
    if sectors.BIO_BLOCK.search(" ".join((tech_s, desc_s)).lower()):
        agg["bio"] = 0.0

    scores = {"bio_routing": round(agg["bio"], 2), "hax": round(agg["hax"], 2),
              "500": round(agg["500"], 2)}
    prim = sectors.primary(sector_s) or sectors.primary(desc_s) or sectors.primary(tech_s)

    # ── STEP 1: 섹터 필드가 단일 트랙으로 확정되면 그것이 authoritative(진짜 섹터 우선)
    sec_tracks = {sectors.track_of(k) for k in sectors.classify(sector_s)}
    if "bio" in sec_tracks and sectors.BIO_BLOCK.search(blob):
        sec_tracks.discard("bio")            # 디지털·진단·기기는 바이오 아님
    if len(sec_tracks) == 1:
        tr = sec_tracks.pop()
        track = _TRACK_OUT[tr]
        reason = f"[업종 확정: {sectors.display(prim)}] → {track} (섹터 우선)"
        return {"track": track, "confidence": "high", "scores": scores,
                "sector": prim, "reason": reason}

    # ── STEP 2: 섹터 필드가 공란/모호 → 소개·기술 가중으로 판정(폴백)
    ranked = sorted(scores.items(), key=lambda x: -x[1])
    (t1, s1), (t2, s2) = ranked[0], ranked[1]

    if s1 == 0:
        return {"track": "판정 보류", "confidence": "low", "scores": scores,
                "sector": prim,
                "reason": "신호 약함 — 업종·소개로 트랙 특정 불가(자료 요청)"}

    track = t1                                # bio_routing/hax/500 (키 그대로)
    conf = "high" if s1 - s2 >= CONF_MARGIN else "low"

    reason = (f"[소개·기술 폴백] {track} (bio {scores['bio_routing']} / "
              f"hax {scores['hax']} / 500 {scores['500']})")
    if prim:
        reason = f"[{sectors.display(prim)}] " + reason
    if conf == "low":
        reason += " — 신호 접전, 라우팅 불안정(사람 확인 권장)"

    return {"track": track, "confidence": conf, "scores": scores,
            "sector": prim, "reason": reason}
