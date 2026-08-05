"""실전 선발 사례 평가 — 디캠프×500글로벌 플래그십 1기 (2025.09).

  python -m screening.live_eval            # 결과 출력
  python -m screening.live_eval --report   # screening/LIVE_EVAL.md 생성

무엇인가
--------
디캠프–500글로벌 파트너십으로 실제 선발된 기업(카드몬스터·올세일코퍼레이션 —
1기 전체, 2026.08 기준 2기 미발표)을 웹 검색으로 딥하게 재조사해, 선발 시점
(2025.09) 기준 보강 팩트시트를 만들고 엔진에 통과시킨 결과다.

기존 dataset.py 의 두 기업 항목과 다른 점: 당시 `확인 필요`였던 축을 채울 수
있는 새 사실이 확보됐다 — 카드몬스터의 디즈니 라이선스 계약(2024.11 보도,
선발 이전 확정), 올세일의 첫해 매출·고객사 수(대표 인터뷰).

방법론 (오염 방지)
------------------
- 이 모듈의 레벨은 **개선된 §3·§4 규칙만 받은 격리 세션**이 분류했다.
  격리 세션에는 선발 사실을 주지 않았고, 시점 귀속이 약한 사실은
  `[시점 불명]`으로 표기해 §4-2 규칙으로 보수 처리하게 했다.
- dataset.COMPANIES 에 넣지 않는다 — 두 기업은 이미 admitted_500 으로
  백테스트에 들어 있고, 여기 팩트시트는 보강판이라 섞으면 이중 계상이다.

수집 한계
---------
- 이 환경은 대상 사이트 직접 크롤링이 차단된다(프록시 CONNECT 403) —
  웹 검색 결과 본문만 사용했다. 커머스 리스팅·기업DB 기재는 2026.08 확인분이라
  선발 시점 귀속이 약하다(레벨 분류에서 보수 처리됨).
"""
from __future__ import annotations

import argparse
from pathlib import Path

from screening import dataset, rules, rules_v2, rules_v3

BASE = Path(__file__).resolve().parent.parent

# 선발 시점(2025.09) 기준 보강 팩트시트. 증거 등급과 시점 귀속을 사실마다 표기.
ENRICHED = {
    "cardmonster": {
        "name": "카드몬스터 (CardMonster)", "track": "500", "stage_band": "시드 초기",
        "selected": "디캠프×500글로벌 플래그십 1기 (2025.09 발표, 10.07 데모데이)",
        "facts": [
            ("2023.09 설립", "문서 명시(기업DB)"),
            ("2024.08 500글로벌·매쉬업벤처스 프리시드 (금액 비공개)", "문서 명시(보도)"),
            ("대표 손수현 — 넥슨·펍지(PUBG)·크래프톤 게임 디자이너/프로듀서", "문서 명시(보도)"),
            ("2024.11 월트디즈니 코리아 라이선스 계약 — 디즈니·픽사 IP 게임·완구·굿즈 "
             "개발. 선발 이전 확정", "문서 명시(보도)"),
            ("겨울왕국 트럼프 카드 제작, 쿠팡·자사몰 판매 리스팅(2026.08 확인 — "
             "선발 시점 판매 여부 [시점 불명])", "문서 명시(커머스)"),
            ("기업DB 기재 고객사: 디즈니·유니버설·크래프톤·데브시스터즈·컴투스 "
             "(2026 확인 — [시점 불명])", "문서 명시(기업DB)"),
            ("AI 자체 모델로 기획·개발 기간 ~2년 → 몇 달 단축 주장", "문서 명시(보도)"),
            ("'30조원 글로벌 테이블탑 시장 공략' — 회사 주장 보도", "문서 명시(보도)"),
            ("MRR·판매량·매출 수치", "확인 필요"),
        ],
        # 격리 세션 분류 (개선 §3·§4) — 근거 문장 포함
        "levels": {
            "traction": (3, "오프라인 게임 검증 = 외부 검증 명시(L2↔L3 통과). 판매 "
                            "리스팅·고객사 기재는 [시점 불명]이라 §4-2 시점 귀속상 "
                            "선발 시점 유료화 증거 없음 → L3 상한"),
            "team": (4, "손수현 넥슨·펍지·크래프톤 경력 = 개인 특정+이력 명시(§4-1 "
                        "반례 유형). 깊은 도메인, 엑싯 이력 없음 → L4"),
            "market": (None, "'30조원 시장'은 회사 주장 보도뿐 — Market 상향 금지 "
                             "규칙(덱·논증 문서 필요) → 확인 필요"),
            "moat": (4, "2024.11(선발 이전 확정) 디즈니 라이선스 계약 = 제3자 부여 "
                        "IP 우위 문서 확인 → L4. AI 파이프라인 주장 단독이면 L3"),
        },
        "unstable": {"moat": 3},
        "sources": [
            "https://wowtale.net/2024/11/08/232586/ (디즈니 파트너십, 2024.11)",
            "https://v.daum.net/v/192xFrnQs5 (더 비비드 — 디즈니·픽사 공식 파트너십)",
            "https://www.gamejob.co.kr/Company/Detail?M=45960378 (고객사 로스터)",
            "https://cardmon.store / 쿠팡 리스팅 (판매 확인, 2026.08)",
            "https://www.businesswire.com/news/home/20250831333378/en/ (500 공식 발표)",
        ],
        "gate_kwargs": dict(has_working_product=True,
                            product_note="실물 카드 제품 제작·판매 리스팅 확인"),
        "fit": ("높음", "+6", "500 Korea 프리시드 포트폴리오 + 디캠프 추천 채널 + "
                              "모멘텀(디즈니 계약·투자)"),
    },
    "allsale": {
        "name": "올세일코퍼레이션 (Allsale)", "track": "500", "stage_band": "시드 초기",
        "selected": "디캠프×500글로벌 플래그십 1기 (2025.09 발표, 10.07 데모데이)",
        "facts": [
            ("미국 틱톡샵 공식 파트너사", "문서 명시(보도)"),
            ("2024.08 CJ온스타일 전략적 투자", "문서 명시(보도)"),
            ("더벤처스·500글로벌 등 투자 유치", "문서 명시(인터뷰)"),
            ("법인 설립 1년 만에 뷰티 브랜드 고객사 약 23곳, 첫해 매출 약 3~4억원 "
             "(서술 자체가 선발 이전 실적)", "문서 명시(인터뷰)"),
            ("솔루션 런칭 ~1년 만에 누적 40개 브랜드 온보딩 (도달 시점 [시점 불명])",
             "문서 명시(인터뷰)"),
            ("2025.08 미국 법인 설립 — 선발 직전", "문서 명시(인터뷰)"),
            ("제품 'Affitok': 크리에이터 검색·협업 발송·틱톡샵 추적 자동화", "문서 명시(인터뷰)"),
            ("대표 김정동 — 블록체인 스타트업 창업 경험 후 발견형 커머스로 전환", "문서 명시(인터뷰)"),
            ("월 GMV·수수료 구조·브랜드 리텐션", "확인 필요"),
        ],
        "levels": {
            "traction": (4, "유상 운영대행 실운영 + '첫해 매출 3~4억·고객사 23곳' = "
                            "돈의 이동 명시(L3↔L4 통과) → L4. L5(첫 유료 6개월 이내 "
                            "+ 증가)는 시점 증거 미달"),
            "team": (2, "김정동 블록체인 창업 경험 = 개인 특정+이력 명시로 부여 가능"
                        "(§4-1). 단 커머스 도메인 연결 약함 → L2, '관련 도메인 초기 "
                        "창업'(L3) 여지로 타이브레이크 + 판정 불안정"),
            "market": (None, "덱·시장 논증 문서 없음, 사업 정의만으로 협소/거대 확정 "
                             "불가(§4-4) → 확인 필요"),
            "moat": (4, "틱톡샵 공식 파트너 지위 = 제3자 부여 지위 문서 확인"
                        "(Moat L3↔L4 실례 그대로) → L4"),
        },
        "unstable": {"team": 3},
        "sources": [
            "https://www.tech42.co.kr/ 김정동 대표 인터뷰 (2026.06 — 첫해 실적·경력)",
            "https://www.hankookilbo.com/News/Read/A2025083111480001980 (선발 보도)",
            "https://wowtale.net/2025/09/01/246287/ (1기 선발 발표)",
        ],
        "gate_kwargs": dict(has_working_product=True,
                            product_note="Affitok 솔루션 + 운영대행 실운영"),
        "fit": ("높음", "+6", "500 투자 이력 + 미국 진출이 사업의 본질 + 모멘텀"
                              "(미국 법인·매출)"),
    },
}


def evaluate(key: str) -> dict:
    e = ENRICHED[key]
    base = dataset.by_key(key)          # 게이트 입력은 기존 기업 정의를 재사용
    levels = {a: v[0] for a, v in e["levels"].items()}
    gate = rules.gate_verdict(rules.run_gates(base))
    v2 = rules_v2.aggregate(e["track"], levels)
    v3 = rules_v3.decide(e["track"], levels, e["unstable"], gate)
    return {"key": key, "e": e, "gate": gate, "v2": v2, "v3": v3,
            "action": rules_v3.action_of(v3, e["fit"][0])}


def baseline(key: str) -> dict:
    """비교용 — 기존 dataset(공개 정보 얕은 수집) 기준 판정."""
    c = dataset.by_key(key)
    gate = rules.gate_verdict(rules.run_gates(c))
    lv = dataset.levels_v2_of(c)
    return {"v2": rules_v2.aggregate(c.track, lv),
            "v3": rules_v3.decide(c.track, lv, c.unstable, gate)}


def render() -> str:
    L = ["# 실전 선발 사례 평가 — 디캠프×500글로벌 플래그십 1기", ""]
    L.append("**선발 리스트 검증**: 웹 재조사 결과 1기 선발은 카드몬스터·올세일코퍼레이션 "
             "**2개사가 전부**다(2025.08.28 MOU, 2025.09.01 발표, 10.07 SF 데모데이). "
             "2기는 2026.1Q 예정이었으나 2026.08 현재 선발 발표를 찾지 못했다.")
    L.append("")
    L.append("**선발 구조에 대한 발견**: 두 기업 모두 선발 **이전에 이미 500 글로벌이 "
             "투자한 포트폴리오사**다(카드몬스터 2024.08 프리시드 리드, 올세일도 "
             "500글로벌 투자 확인). 즉 이 선발은 엔진이 모사하는 '콜드 지원 심사'가 "
             "아니라 **기존 포트폴리오 + 디캠프 추천 채널**을 통한 선발이다. 이 표본으로 "
             "'엔진이 심사를 재현하는가'를 검증할 때는 이 선택 편향을 감안해야 한다.")
    L.append("")
    for key in ENRICHED:
        r = evaluate(key)
        b = baseline(key)
        e = r["e"]
        L.append(f"## {e['name']} — {e['selected']}")
        L.append("")
        L.append("| 사실 | 증거 등급 |")
        L.append("|---|---|")
        for f, g in e["facts"]:
            L.append(f"| {f} | {g} |")
        L.append("")
        L.append("**격리 세션 분류 (개선 §3·§4 적용)**:")
        L.append("")
        for axis, (lv, why) in e["levels"].items():
            tag = f"L{lv}" if lv else "`확인 필요`"
            L.append(f"- **{rules.AXIS_LABELS[axis]}** {tag} — {why}")
        L.append("")
        w = "—" if r["v2"].weighted is None else f"{r['v2'].weighted:.2f}"
        L.append(f"- 게이트: **{r['gate']}** (풀타임·리로케이션 설문 미제출)")
        L.append(f"- v2: 가중평균 **{w}** → **{r['v2'].tier}** / Fit **{e['fit'][0]}**")
        L.append(f"- v3: 구간 **[{r['v3'].lo:.2f}, {r['v3'].hi:.2f}]** → "
                 f"**{r['v3'].zone}**")
        L.append(f"- 조치: **{r['action']}**")
        bw = "—" if b["v2"].weighted is None else f"{b['v2'].weighted:.2f}"
        L.append(f"- (비교) 얕은 공개 정보 기준: v2 {bw} → {b['v2'].tier} / "
                 f"v3 [{b['v3'].lo:.2f}, {b['v3'].hi:.2f}] → {b['v3'].zone}")
        L.append("- 출처: " + " / ".join(e["sources"]))
        L.append("")

    L.append("## 판정 요약 — 엔진은 실제 선발 기업을 선택하는가")
    L.append("")
    L.append("| 기업 | 실제 결과 | v2 (점추정) | v3 (구간) | 걸러지는가 |")
    L.append("|---|---|---|---|---|")
    for key in ENRICHED:
        r = evaluate(key)
        w = f"{r['v2'].weighted:.2f}"
        L.append(f"| {r['e']['name']} | 선발 ✅ | {r['v2'].tier} ({w}) | "
                 f"{r['v3'].zone} | **아니다** — 탈락/비추천 아님 |")
    L.append("")
    L.append("읽는 법:")
    L.append("")
    L.append("1. **두 선발사 모두 v2 에서 `B 확인 후 추천` + Fit 높음 → 조치 '추천 진행'** "
             "— 엔진은 실제 선발 기업을 걸러내지 않고 추천 트랙에 올린다.")
    L.append("2. **v3 는 두 기업 모두 `사람 검토`** — 확정 추천까지 가지 못하는 이유는 "
             "둘 다 같다: Market 축이 `확인 필요`(덱 미제출)라 구간 하한이 추천선 "
             "3.25 아래로 내려간다. 실제 운영에서 덱이 들어오면(예: Market L3 확정 시 "
             "카드몬스터 하한 3.30) 확정 추천으로 넘어가는 구조다. 올세일은 Team 축 "
             "(도메인 연결)이 추가 관건이다.")
    L.append("3. **올세일 가중평균 3.25 는 정확히 B 컷오프 경계값**이다 — 점추정(v2)만 "
             "보면 운에 가까운 판정이고, v3 가 `사람 검토`로 유보하는 것이 이 사례에서 "
             "구조적으로 더 정직하다.")
    L.append("4. 이 결과는 재현성 측정(AGREEMENT.md)과 일관된다: 공개 정보만으로 엔진이 "
             "확정 판정을 내리는 비율은 낮고, 병목은 규칙이 아니라 제출 자료다.")
    L.append("")
    L.append("한계: (1) 선발 사실을 알고 사후에 수집한 팩트다 — 격리 분류·시점 귀속으로 "
             "완화했지만 확증 편향을 완전히 제거할 수 없다. (2) 탈락한 지원 기업(대조군)은 "
             "비공개라 이 두 건으로 판별력을 주장할 수 없다 — '선발사를 떨어뜨리지 "
             "않는다'는 재현율 방향의 증거일 뿐이다. (3) 직접 크롤링 차단으로 검색 결과 "
             "본문만 사용했다.")
    L.append("")
    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    for key in ENRICHED:
        r = evaluate(key)
        w = f"{r['v2'].weighted:.2f}" if r["v2"].weighted else "—"
        print(f"{r['e']['name']}: 게이트 {r['gate']} / v2 {r['v2'].tier} ({w}) / "
              f"v3 [{r['v3'].lo:.2f}, {r['v3'].hi:.2f}] {r['v3'].zone} / {r['action']}")
    if a.report:
        body = render()
        (BASE / "screening" / "LIVE_EVAL.md").write_text(body, encoding="utf-8")
        print("\n리포트: screening/LIVE_EVAL.md")


if __name__ == "__main__":
    main()
