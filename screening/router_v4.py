"""라우터 — **분야(field) authoritative**, 업종(CB 그룹)은 폴백/신호.

왜 분야 우선 (v7)
-----------------
업종(CB 그룹)은 거칠다: "Hardware" 그룹에 로보틱스·반도체(하드테크)와 소매기술·화상
회의(SW성)가 섞이고, "Financial Services" 는 결제·대출·보험을 뭉뚱그린다. 그래서
라우팅·탈락은 **분야(sectors.field_of — 소개·기술로 세밀 판정)**를 기준으로 한다.
업종은 소개가 비었을 때의 prior/폴백일 뿐이고, 업종≠분야면 그 자체가 신호다.

- 분야가 단일 트랙으로 잡히면 그 트랙이 authoritative(소개가 SW 단어여도 분야=로봇이면 HAX).
- 분야가 접전(두 트랙)이면 업종 prior 로 깨고, 그래도 애매하면 저신뢰 → 양쪽 평가.
- 분야가 비면 업종(CB 그룹) 트랙으로 폴백.
- 치료제(bio)는 분야에서 확인될 때만 IndieBio 라우팅(디지털·진단·기기·SW 는 차단).

라벨 비의존. 트랙 매핑은 프로그램 정의(sectors)에서 나온다.
"""
from __future__ import annotations

from screening import sectors


def route(sector: str, tech: str, desc: str, name_en: str = "",
          svc: str = "") -> dict:
    """분야 기반 라우팅. 반환: track, confidence, field, cb_group, mismatch, scores, reason."""
    if not any(x and x.strip() for x in (sector, tech, desc, name_en, svc)):
        return {"track": "대상외", "confidence": "none", "field": None,
                "cb_group": None, "mismatch": False, "scores": {},
                "reason": "입력 없음 (업종·기술·소개 공란)"}

    f = sectors.field_of(sector, tech, desc, " ".join((svc or "", name_en or "")))
    fine_keys = f["fine_keys"]
    field, ftrack = f["field"], f["field_track"]
    cb_disp, cb_track = f["cb_group"], f["cb_track"]
    scores = sectors.track_scores(" ".join((desc or "", tech or "", svc or "")))

    def out(track, conf, why):
        return {"track": track, "confidence": conf, "field": field,
                "cb_group": cb_disp, "mismatch": f["mismatch"], "scores": scores,
                "reason": f"[분야:{field} / 업종:{cb_disp or '—'}] {why}"}

    # 1) 치료제 → IndieBio (분야 확인)
    if f["bio"]:
        return out("bio_routing", "high", "치료제 확인 → IndieBio")

    # 2) 분야(세밀)가 단일 트랙 → authoritative
    fine_tracks = {sectors.track_of(k) for k in fine_keys if k != "바이오치료제"}
    fine_tracks.discard(None)
    if fine_tracks == {"hax"}:
        return out("hax", "high", "분야=하드테크 확정")
    if fine_tracks == {"500"}:
        return out("500", "high", "분야=SW/서비스 확정")

    # 3) 분야 접전(두 트랙) → 업종 prior 로 시도, 저신뢰(양쪽 평가로 해소)
    if len(fine_tracks) >= 2:
        track = cb_track or "500"
        return out(track, "low", "분야 접전(HW·SW 혼재) → 저신뢰, 양쪽 평가")

    # 4) 분야 비었음 → 업종(CB 그룹) 트랙 폴백
    if cb_track:
        conf = "high"
        why = "소개 신호 약함 → 업종 prior 사용"
        if f["mismatch"]:
            why = "업종≠분야 불일치"
        return out(cb_track, conf, why)

    return {"track": "판정 보류", "confidence": "low", "field": field,
            "cb_group": cb_disp, "mismatch": False, "scores": scores,
            "reason": "신호 약함 — 업종·소개로 트랙 특정 불가(설문)"}
