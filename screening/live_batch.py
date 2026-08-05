"""디캠프 배치 기업 31개사 실전 평가 — 라우팅·게이트 퍼널 + 점수화.

  python -m screening.live_batch            # 퍼널 요약 출력
  python -m screening.live_batch --xlsx     # output/screening/live_eval.xlsx 생성

무엇인가
--------
디캠프 배치 2·4·6·7기에 실제 선발된 31개사를 웹 검색으로 수집(facts_all.json)해,
500/HAX 프리스크리닝 엔진에 통과시킨다. 이 표본의 성격이 중요하다:

  디캠프 '배치'는 **프리A~시리즈A 스케일업** 프로그램이다. 500 Flagship·HAX 는
  **프리시드~시드** 대상이다. 즉 이 31개사는 500/HAX 의 타깃보다 **한두 단계 뒤**다.
  따라서 엔진의 1차 필터(트랙 라우팅 + 스테이지 게이트)에서 대량 탈락하는 것이
  정상이며, 그 자체가 "게이트가 스테이지를 실제로 거른다"는 증거다.

라우팅 규칙 (엔진 로직, 사실 기반 — 사람 판단 아님)
  - 바이오 치료제/의약품 생산 → bio_routing (IndieBio, 점수 미산출)
  - 물리 하드웨어/소재/로보틱스/기후/에너지/우주 → HAX 트랙
  - 순수 SW → 500 트랙 (HAX 제외 섹터)
경계 사례는 ROUTING 에 사유와 함께 표기했다.

한계: 직접 크롤링 차단(403)으로 검색 결과 본문만 사용. 스테이지 밴드는 공개된
최신 라운드로 추정했고, 미확인 라운드는 보수적으로 낮은 밴드에 두되 `확인 필요`로
표기한다.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from screening import rules, rules_v2, rules_v3

BASE = Path(__file__).resolve().parent.parent
FACTS = BASE / "output" / "screening" / "facts_all.json"

# 트랙·밴드·라우팅 사유. 근거는 facts_all.json 의 사실. (track, stage_band, reason)
ROUTING = {
    # ---- 배치 2기 ----
    "loas":        ("hax", "시드 후기", "산업 이상음 센서+SW 진단 하드웨어 / 프리A 40억"),
    "vusion":      ("hax", "A 이후", "PDLC 필름 소재·양산 / 시리즈A 50억 클로징"),
    "tesollo":     ("hax", "A 이후", "로봇핸드 양산 / 시리즈A→B, IPO 준비"),
    "eflow":       ("hax", "시드 후기", "AFPM 모터 양산(2024) / 라운드 미확인 → 보수 밴드"),
    "tial":        ("hax", "A 이후", "AI 폐기능 검사기(의료기기 HW) / 시리즈A 25억. 진단기기라 IndieBio 아님"),
    "vpplab":      ("500", "A 이후", "VPP 전력중개 순수 SW / 시리즈A"),
    "ds_semicon":  ("500", "시드 후기", "반도체 불량검출 머신비전 SW / 프리A"),
    # ---- 배치 4기 ----
    "gaptech":     ("hax", "시드 초기", "온실가스 저감 설비 HW / 투자 라운드 미확인 → 보수 밴드"),
    "deepmetrics": ("500", "A 이후", "의료 AI 순수 SW(HAX 제외 섹터) / 시리즈A 50억"),
    "metech":      ("hax", "시드 초기", "축우 메탄 캡슐 HW / 라운드 미확인, 수출계약 존재"),
    "spacelintech": ("bio_routing", "A 이후", "미세중력 바이오의약품 '생산' → 치료제 라우팅(IndieBio). 시리즈B"),
    "ideaocean":   ("hax", "시드 후기", "설계 AI(SW)+모듈 HW / 프리A 15억. HW 병행이라 HAX"),
    "ahes":        ("hax", "A 이후", "알카라인 수전해 장치 소재·HW / 시리즈A 60억"),
    "cosmobee":    ("hax", "시드 초기", "위성 홀추력기 HW / 라운드 미확인, 개발 단계"),
    "tepharobotics": ("500", "시드 후기", "로봇 로우코드 순수 SW / 프리A 20억"),
    "firstlab":    ("hax", "시드 후기", "초음파 집속 장비 HW(제약·수처리) / 프리A 31억. 장비라 IndieBio 아님"),
    "pitin":       ("hax", "시드 후기", "배터리 스왑 스테이션 HW / 프리A 20억"),
    # ---- 배치 6기 ----
    "readyrobust": ("hax", "A 이후", "중장비 유압회수 HW / 시리즈B 134억"),
    "imeditech":   ("hax", "A 이후", "나노섬유 의료기기 HW / 시리즈B. 기기라 IndieBio 아님"),
    "rx_deeptech": ("500", "시드 초기", "SMR 설계 엔지니어링 SW / 라운드 미확인"),
    "enertech":    ("hax", "시드 후기", "하이브리드 변압기 전력기기 HW / 라운드 미확인, 납품 실적"),
    "walkerin":    ("hax", "시드 후기", "궤도상 서비싱 로봇위성 HW / 프리A 90억"),
    "withpoints":  ("hax", "시드 후기", "3D 로봇비전 자동화 HW+SW / 프리A 40억"),
    "provalabs":   ("hax", "시드 후기", "오가노이드 바이오센서(분석 도구) / 프리A. 치료제 아니라 HAX"),
    "hydroexpand": ("hax", "시드 후기", "AEM 수전해 스택 소재·HW / 프리A"),
    # ---- 배치 7기 ----
    "kids23c":     ("500", "A 이후", "버추얼 아이돌 엔터 SW / 시리즈A 40억"),
    "grineta":     ("500", "시드 초기", "3D 데이터 압축 산업 AI SW / 라운드 미확인"),
    "dor":         ("500", "시드 후기", "게임영상 소셜 플랫폼 SW / 시드(2023.12), 60만 유저"),
    "deeppoint":   ("hax", "시드 후기", "남성 헤어 디바이스 HW+D2C / 시드, 매출 140억"),
    "wake":        ("hax", "시드 후기", "대체커피 푸드테크 제조 HW / 프리A. 이커머스 아님(제조)"),
    "infoseez":    ("500", "A 이후", "온톨로지 산업 AI SW / 첫 라운드 130억(A급)"),
}


def load_facts() -> dict:
    return json.loads(FACTS.read_text(encoding="utf-8"))


def route_and_gate(key: str) -> dict:
    """트랙 라우팅 → 스테이지·섹터 하드게이트. 점수화 이전 1차 필터."""
    track, band, reason = ROUTING[key]
    f = load_facts()[key]
    if track == "bio_routing":
        return {"key": key, "name": f["name"], "batch": f["batch"], "track": track,
                "band": band, "reason": reason, "gate": "라우팅",
                "scoreable": False, "outcome": "IndieBio 라우팅 (점수 미산출)"}

    # 게이트 로직 재현 (rules.run_gates 와 동일 판정, 밴드/섹터 입력만 여기서 구성)
    gates = []
    if track == "500":
        gates.append(("동작 프로토타입", rules.GATE_PASS))   # 전 기업 제품 존재 확인
        gates.append(("풀타임/리로케이션", rules.GATE_COND))  # 설문 미제출
        gates.append(("스테이지", rules.GATE_HUMAN if band == "A 이후" else rules.GATE_PASS))
    else:  # hax
        # HAX 제외 섹터 여부는 라우팅에서 이미 SW 를 500 으로 보냈으므로 여기선 통과
        gates.append(("HAX 제외 섹터", rules.GATE_PASS))
        if band == "A 이후":
            gates.append(("스테이지/프라이스드 라운드 충돌", rules.GATE_FAIL))
        else:
            # 시드 후기까지는 프라이스드 라운드 가능성 → 조건부
            gates.append(("프라이스드 라운드", rules.GATE_COND))
        gates.append(("HAX 지분 수용", rules.GATE_COND))
    gates.append(("C레벨 영어", rules.GATE_COND))

    verdict = rules.gate_verdict([rules.GateResult(n, v, "") for n, v in gates])
    scoreable = verdict != rules.GATE_FAIL
    outcome = {
        rules.GATE_FAIL: "게이트 탈락 (스테이지 이탈 — HAX 프리시드~시드 대상 아님)",
        rules.GATE_HUMAN: "사람 검토 에스컬레이션 (500: A 이후 밴드)",
        rules.GATE_COND: "조건부 통과 → 점수화 진행",
        rules.GATE_PASS: "통과 → 점수화 진행",
    }[verdict]
    return {"key": key, "name": f["name"], "batch": f["batch"], "track": track,
            "band": band, "reason": reason, "gate": verdict,
            "scoreable": scoreable, "outcome": outcome}


def funnel() -> list[dict]:
    return [route_and_gate(k) for k in ROUTING]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", action="store_true")
    a = ap.parse_args()
    rows = funnel()
    from collections import Counter
    c = Counter(r["outcome"] for r in rows)
    print(f"총 {len(rows)}개사")
    for outcome, n in c.most_common():
        print(f"  {n:2}개사 — {outcome}")
    print()
    print(f"점수화 대상(게이트 통과): {sum(1 for r in rows if r['scoreable'])}개사")
    if a.xlsx:
        from screening import live_batch_xlsx
        live_batch_xlsx.build()


if __name__ == "__main__":
    main()
