"""GBD 마스터 DB 대규모 자동 평가 — 라우팅·게이트 퍼널 (Step 3~4 자동화).

  python -m screening.gbd_pipeline            # 전체 퍼널 요약
  python -m screening.gbd_pipeline --xlsx     # output/screening/gbd_auto_eval.xlsx

무엇인가
--------
디캠프 GBD 스타트업 마스터 DB(3,424개사)의 **정형 필드**(업종·기술·스테이지·1줄
소개·재단분류)만으로 500/HAX 엔진의 1차 필터(트랙 라우팅 + 하드 게이트)를 전
기업에 자동 적용한다. 개별 크롤링·LLM 호출 없이 결정적 규칙으로 돌아간다.

무엇을 자동화하고 무엇을 못 하나
  자동화 O: 트랙 라우팅(섹터/기술/소개 키워드) + 스테이지 게이트(투자 스테이지)
  자동화 X: 4축 레벨 점수(v2/v3) — 1줄 소개만으로는 Traction/Team/Market/Moat 를
            신뢰성 있게 매길 수 없다. 점수는 팩트시트가 있는 소표본에서만 낸다
            (consolidated 의 102개사). 이 한계를 리포트에 명시한다.

PII 제외: 대표 이메일·연락처는 추출 단계에서 버렸다(data/gbd_full.json 에 없음).
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

from screening import rules

DATA = Path(__file__).resolve().parent / "data"

# ---------------------------------------------------------------- 라우팅 키워드
# 바이오 치료제(→ IndieBio 라우팅): 신약·치료제 개발. 진단·의료기기·디지털헬스 제외.
BIO_THERA = re.compile(
    r"신약|치료제|therapeutic|drug discovery|antibody|항체|백신|vaccine|"
    r"세포치료|cell therapy|gene therapy|유전자\s*치료|바이오의약품|"
    r"biopharmaceutical|mRNA|면역항암|신약개발|펩타이드|peptide 치료")
# 하드웨어(→ HAX): 물리 제품·소재·로보틱스·기후·에너지·우주·제조 장비
HW_KW = re.compile(
    r"robot|로봇|hardware|하드웨어|manufactur|제조|양산|반도체|semiconductor|"
    r"소재|material|배터리|batter|수소|hydrogen|드론|drone|위성|satellite|"
    r"우주|aerospace|space|센서|sensor|장비|machinery|기계|웨어러블|wearable|"
    r"디바이스|device|모터|motor|전지|셀|actuator|그리퍼|gripper|3d\s*print|"
    r"농기계|chip|칩|리튬|lithium|태양광|solar|풍력|wind power|전기차|EV\b|"
    r"수전해|electroly|변압기|transformer|정련|smelt|광물|mineral|나노섬유|"
    r"바이오센서|biosensor|이차전지|스마트팜 장치|양식 장치|플랜트|plant")
# HAX 제외 섹터(순수 SW·핀테크·크립토·보안·이커머스) → 500 강제
SW_ONLY = re.compile(
    r"fintech|핀테크|payment|결제|crypto|블록체인|blockchain|보안|security|"
    r"이커머스|e-?commerce|커머스\b|SaaS|소프트웨어|software|플랫폼|platform|"
    r"앱\b|app\b|콘텐츠|content|미디어|media|광고|marketing|커뮤니티|community|"
    r"에듀|교육|education|게임|game")

LATE_STAGE = re.compile(r"Series|시리즈|Pre-?IPO|IPO|M&A|상장")
EARLY_STAGE = re.compile(r"Seed|시드|Pre-?A|프리\s*A|Angel|엔젤")


def route(rec: dict) -> tuple[str, str]:
    """(track, reason). 섹터+기술+소개 키워드 결정 규칙."""
    blob = " ".join((rec["sector"], rec["tech"], rec["desc"],
                     rec["name_en"])).lower()
    sector = rec["sector"].lower()
    if not blob.strip():
        return "판정 불가", "정보 부족 (업종·기술·소개 공란)"
    # 1) 바이오 치료제 → IndieBio (디지털 치료제·진단·의료기기·SW 는 제외)
    digital_or_sw = re.search(
        r"digital therapeut|디지털\s*치료|motion|진단|diagnos|플랫폼|platform|"
        r"소프트웨어|software|\bapp\b|\bAI\b", blob)
    is_bio_sector = bool(re.search(r"\bbio\b|biotech|pharma|제약", sector))
    if (BIO_THERA.search(blob) and not digital_or_sw) or \
       (is_bio_sector and not HW_KW.search(blob) and not digital_or_sw
        and not re.search(r"device|기기|SW", blob)):
        return "bio_routing", "바이오 치료제/신약 → IndieBio"
    # 2) 하드웨어 → HAX (단, 순수 SW 성격이 지배적이면 500)
    if HW_KW.search(blob):
        return "hax", "하드웨어/소재/로보틱스/기후 키워드"
    # 3) 그 외 → 500 (섹터 무관)
    return "500", "순수 SW/서비스 (500 섹터 무관)"


def band_of(stage: str) -> str:
    if not stage or stage in ("알 수 없음",):
        return "미상"
    if LATE_STAGE.search(stage):
        return "A 이후"
    if re.search(r"Pre-?A|프리\s*A", stage):
        return "시드 후기"
    if EARLY_STAGE.search(stage):
        return "시드 초기"
    return "미상"


def gate(track: str, band: str) -> tuple[str, str]:
    """(gate_verdict, outcome). 스테이지 기반 하드 게이트."""
    if track == "bio_routing":
        return "라우팅", "IndieBio 라우팅 (점수 미산출)"
    if track == "판정 불가":
        return "판정 불가", "정보 부족 — 라우팅 불가"
    if band == "미상":
        return "스테이지 미상", "스테이지 미상 — 게이트 판정 보류(자료 요청)"
    if track == "hax":
        if band == "A 이후":
            return rules.GATE_FAIL, "게이트 탈락 (HAX 스테이지 이탈 — 시리즈A+)"
        return rules.GATE_COND, "조건부 통과 → 점수화 대상"
    # 500
    if band == "A 이후":
        return rules.GATE_HUMAN, "사람 검토 (500: A 이후 밴드)"
    return rules.GATE_PASS, "통과 → 점수화 대상"


def evaluate(rec: dict) -> dict:
    track, rreason = route(rec)
    band = band_of(rec["stage"])
    gv, outcome = gate(track, band)
    return {**rec, "track": track, "route_reason": rreason, "band": band,
            "gate": gv, "outcome": outcome}


def run() -> list[dict]:
    recs = json.loads((DATA / "gbd_full.json").read_text(encoding="utf-8"))
    return [evaluate(r) for r in recs]


def summarize(rows: list[dict]) -> dict:
    return {
        "n": len(rows),
        "track": Counter(r["track"] for r in rows),
        "band": Counter(r["band"] for r in rows),
        "outcome": Counter(r["outcome"] for r in rows),
        "type": Counter(r["type"].split(",")[0].split("(")[0].strip() or "미분류"
                        for r in rows),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", action="store_true")
    a = ap.parse_args()
    rows = run()
    s = summarize(rows)
    print(f"GBD 마스터 DB 자동 평가 — {s['n']}개사")
    print("\n[트랙 라우팅]")
    for k, n in s["track"].most_common():
        print(f"  {n:5} {k}")
    print("\n[1차 필터 결과]")
    for k, n in s["outcome"].most_common():
        print(f"  {n:5} {k}")
    if a.xlsx:
        from screening import gbd_xlsx
        print("\n" + str(gbd_xlsx.build(rows, s)))


if __name__ == "__main__":
    main()
