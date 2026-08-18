"""v7 — 500 / HAX 별개 엔진 + 분야 기반 판정 + 사람검토 폐지(경계→메일).

무엇이 바뀌었나 (v7)
--------------------
1. **업종 ≠ 분야** — 라우팅·탈락은 **분야(sectors.field_of, 사업 실체)**가 authoritative.
   업종(CB 그룹)은 거친 prior/폴백. 둘이 어긋나면 신호로 표시.
2. **사람검토 폐지** — 확정 탈락이 아닌 모든 것은 `메일 대상`으로 흡수. 경계·설문
   필요·점수화 가능·라우팅 접전 전부 메일로(붙잡아두지 않는다).
3. **두 엔진 분리 + 크로스 리퍼럴** — 500/HAX config 분리, HAX 탈락이 500 후보면 리퍼럴.

라벨 비의존: 기준은 프로그램 공식 정의(programs.PROGRAMS)에서 나온 것이지 합불 튜닝이
아니다.
"""
from __future__ import annotations

from screening import disqualifiers, router_v4, sectors
from screening.programs import PROGRAMS   # SSOT config

Z_FAIL = disqualifiers.Z_FAIL
Z_MAIL = disqualifiers.Z_MAIL
Z_BIO = disqualifiers.Z_BIO
Z_OOS = disqualifiers.Z_OOS
Z_DUAL = "메일 대상 (양 프로그램 후보)"


def eval_program(track: str, rec: dict, signals: dict | None = None) -> dict:
    """지정 프로그램(500/hax) 엔진 평가. 확정 탈락 아니면 전부 메일 대상."""
    c = disqualifiers.check(track, rec["sector"], rec["tech"], rec["desc"],
                            rec["stage"], signals, rec.get("svc", ""))
    zone = Z_FAIL if c["fails"] else Z_MAIL
    return {"zone": zone, "fails": c["fails"], "conds": c["conds"],
            "stage_unknown": c["stage_unknown"]}


def cross_referral(primary: str, rec: dict) -> str | None:
    """primary(=hax) 에서 탈락해도 500 후보면 '500' 반환. 500 은 섹터 무관 catch-all."""
    if primary != "hax":
        return None
    r = eval_program("500", rec)
    return "500" if r["zone"] != Z_FAIL else None


def decide_v6(rec: dict, signals: dict | None = None) -> dict:
    """라우팅(분야) → 단일/양쪽 평가 → 2갈래 판정 + 메일 유형."""
    rr = router_v4.route(rec["sector"], rec["tech"], rec["desc"],
                         rec.get("name_en", ""), rec.get("svc", ""))
    track = rr["track"]
    base = {"field": rr.get("field"), "cb_group": rr.get("cb_group"),
            "mismatch": rr.get("mismatch", False)}

    if track == "대상외":
        return {**base, "primary": "—", "zone": Z_OOS, "reasons": ["입력 없음"],
                "cross": None, "dual": None, "email": "—"}
    if track == "bio_routing":
        z = Z_BIO
        return {**base, "primary": "bio", "zone": z,
                "reasons": ["바이오 치료제 → IndieBio"], "cross": None,
                "dual": None, "email": disqualifiers.email_hint(z, [], [], False)}

    # 라우팅 접전(저신뢰) → 양쪽 평가, 사람에게 미루지 않는다
    if rr.get("confidence") == "low":
        r5, rh = eval_program("500", rec, signals), eval_program("hax", rec, signals)
        dual = {"500": r5["zone"], "hax": rh["zone"]}
        pass5, passh = r5["zone"] != Z_FAIL, rh["zone"] != Z_FAIL
        if pass5 and passh:
            z = Z_DUAL
            return {**base, "primary": "500/hax", "zone": z,
                    "reasons": ["양 프로그램 후보 — 담당자 프로그램 선택"],
                    "cross": None, "dual": dual,
                    "email": disqualifiers.email_hint(Z_MAIL, [], [], False)}
        if pass5 or passh:
            pri = "500" if pass5 else "hax"
            r = r5 if pass5 else rh
            z = Z_MAIL
            return {**base, "primary": pri, "zone": z,
                    "reasons": r["conds"] or ["점수화 대상"], "cross": None,
                    "dual": dual,
                    "email": disqualifiers.email_hint(
                        z, r["fails"], r["conds"], r["stage_unknown"])}
        return {**base, "primary": "양 트랙", "zone": Z_FAIL,
                "reasons": r5["fails"] + rh["fails"] or ["양 프로그램 부적합"],
                "cross": None, "dual": dual, "email": "자가진단·보완 안내"}

    # 확신 라우팅 → 단일 평가 (+ HAX 탈락 시 500 리퍼럴)
    r = eval_program(track, rec, signals)
    cross = cross_referral(track, rec) if r["zone"] == Z_FAIL else None
    reasons = r["fails"] if r["zone"] == Z_FAIL else (r["conds"] or ["점수화 대상"])
    return {**base, "primary": track, "zone": r["zone"], "reasons": reasons,
            "cross": cross, "dual": None,
            "email": disqualifiers.email_hint(
                r["zone"], r["fails"], r["conds"], r["stage_unknown"])}
