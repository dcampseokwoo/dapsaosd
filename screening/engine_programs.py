"""v6 — 500 / HAX 를 명시적 별개 엔진으로 분리 + 크로스 리퍼럴 + 양쪽 평가.

왜 v6
-----
500 Global 과 HAX(SOSV)는 축·게이트·스테이지 정책이 전혀 다른 **별개 프로그램**이다.
v5 까지는 한 파이프라인이 트랙만 갈라 처리했다. v6 는 이를 명시적으로 재설계한다:

1. **두 엔진 config 분리(PROGRAMS)** — 각 프로그램의 대상·형태·4축·스테이지 정책·
   확정 탈락 기준을 한 곳에 선언. 출력도 트랙별로 분리한다.
2. **애매하면 양쪽 다 평가(dual-run)** — 라우팅 신호가 접전이면 사람에게 미루지 않고
   500·HAX 두 엔진에 모두 통과시켜 두 판정을 나란히 낸다. 한쪽만 통과하면 자동 해소.
3. **크로스 프로그램 리퍼럴** — 한 프로그램에서 탈락해도 다른 프로그램 후보면
   '타 프로그램 후보'로 넘긴다(막다른 탈락을 라우팅 정보로). 예: HAX 제외 섹터로
   탈락한 SW → 500 후보. 500 은 섹터 무관이므로 catch-all 역할.

라벨 비의존: 기준은 전부 프로그램 공식 정의에서 나온 것이지 합불 분포 튜닝이 아니다.
"""
from __future__ import annotations

from screening import disqualifiers, router_v4
from screening.programs import PROGRAMS   # SSOT config — 프로그램 기준은 programs.py 한 곳

Z_DUAL = "양 프로그램 후보 (500·HAX 점수화 대상)"


# ---------------------------------------------------------------- 단일 프로그램 평가
def eval_program(track: str, rec: dict, signals: dict | None = None) -> dict:
    """지정 프로그램(500/hax) 엔진으로만 평가. disqualifiers.check 재사용."""
    c = disqualifiers.check(track, rec["sector"], rec["tech"], rec["desc"],
                            rec["stage"], signals)
    if c["fails"]:
        zone = disqualifiers.Z_FAIL
    elif c["humans"]:
        zone = disqualifiers.Z_HUMAN
    elif c["stage_unknown"]:
        zone = disqualifiers.Z_HOLD
    elif c["conds"]:
        zone = disqualifiers.Z_COND
    else:
        zone = disqualifiers.Z_SCORE
    return {"zone": zone, "fails": c["fails"], "humans": c["humans"],
            "conds": c["conds"]}


# ---------------------------------------------------------------- 크로스 리퍼럴
def cross_referral(primary: str, fails: list[str], rec: dict) -> str | None:
    """primary 에서 탈락했지만 다른 프로그램 후보인지 판단 → 후보 트랙 or None.

    핵심 케이스: HAX 제외 섹터(SW)로 탈락 → 500 은 섹터 무관이라 후보.
    HAX 스테이지(시리즈A)로 탈락 → 500 은 시리즈A 를 경계로 받으므로 후보.
    (500 의 탈락 사유[시리즈B+·영어·제품]는 HAX 도 공유하므로 크로스 없음.)
    """
    if primary != "hax":
        return None
    other = "500"
    reason_txt = " ".join(fails)
    # HAX 탈락이 '섹터' 또는 '스테이지(시리즈A)' 때문이면 500 재평가
    if "섹터 부적합" in reason_txt or "시리즈A" in reason_txt:
        r = eval_program(other, rec)
        if r["zone"] != disqualifiers.Z_FAIL:
            return other
    return None


# ---------------------------------------------------------------- v6 종합 판정
def decide_v6(rec: dict, signals: dict | None = None) -> dict:
    """라우팅 → (확신) 단일 평가 + 크로스 리퍼럴 / (접전) 양쪽 평가."""
    rr = router_v4.route(rec["sector"], rec["tech"], rec["desc"], rec["name_en"])
    track, conf = rr["track"], rr.get("confidence")

    if track == "대상외":
        return {"primary": "—", "zone": disqualifiers.Z_OOS,
                "reasons": ["입력 없음"], "cross": None, "dual": None}
    if track == "판정 보류":
        return {"primary": "—", "zone": disqualifiers.Z_SHOLD,
                "reasons": ["신호 약함"], "cross": None, "dual": None}
    if track == "bio_routing":
        return {"primary": "bio", "zone": disqualifiers.Z_ROUTE,
                "reasons": ["바이오 치료제 → IndieBio"], "cross": None, "dual": None}

    # 라우팅 접전 → 양쪽 엔진 다 평가(사람에게 미루지 않고 자동 해소 시도)
    if conf == "low":
        r5, rh = eval_program("500", rec, signals), eval_program("hax", rec, signals)
        pass5 = r5["zone"] not in (disqualifiers.Z_FAIL,)
        passh = rh["zone"] not in (disqualifiers.Z_FAIL,)
        dual = {"500": r5["zone"], "hax": rh["zone"]}
        if pass5 and not passh:
            return {"primary": "500", "zone": r5["zone"],
                    "reasons": r5["fails"] + r5["humans"] + r5["conds"],
                    "cross": None, "dual": dual, "note": "라우팅 접전 → 양쪽 평가로 500 확정"}
        if passh and not pass5:
            return {"primary": "hax", "zone": rh["zone"],
                    "reasons": rh["fails"] + rh["humans"] + rh["conds"],
                    "cross": None, "dual": dual, "note": "라우팅 접전 → 양쪽 평가로 HAX 확정"}
        if not pass5 and not passh:
            return {"primary": "양 트랙", "zone": disqualifiers.Z_FAIL,
                    "reasons": ["500·HAX 양 프로그램 모두 부적합"],
                    "cross": None, "dual": dual}
        # 둘 다 통과 가능 → 부담이 아니라 '양 프로그램 후보'(긍정) — 점수화 대상
        return {"primary": "500/hax", "zone": Z_DUAL,
                "reasons": ["양 프로그램 모두 점수화 대상 — 담당자가 프로그램 선택"],
                "cross": None, "dual": dual}

    # 확신 라우팅 → 단일 평가 + (탈락 시) 크로스 리퍼럴
    r = eval_program(track, rec, signals)
    cross = None
    if r["zone"] == disqualifiers.Z_FAIL:
        cross = cross_referral(track, r["fails"], rec)
    return {"primary": track, "zone": r["zone"],
            "reasons": r["fails"] + r["humans"] + r["conds"],
            "cross": cross, "dual": None,
            "band": disqualifiers.decide(track, conf, rec["sector"], rec["tech"],
                                         rec["desc"], rec["stage"], signals)["band"]}
