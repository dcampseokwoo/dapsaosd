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


def eligible(rec: dict) -> dict:
    """공고 요건으로 US FORGED 적합도 판정.

    반환: {status, field, hardtech, stage, us, reasons}
      status ∈ '적합(즉시 후보)' / '적합(설문 확인)' / '부적합'
    """
    f = sectors.field_of(rec.get("sector", ""), rec.get("tech", ""),
                         rec.get("desc", ""), rec.get("svc", ""))
    field, ftrack = f["field"], f["field_track"]
    hardtech = (ftrack == "hax") or (field in TARGET_FIELDS)
    st = stage_status(rec.get("stage", ""))
    target = (rec.get("target") or "")
    us = "미국" in target

    reasons = []
    # 1) 하드테크 아니면 확정 부적합 (Software-only·소비재·범용 제품)
    if not hardtech:
        reasons.append(f"분야 부적합: {field} — Software-only/소비재는 대상 아님")
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


def fine_confirmed(rec: dict) -> bool:
    """분야가 소개·기술 텍스트로 '확정'됐는가(= CB 업종 폴백이 아닌 실체 신호)."""
    fk = sectors.classify(" ".join((rec.get("desc", ""), rec.get("tech", ""),
                                    rec.get("svc", ""))))
    return any(sectors.track_of(k) == "hax" for k in fk)


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
