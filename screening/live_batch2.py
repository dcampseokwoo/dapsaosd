"""디캠프 배치 1·3·5기 24개사 실전 평가 — 라우팅·게이트 퍼널.

live_batch.py 와 동일 구조. 이 24개사는 배치 1·3·5기(IT서비스·커머스·AI SW 중심)로,
대부분 순수 SW → 500 트랙이다. 500 은 섹터 무관 프로그램이라 HAX 의 제외 섹터
게이트(순수SW·핀테크·이커머스 탈락)가 **적용되지 않는다** — 따라서 이 배치에서는
하드 게이트 탈락이 없고, 스테이지 이탈(A 이후)만 사람 검토로 에스컬레이션된다.
(하드웨어 배치 2·4·6·7기와 대비되는 지점.)

facts: output/screening/facts_new.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from screening import rules

BASE = Path(__file__).resolve().parent.parent
FACTS = Path(__file__).resolve().parent / "data" / "facts_batch_135.json"

# (track, stage_band, reason). 전 기업 순수 SW/서비스 → 500 트랙(섹터 무관).
ROUTING2 = {
    # ---- 배치 1기 ----
    "studiolab":   ("500", "시드 후기", "패션 커머스 콘텐츠 생성 SaaS / 프리A(2023)"),
    "intellisys":  ("500", "시드 초기", "기업용 RAG SW / 라운드 미확인, 제품 2024.10 출시"),
    "bind":        ("500", "A 이후", "남성 패션 버티컬 커머스 / 시리즈A 40억"),
    "kaviz":       ("500", "시드 후기", "농산물 정기배송 커머스 / 프리A, 매출 121억"),
    "oneselfworld": ("500", "시드 후기", "블록체인 리워드 앱 / 프리시리즈A"),
    "petpharm":    ("500", "A 이후", "반려동물 의약품 B2B 커머스/유통 — 치료제 개발 아님(라우팅X) / 시리즈B"),
    "meisters":    ("500", "시드 후기", "가전 A/S 서비스+B2B SaaS / 프리A, 매출 268억"),
    "nextedition": ("500", "시드 후기", "캠핑 예약 O2O+PMS / 프리A+브릿지"),
    "lenized":     ("500", "시드 초기", "버추얼 아바타 영상편집 앱 / 초기 투자(2024)"),
    # ---- 배치 3기 ----
    "nextground":  ("500", "시드 후기", "부동산 리뷰 플랫폼 SW / 시드(2022)"),
    "realdraw":    ("500", "시드 후기", "AI 웹툰 제작 SW / 프리시리즈A 22억"),
    "theplato":    ("500", "시드 초기", "AI 노트테이커 SaaS / 시드 8억, MRR 1억·월37%"),
    "rentry":      ("500", "A 이후", "렌탈 유통 플랫폼 / 시리즈A 41억"),
    "namdomarket": ("500", "A 이후", "도매시장 AI OS·B2B 커머스 / 시리즈A 60억"),
    "kepartners":  ("500", "시드 초기", "교육 AX SW / 라운드 미확인, 1300 학원 사용"),
    "pulsead":     ("500", "시드 후기", "이커머스 광고 관리 SaaS / 프리A 20억"),
    # ---- 배치 5기 ----
    "goijang":     ("500", "A 이후", "상조 원스톱 서비스 / 시리즈A 90억"),
    "rootrix":     ("500", "A 이후", "수목 유통 플랫폼 / 시리즈A 45억"),
    "violetpay":   ("500", "시드 초기", "계좌 기반 PG 핀테크 / 라운드 미확인"),
    "apollostudio": ("500", "시드 초기", "AI 게임 엔진 / 시드(2025.10), 제품 미출시"),
    "ents":        ("500", "A 이후", "탄소관리 ESG SaaS / 시리즈A 20억"),
    "impactiveai": ("500", "A 이후", "AI 수요예측 SaaS / 시리즈A 82억"),
    "constant":    ("500", "A 이후", "AI 두피케어 D2C(스캐너+화장품) / 시리즈A후 110억"),
    "lemong":      ("500", "시드 후기", "자영업 리뷰관리 AI SaaS / 프리A 10억, 흑자"),
}


def load_facts() -> dict:
    return json.loads(FACTS.read_text(encoding="utf-8"))


def route_and_gate(key: str) -> dict:
    track, band, reason = ROUTING2[key]
    f = load_facts()[key]
    # 전 기업 500 트랙 — 섹터 제외 게이트는 HAX 전용이라 미적용.
    # 제품 존재 여부: apollostudio(제품 미출시)만 프로토타입 게이트 확인 필요
    no_product = key == "apollostudio"
    gates = []
    if no_product:
        gates.append(("동작 프로토타입", rules.GATE_FAIL))
    else:
        gates.append(("동작 프로토타입", rules.GATE_PASS))
    gates.append(("풀타임/리로케이션", rules.GATE_COND))
    gates.append(("스테이지", rules.GATE_HUMAN if band == "A 이후" else rules.GATE_PASS))
    gates.append(("C레벨 영어", rules.GATE_COND))
    verdict = rules.gate_verdict([rules.GateResult(n, v, "") for n, v in gates])
    scoreable = verdict != rules.GATE_FAIL
    outcome = {
        rules.GATE_FAIL: "게이트 탈락 (동작 프로토타입 없음 — 제품 미출시)",
        rules.GATE_HUMAN: "사람 검토 에스컬레이션 (500: A 이후 밴드)",
        rules.GATE_COND: "조건부 통과 → 점수화 진행",
        rules.GATE_PASS: "통과 → 점수화 진행",
    }[verdict]
    return {"key": key, "name": f["name"], "batch": f["batch"], "track": track,
            "band": band, "reason": reason, "gate": verdict,
            "scoreable": scoreable, "outcome": outcome}


def funnel() -> list[dict]:
    return [route_and_gate(k) for k in ROUTING2]


def main() -> None:
    ap = argparse.ArgumentParser()
    a = ap.parse_args()
    from collections import Counter
    rows = funnel()
    c = Counter(r["outcome"] for r in rows)
    print(f"총 {len(rows)}개사 (배치 1·3·5기)")
    for outcome, n in c.most_common():
        print(f"  {n:2}개사 — {outcome}")
    print(f"\n점수화 대상: {sum(1 for r in rows if r['scoreable'] and r['gate'] != rules.GATE_HUMAN)}개사"
          f" (+ 사람검토 {sum(1 for r in rows if r['gate']==rules.GATE_HUMAN)}개사 참고 점수)")


if __name__ == "__main__":
    main()
