"""US FORGED — 디캠프 x HAX Hardtech Pre-Program 전용 필터 (공고문 기반).

'큰 엔진 틀, 프로그램은 config 로 교체'의 실증. 공고문(2026-08) 요건을 그대로 코드화:

  대상    : 미국 시장 진출 준비하는 **Pre-Seed~Seed** 딥테크·하드테크
  분야    : Robotics/Automation, Advanced Manufacturing, Energy/Climate,
            Industrial Hardware, Semiconductor/Advanced Materials,
            Sensor/Edge Device, Physical AI, Healthtech Device,
            Manufacturing Process, Aerospace, Quantum (= 우리 하드테크 분야 전부)
  제외    : **Software-only 기업, 일반 소비재, 범용 제품** (기술 차별성 낮음)
  팀      : Lab-scale 이상 프로토타입 · 미국 진출 의지 · 대표/CTO 직접 참여
  선발    : 8~10개사 / 마감 2026-09-06

엔진 매핑: HAX 엔진과 동일 축이되, (1) 스테이지를 Pre-Seed~Seed 로 더 좁히고,
(2) 하드테크 분야가 아니면(=Software-only/소비재) 확정 부적합, (3) 미국 진출은
타겟 국가로 확인(대부분 미상 → 설문 대상)한다. 라벨 튜닝 없음.
"""
from __future__ import annotations

import re

from screening import sectors

# 공고 명시 분야 → 우리 하드테크 분야 키 (전부 hax 트랙)
TARGET_FIELDS = {
    "로보틱스·자동화", "제조·장비", "배터리·에너지", "기후·환경", "하드웨어",
    "반도체", "소재·나노", "센서·IoT", "Physical AI", "의료기기·헬스HW",
    "우주·항공", "양자·퀀텀",
}

# Pre-Seed~Seed 만 (Pre-A·Series·IPO·M&A 제외 — 공고가 Pre-Seed~Seed 로 명시)
_SEED = re.compile(r"Pre-?Seed|프리\s*시드|Seed|시드|Angel|엔젤")
_LATER = re.compile(r"Pre-?A|프리\s*A|Series|시리즈|IPO|M&A|상장|Pre-?IPO")


def stage_status(stage: str) -> str:
    """OK(Pre-Seed~Seed) / LATER(시리즈 등 이탈) / UNKNOWN(미상)."""
    s = stage or ""
    if not s or s == "알 수 없음":
        return "UNKNOWN"
    if _LATER.search(s):
        return "LATER"
    if _SEED.search(s):
        return "OK"
    return "UNKNOWN"


# CB 업종이 명확히 소비재·SW인데 키워드로 하드테크로 오분류되던 문제 → CB 업종을
# '가드'로 사용. 코어(하드웨어/제조/과학·공학/지속가능=CB track hax)는 무조건 인정,
# 아래 조건부 그룹은 소개가 하드웨어 디바이스로 확인될 때만 인정, 그 외 CB(소비재·SW)는
# 키워드가 뭘 잡든 부적합(= 공고가 명시 배제한 일반 소비재·Software-only·범용 제품).
CONDITIONAL_CB = {
    "healthcare", "biotechnology", "bio", "agriculture and farming",
    "navigation and mapping", "mobility", "artificial intelligence",
}
# 소비재·라이프스타일 CB 태그 — 하나라도 있으면 Manufacturing 이 같이 붙어도 거부
# (식품 제조·뷰티 제조는 US FORGED 가 명시 배제한 '일반 소비재'다).
CONSUMER_VETO_CB = {
    "food and beverage", "food & beverage", "beauty/cosmetic", "clothing and apparel",
    "consumer goods", "commerce and shopping", "sports", "community and lifestyle",
    "pet", "kids", "real estate", "travel and tourism", "entertainment/art",
    "publishing", "video", "audio", "media", "events", "game",
}
# 스타트업이 아닌 법인(투자조합·SPC·펀드·해외법인 등) 배제
_NON_STARTUP = re.compile(
    r"투자목적회사|투자조합|벤처투자조합|신기술사업투자조합|사모투자|"
    r"성장투자목적|기업인수목적|\d+\s*호\s*(?:유한회사|유한|투자조합|조합)|"
    r"유한책임회사|유한공사|有限|북경|베이징")


def _cb_hardtech(sector: str, fine_ok: bool) -> tuple[bool, str]:
    """CB 업종 가드 → (하드테크 여부, 판단 근거 업종). 소비재·SW 업종은 승격 불가."""
    toks = [t.strip().lower() for t in re.split(r"[;,/]", sector or "") if t.strip()]
    if not toks:
        return fine_ok, "업종 미상"
    tracks, cond, names = set(), False, []
    for t in toks:
        if t in CONSUMER_VETO_CB:              # 소비재 태그 하나라도 → 즉시 거부
            disp = sectors.CB_GROUP.get(t, (t,))[0]
            return False, disp
        cb = sectors.CB_GROUP.get(t)
        if cb:
            tracks.add(cb[1])
            names.append(cb[0])
            if t in CONDITIONAL_CB:
                cond = True
    if "hax" in tracks:                       # CB=하드웨어/제조/과학공학/지속가능
        return True, "·".join(names) or sector
    if cond and fine_ok:                       # 헬스·바이오·농업·모빌리티 + 디바이스 확인
        return True, "·".join(names)
    return False, "·".join(names) or sector


def eligible(rec: dict) -> dict:
    """공고 요건으로 US FORGED 적합도 판정. CB 업종 가드 + 비스타트업 배제.

    반환: {status, field, hardtech, stage, us, reasons}
      status ∈ '적합(즉시 후보)' / '적합(설문 확인)' / '부적합'
    """
    f = sectors.field_of(rec.get("sector", ""), rec.get("tech", ""),
                         rec.get("desc", ""), rec.get("svc", ""))
    st = stage_status(rec.get("stage", ""))
    target = (rec.get("target") or "")
    us = "미국" in target
    reasons = []

    # 0) 비스타트업 법인(투자조합·SPC·해외법인) 배제
    if _NON_STARTUP.search(rec.get("name_ko", "") + " " + rec.get("name_en", "")):
        return {"status": "부적합", "field": "—", "hardtech": False,
                "stage": st, "us": us,
                "reasons": ["비스타트업 법인(투자조합·SPC·해외법인 등)"]}

    # 1) CB 업종 가드로 하드테크 판정. 분야(fine) 하드테크 확인 여부를 조건부에 사용.
    fine_keys = _fine_hax_keys(rec)
    fine_ok = bool(fine_keys)
    hardtech, cb_basis = _cb_hardtech(rec.get("sector", ""), fine_ok)
    # 표시 분야: 하드테크면 fine 하드테크 키 우선, 없으면 CB 업종
    field = sectors.display(fine_keys[0]) if fine_keys else (
        cb_basis if hardtech else f["field"])

    if not hardtech:
        reasons.append(f"업종 부적합: {cb_basis} — 일반 소비재/Software-only (하드테크 아님)")
        return {"status": "부적합", "field": field, "hardtech": False,
                "stage": st, "us": us, "reasons": reasons}
    # 2) 스테이지 이탈(시리즈A+)이면 확정 부적합
    if st == "LATER":
        reasons.append(f"스테이지 이탈: {rec.get('stage')} — Pre-Seed~Seed 대상")
        return {"status": "부적합", "field": field, "hardtech": True,
                "stage": st, "us": us, "reasons": reasons}
    # 3) 하드테크 + (시드 or 미상). 즉시/설문 갈림
    #    프로토타입(Lab-scale)·미국 의지는 DB로 확인 불가 → 설문. 미국 명시 + 시드면 즉시.
    if us and st == "OK":
        return {"status": "적합(즉시 후보)", "field": field, "hardtech": True,
                "stage": st, "us": True, "reasons": ["하드테크 · 시드 · 미국 명시"]}
    need = []
    if not us:
        need.append("미국 진출 의지")
    if st == "UNKNOWN":
        need.append("스테이지")
    need.append("Lab-scale 프로토타입")
    return {"status": "적합(설문 확인)", "field": field, "hardtech": True,
            "stage": st, "us": us, "reasons": ["설문 확인 필요: " + ", ".join(need)]}


def _fine_hax_keys(rec: dict) -> list[str]:
    """소개·기술로만(회사명·서비스명 제외 — 브랜드명 오탐 방지) 잡힌 하드테크 분야 키."""
    fk = sectors.classify(" ".join((rec.get("desc", ""), rec.get("tech", ""))))
    return [k for k in fk if sectors.track_of(k) == "hax"]


def fine_confirmed(rec: dict) -> bool:
    """분야가 소개·기술 텍스트로 '확정'됐는가(= CB 업종 폴백이 아닌 실체 신호)."""
    return bool(_fine_hax_keys(rec))


def tier(rec: dict, e: dict | None = None) -> str | None:
    """적합 후보의 신뢰도 티어(DB로 확인 가능한 두 축: 스테이지·분야 확정).

    T1 최우선 = 시드 확정 + 분야 확정 / T2 검토 = 둘 중 하나만 / T3 설문 우선 = 둘 다 미확정.
    (더 세게 거르지 않는다 — 진짜 딥테크가 특수 용어라 분야폴백일 수 있어 버리지 않고 티어로.)
    """
    e = e or eligible(rec)
    if not e["status"].startswith("적합"):
        return None
    seed = e["stage"] == "OK"
    fc = fine_confirmed(rec)
    if seed and fc:
        return "T1 최우선"
    if seed or fc:
        return "T2 검토"
    return "T3 설문 우선"


def run() -> list[dict]:
    """전체 DB 에 US FORGED 필터 적용 → 각 rec 에 판정·티어 부착."""
    from screening import gbd_pipeline
    import json
    recs = json.loads((gbd_pipeline.DATA / gbd_pipeline.FACTS)
                      .read_text(encoding="utf-8"))
    out = []
    for r in recs:
        e = eligible(r)
        out.append({**r, "uf_status": e["status"], "uf_field": e["field"],
                    "uf_stage": e["stage"], "uf_us": e["us"],
                    "uf_tier": tier(r, e), "uf_reasons": "; ".join(e["reasons"])})
    return out
