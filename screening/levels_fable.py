"""Fable 독립 분류 — 블라인드 재분류 결과 (작업 1-2).

생성 절차
---------
1. `blind_fixture.py` 가 dataset.COMPANIES 에서 사실만 추출해
   `output/screening/blind_input.json` 생성 (levels/LEVELS_V2/FIT/
   ground_truth/unstable/note/fit_reason/sources/needs_confirm 제외).
2. **dataset.py 를 읽은 적 없는 격리 세션**(같은 Fable 모델, 깨끗한 컨텍스트)이
   그 JSON + ENGINE_V2.md §3(밴드별 레벨표)·§4(증거 등급 규칙) 발췌만 보고
   각 축을 분류했다. ENGINE_V2.md 원문은 §6·§12 에 기존 분류 일부가 적혀 있어
   통째로 주지 않았다.
3. 격리 세션은 `[후행]` 사실과 합격/탈락 결과 사실을 레벨 근거에서 제외하라는
   지시를 받았다.
4. 이 파일은 격리 세션의 출력을 기계적으로 변환한 것이다 — 메인 세션이
   레벨 값을 수정하지 않았다.

CONFIDENCE: 그 축을 정하면서 다른 레벨(또는 `확인 필요`)과 진짜로 헷갈렸으면
"low". 작업 2에서 "불일치가 예측 가능했는가" 검증에 쓴다.

ALT: confidence="low" 축 중 **구체적 인접 레벨**과 헷갈린 경우 그 대안 레벨.
`확인 필요`(None)와 헷갈린 경우는 포함하지 않는다(레벨 범위로 전파 불가).
rules_v3.decide 의 unstable 입력으로 쓴다.

RECLASSIFIED: 작업 2-3 — 개선된 레벨 정의로 **불일치했던 축만** 격리
재분류한 결과. agreement.improvement_effect() 가 전후 일치율을 계산한다.
"""
from __future__ import annotations


LEVELS_FABLE: dict[str, dict[str, tuple[int | None, str]]] = {
    "cardmonster": {
        "traction": (2,
                    "오프라인 게임 실물 출시·테스트는 문서로 확인되나 외부 사용자·유료 지표는 '확인 필요'이므로 시드 초기 L2(출시했으나 외부 사용 미확인)에 해당, 외부 사용 증거가 있으면 L3"),
        "team": (4,
                    "대표의 넥슨·크래프톤(PUBG) 게임 기획/제작 경력(문서 명시 보도)이 '깊은 도메인, 스케일업(창업) 이력 없음' L4 정의에 부합"),
        "market": (None,
                    "덱 미제출이고 시장 규모·논증에 관한 사실이 전무 — 덱 미제출 상태에서 시장 논증 판정 금지 규칙에 따라 null"),
        "moat": (3,
                    "AI 카드 디자인·밸런싱 자동화 파이프라인 보유가 보도로 명시되나 데이터·IP 우위의 가시성은 미확인 — '그럴듯하나 미구축' L3"),
    },
    "allsale": {
        "traction": (3,
                    "중소 브랜드 대상 원스톱 체계 구축·서비스 실운영(문서 명시)으로 외부 사용자 존재 = 시드 초기 L3, 유료 브랜드 수·GMV는 '확인 필요'라 L4 불가"),
        "team": (None,
                    "대표 이름(김정동)만 기업DB에 있고 경력 사실이 없음 — 팀 축 근거 부재로 null"),
        "market": (None,
                    "덱 미제출이고 시장 규모 논증 사실 없음 — null"),
        "moat": (3,
                    "미국 틱톡샵 공식 파트너사 지위(문서 명시)는 자산이나 배타적 데이터·네트워크·IP 우위 가시성은 아님 — '그럴듯하나 미구축' L3"),
    },
    "stillbright": {
        "trl": (5,
                    "랩 스케일 전기화학 정련 공정 실증(product_note, 컬럼비아 스핀아웃 보도)이 프리시드 L5 '랩 통합 프로토타입(TRL 4~5)'에 해당; [후행] 파일럿 사실은 제외"),
        "team": (4,
                    "컬럼비아대 연구진 공동창업(CEO/CTO, 문서 명시)으로 자기 기술 분야 깊은 도메인 보유, 스케일업·양산 이력은 없음 = L4"),
        "manufacturing": (None,
                    "지원 시점 BOM·공급사·양산 관련 사실이 전무([후행] 설비 목표는 제외) — null"),
        "customer": (None,
                    "지원 시점 고객·LOI·파일럿 사실이 전무 — null"),
    },
    "neptune": {
        "trl": (5,
                    "[후행] 표시 없는 product_note '실해역 운용 로봇'과 AI 판별+캐비테이션 세정 로봇 보도가 시드 초기 L5 '관련 환경 검증 통합 프로토타입(TRL 5~6)' 이상에 해당하나 시점 특정이 약함"),
        "team": (None,
                    "Entrepreneur First 출신이라는 프로그램 이력만 있고 해양·로봇 도메인 경력 사실이 없음 — 팀 근거 미달로 null"),
        "manufacturing": (None,
                    "지원 시점 BOM·CM 사실 없음(로봇 27대·항만 운영은 [후행]) — null"),
        "customer": (2,
                    "Cargill·NYK 계약은 [후행]으로 제외, 남는 것은 연료 절감·CO2 감축 정량 가치 제안(보도)뿐 = '타깃 세그먼트 정의' L2"),
    },
    "safetics": {
        "traction": (4,
                    "매출 4.1억→4.9억→7.0억 연속 성장(기업DB)과 두산로보틱스·넥스코봇 계약 = A 이후 L4 '유료 고객 + 명확한 우상향'; 20%+ MoM 증거 없어 L5 불가"),
        "team": (None,
                    "창업팀 경력에 관한 사실이 전무 — null"),
        "market": (2,
                    "사업 정의 자체(협동로봇 충돌 안전 분석 SW+인증, sector_note)가 협소한 B2B 세그먼트임을 확정 — 니치(L1)와 논증 약한 대형(L3) 사이 L2"),
        "moat": (4,
                    "안전 인증 도메인 SW + 대만·중국·일본 독점 총판 계약(문서 명시)으로 구조적 우위가 부분적으로 가시화 — L3(그럴듯)와 L5(완전 가시적) 사이 L4"),
    },
    "dhive": {
        "trl": (4,
                    "실증 투입 로봇 존재(product_note) + 규제샌드박스 선정(보도)이 시드 초기 L4 '실환경 실증 진행 중(TRL 5)'에 해당; 도입은 아직 '예정'이라 L5 불가"),
        "team": (None,
                    "창업팀 구성·경력이 '확인 필요' — null"),
        "manufacturing": (None,
                    "BOM·양산 파트너가 '확인 필요' — null"),
        "customer": (4,
                    "수원시 자율주행 방범·물류 서비스 단계적 도입 예정(보도) = 지자체와의 도입 합의로 'LOI·공동평가 합의' L4에 해당, 유료 증거는 없어 L5 불가"),
    },
    "bitbyte": {
        "traction": (4,
                    "돈이돼지 출시 후 연속 흑자·월간 BEP + 매출 전년 동기 8배(모두 보도 명시) = 시드 후기 L4 '유료(수익화) + 명확한 우상향'; 지속 20%+ MoM은 미확인이라 L5 불가"),
        "team": (None,
                    "대표 이름만 있고 경력 사실이 없음 — null"),
        "market": (None,
                    "덱 미제출이고 시장 논증 사실 없음, 사업 정의만으로 협소/대형 확정 불가 — null"),
        "moat": (2,
                    "매출 8배 성장의 동력이 외부 솔루션(딜라이트룸 '다로') 적용임이 보도로 명시 — 자체 우위 부재를 시사하는 성격 확정 사실로 L1~L3 사이 L2"),
    },
    "nthing": {
        "trl": (5,
                    "상용 제품 배치 중(product_note) + 시리즈C·삼성벤처 투자(보도)가 A 이후 L5 '상용 배치·양산 검증'에 해당; 양산 검증 자체의 직접 증거는 얇음"),
        "team": (None,
                    "창업팀 경력에 관한 사실이 전무 — null"),
        "manufacturing": (None,
                    "BOM·공급사·CM에 관한 문서 명시 사실 없음 — null"),
        "customer": (None,
                    "유일한 고객 관련 사실(UAE 수주)이 '추정' 등급으로 문서 명시 미달 — null"),
    },
    "jobis": {
        "trl": (5,
                    "상용 서비스 운영(product_note) + 1,500억 프리IPO 추진(보도)이 A 이후 L5 '상용 배치'에 해당(SW라 TRL을 상용화 단계로 해석)"),
        "team": (None,
                    "창업팀 경력 사실이 전무 — null"),
        "manufacturing": (None,
                    "SW 서비스이고 양산 경로 관련 사실 없음 — null"),
        "customer": (5,
                    "상용 유료 서비스로 프리IPO 규모까지 확인(보도) → 유료 고객 확보 = L5, 다만 고객 지표 직접 사실은 없어 확신 낮음"),
    },
    "palussmny": {
        "traction": (3,
                    "평판 커뮤니티 서비스 운영 중(product_note+sector_note)으로 외부 사용자 존재 = L3(프리시드/시드 초기 기준); 스테이지 밴드가 '확인 필요'라 열 선택이 불확실"),
        "team": (None,
                    "창업팀 경력이 '확인 필요' — null"),
        "market": (2,
                    "사업 정의 자체(대학원 연구실 평판 커뮤니티/이공계 채용)가 협소 세그먼트임을 확정 — 니치 L1과 L3 사이, 채용 확장성 고려해 L2"),
        "moat": (3,
                    "평판 데이터 축적형 커뮤니티라는 사업 성격상 데이터·네트워크 우위가 그럴듯하나 규모·우위 가시성 미확인 = L3"),
    },
    "wavedeck": {
        "traction": (None,
                    "프로토타입 존재 여부조차 확인 불가, 제품·매출 일체 '확인 필요' — null"),
        "team": (None,
                    "팀 관련 사실 일체 '확인 필요' — null"),
        "market": (None,
                    "사업 내용 자체를 특정 실패 — null"),
        "moat": (None,
                    "사업 내용 미상으로 모트 판단 근거 전무 — null"),
    },
    "aroundus": {
        "traction": (None,
                    "현재 매출·운영 상태 '확인 필요'이며 '7년간 보도 없음'을 활동 부재의 근거로 쓰는 것은 금지 — null"),
        "team": (None,
                    "팀 경력 사실 전무 — null"),
        "market": (None,
                    "'지역 기반 서비스'는 사업 내용을 확정하기에 불충분하고 시장 논증 사실 없음 — null"),
        "moat": (None,
                    "모트 관련 사실 전무 — null"),
    },
    "kkureogi": {
        "trl": (None,
                    "CES 2025 참가 사실만으로 TRL 특정 금지(§4), 제품·기술은 '확인 필요' — null"),
        "team": (None,
                    "팀 관련 사실 '확인 필요' — null"),
        "manufacturing": (None,
                    "양산 관련 사실 전무 — null"),
        "customer": (None,
                    "고객 관련 사실 전무 — null"),
    },
    "avidbots": {
        "trl": (5,
                    "HAX 공식 서술의 '거친 프로토타입 상태로 입주'가 프리시드 L5 '랩 통합 프로토타입(TRL 4~5)'에 해당(로봇 전체 프로토타입 = 통합체); '거친'이라 L4와 헷갈림"),
        "team": (None,
                    "공동창업자 이름(Faizan Sheikh)만 있고 경력 사실 없음 — null"),
        "manufacturing": (None,
                    "입주 시점 BOM·양산 파트너 '확인 필요' — null"),
        "customer": (None,
                    "입주 시점 고객 '확인 필요'(고객 계약은 HAX 이후 시퀀스) — null"),
    },
    "cocoon": {
        "trl": (None,
                    "입주 시점 TRL이 명시적으로 '확인 필요'이고 'HAX 랩 설비 활용 개발'은 입주 후 활동이라 지원 시점 근거가 안 됨 — null"),
        "team": (None,
                    "창업팀 구성·경력 '확인 필요' — null"),
        "manufacturing": (None,
                    "입주 시점 양산 계획 '확인 필요' — null"),
        "customer": (None,
                    "입주 시점 고객 '확인 필요' — null"),
    },
    "levelzero": {
        "trl": (None,
                    "입주 시점 센서 완성도·임상 데이터 '확인 필요' — null"),
        "team": (None,
                    "창업자 이름과 EF 출신 프로그램 이력만 있고 바이오센서 도메인 경력 사실 없음 — null"),
        "manufacturing": (None,
                    "양산 관련 사실 전무 — null"),
        "customer": (None,
                    "고객 관련 사실 전무 — null"),
    },
    "unspun": {
        "trl": (None,
                    "입주 시점 TRL '확인 필요', '위빙 장비 개발' 문구만으로 단계 특정 불가 — null"),
        "team": (None,
                    "창업팀 '확인 필요' — null"),
        "manufacturing": (None,
                    "양산 관련 사실 전무 — null"),
        "customer": (None,
                    "고객 '확인 필요' — null"),
    },
    "saasmetrics": {
        "traction": (4,
                    "유료 고객 수십 곳 + 44개국 500+ 기업 가입 + 30% MoM(모두 보도 명시) = 프리시드 L4 '유료 고객 1곳 이상 + 무료 사용자 급증'; L5의 '첫 유료 고객 6개월 이내/리텐션 곡선' 증거는 없음"),
        "team": (None,
                    "창업자 이름 외 팀 규모·경력이 '확인 필요'이고 탈락 공개는 결과 사실이라 근거 불가 — null"),
        "market": (None,
                    "시장 규모·논증 사실 없음, 사업 정의만으로 협소/대형 확정 불가 — null"),
        "moat": (None,
                    "모트 관련 사실 전무 — null"),
    },
    "helpdocs": {
        "traction": (2,
                    "제품 운영 중(product_note)으로 출시는 확정되나 외부 사용자·유료 고객이 '확인 필요' = 시드 초기 L2(출시, 외부 사용 미확인); L3 가능성과 헷갈림"),
        "team": (2,
                    "창업자 스스로 '고객지원 업계 인적 네트워크 없었다'고 밝힘(보도 명시) + 창업 1년 2인 — '도메인 연결 약함' L2 정의에 직접 부합"),
        "market": (None,
                    "덱 미제출이고 시장 논증 사실 없음 — null"),
        "moat": (None,
                    "모트 관련 사실 전무 — null"),
    },
}


CONFIDENCE: dict[str, dict[str, str]] = {
    "cardmonster": {"traction": "low", "team": "high", "market": "high", "moat": "low"},
    "allsale": {"traction": "low", "team": "high", "market": "high", "moat": "low"},
    "stillbright": {"trl": "low", "team": "high", "manufacturing": "high", "customer": "high"},
    "neptune": {"trl": "low", "team": "low", "manufacturing": "high", "customer": "low"},
    "safetics": {"traction": "high", "team": "high", "market": "low", "moat": "low"},
    "dhive": {"trl": "low", "team": "high", "manufacturing": "high", "customer": "low"},
    "bitbyte": {"traction": "high", "team": "high", "market": "high", "moat": "low"},
    "nthing": {"trl": "low", "team": "high", "manufacturing": "high", "customer": "high"},
    "jobis": {"trl": "high", "team": "high", "manufacturing": "high", "customer": "low"},
    "palussmny": {"traction": "low", "team": "high", "market": "low", "moat": "low"},
    "wavedeck": {"traction": "high", "team": "high", "market": "high", "moat": "high"},
    "aroundus": {"traction": "high", "team": "high", "market": "low", "moat": "high"},
    "kkureogi": {"trl": "high", "team": "high", "manufacturing": "high", "customer": "high"},
    "avidbots": {"trl": "low", "team": "high", "manufacturing": "high", "customer": "high"},
    "cocoon": {"trl": "high", "team": "high", "manufacturing": "high", "customer": "high"},
    "levelzero": {"trl": "high", "team": "low", "manufacturing": "high", "customer": "high"},
    "unspun": {"trl": "high", "team": "high", "manufacturing": "high", "customer": "high"},
    "saasmetrics": {"traction": "low", "team": "high", "market": "high", "moat": "high"},
    "helpdocs": {"traction": "low", "team": "high", "market": "high", "moat": "high"},
}


# 격리 세션이 기록한 구체적 대안 레벨 (타이브레이크·경계 판정 축).
# 1차 분류 세션은 대안 레벨을 기록하지 않았다(요청이 완료 후 도착) —
# 아래는 작업 2-3 재분류 세션이 명시한 것만이다.
ALT: dict[str, dict[str, int]] = {
    "stillbright": {"trl": 5},
    "palussmny": {"traction": 3},
}


def unstable_of(key: str) -> dict[str, int]:
    """rules_v3.decide 용 경계 판정 입력 — Fable 분류의 자체 불확실성."""
    return ALT.get(key, {})


# 작업 2-3 재분류 결과 — 개선된 §3·§4 정의로 **불일치했던 30개 축만**
# 별도의 격리 세션이 다시 분류했다 (일치했던 축은 건드리지 않았다).
RECLASSIFIED: dict[str, dict[str, tuple[int | None, str]]] = {
    "cardmonster": {
        "traction": (3,
                    "'오프라인에서 게임을 검증'은 외부 검증 명시로 L2↔L3 판별 질문을 통과하나, 유료화 증거(MRR 등)는 '확인 필요'라 돈의 이동이 없어 L3 상한 — 규칙의 카드몬스터 예시 그대로 적용."),
    },
    "allsale": {
        "traction": (4,
                    "'중소 브랜드 대상 입점·물류·판매·마케팅 원스톱 실운영'은 무상 운영이 성립하지 않는 운영대행 모델이라 L3↔L4 판별 질문(돈의 이동)을 통과 — 규칙의 올세일 예시 그대로 L4."),
        "moat": (4,
                    "'미국 틱톡샵 공식 파트너사'(문서 명시)는 제3자가 이미 부여한 지위로 Moat L3↔L4 판별 질문의 '우위의 제3자 확인'에 해당 — 규칙의 올세일 예시 그대로 L4."),
    },
    "stillbright": {
        "trl": (3,
                    "'랩 스케일 공정 실증'은 단일 원리 실증인지 서브시스템 통합 프로토타입인지 서술로 확정 불가(프리시드 L3↔L5 판별 질문) — 규칙의 Still Bright 예시대로 낮은 쪽 L3 + 판정 불안정."),
        "manufacturing": (3,
                    "'기존 대비 최대 90% 저비용' 주장(문서 명시)은 원가 경로 인지를 보여주나 BOM 원가 모델·공급사/CM·DFM 확보는 미확인 → '인지하나 미정량' L3."),
    },
    "neptune": {
        "trl": (4,
                    "'실해역 운용 로봇'은 운용·실증 진행 중 서술이고 검증 완료 서술이 없어 시드 초기 L4↔L5 판별 질문에서 L4 — 규칙의 Neptune 예시 그대로 적용([후행] 상용 실적은 제외)."),
        "team": (None,
                    "'Entrepreneur First 출신'은 §4-1이 명시적으로 팀 경력의 근거가 아니라고 판정한 예시(프로그램 선발은 개인 경력이 아님)이고 개인 단위 이력 사실이 없어 확인 필요."),
        "manufacturing": (None,
                    "입주/지원 시점의 BOM·양산 파트너 사실이 전무하고 로봇 27대 가동 등은 [후행]이라 시점 귀속 규칙(§4-2)으로 제외 → 확인 필요."),
        "customer": (2,
                    "'연료 절감·CO2 감축 정량 가치 제안'은 상대방 특정 없는 세그먼트·가치 제안뿐이라 고객 L2 — 규칙의 Neptune 예시 그대로(Cargill·NYK는 [후행]이라 제외)."),
    },
    "safetics": {
        "market": (2,
                    "'협동로봇 충돌 안전 분석'은 사업 정의 자체가 협소 버티컬임을 확정하는 성격 판정(§4-4) — 규칙의 세이프틱스 예시 그대로 Market L2."),
    },
    "dhive": {
        "customer": (4,
                    "'수원시 자율주행 방범·물류 서비스 단계적 도입 예정'(문서 명시)은 특정 상대방의 도입 결정으로 고객 L2↔L3↔L4 판별 질문을 통과 — 규칙의 디하이브 예시 그대로 L4."),
    },
    "bitbyte": {
        "team": (None,
                    "'대표 안서형'은 이름만 있는 항목으로 §4-1이 명시한 '대표 이름만 있는 기업DB 항목' 유형 — 개인 단위 소속/직무/이력 사실이 없어 확인 필요."),
    },
    "nthing": {
        "team": (None,
                    "누적 381억 조달·삼성벤처 투자는 §4-1이 명시한 '회사의 조달·운영 실적'(엔씽 예시 그대로)으로 창업팀 경력 사실이 아니어서 확인 필요."),
        "manufacturing": (5,
                    "product_note '상용 제품 배치 중'(A 이후 하드웨어) — 모듈형 컨테이너 하드웨어의 상용 배치는 공급망·원가 모델 확보가 사업 정의상 필연적으로 따라오는 구조적 성격(§4-4)이라 L5."),
        "customer": (None,
                    "고객 특정 사실인 '중동(UAE) 프로젝트 수주'는 증거 등급 '추정'으로 문서 명시 미달이고, '상용 제품 배치 중'만으로는 외부 유료 고객(자가 운영 가능성 배제)이 확정되지 않아 확인 필요."),
    },
    "jobis": {
        "trl": (None,
                    "핀테크 순수 SW에 TRL 축은 물리적으로 적용 불가 — §4-3이 자비스앤빌런즈를 명시적 예시로 든 사안이라 재해석·강등 없이 확인 필요."),
        "team": (None,
                    "시리즈C 300억·프리IPO 추진은 §4-1이 명시한 회사 실적 유형('대규모 조달·상용 서비스 운영')으로 개인 단위 창업팀 경력 사실이 없어 확인 필요."),
    },
    "palussmny": {
        "traction": (2,
                    "product_note '서비스 운영 중'은 HelpDocs 예시('제품 운영 중' → 운영 사실뿐)와 같은 유형으로 외부 사용자가 사실로 명시되지 않았으나, 평판 커뮤니티라는 사업 정의가 외부 사용자 존재를 시사해 L2↔L3 확정 불가 — 타이브레이크로 낮은 쪽 + 판정 불안정."),
        "moat": (3,
                    "평판 커뮤니티는 축적형 데이터 자산의 존재가 정의상 필연이나 우위의 가시성(제3자 확인)은 미확인 — §4-4의 팔루썸니 예시 그대로 L3 상한."),
    },
    "aroundus": {
        "market": (None,
                    "'지역 기반 서비스'는 사업 내용 불명으로 정의가 시장 성격을 확정하지 못함 — §4-4가 어라운드어스를 명시적 예시로 든 사안이라 Market 확인 필요."),
    },
    "avidbots": {
        "trl": (4,
                    "HAX 공식 서술 '거친 프로토타입 상태로 입주'는 통합 프로토타입이 '존재한다(거칠다)'는 서술이고 동작·검증 서술이 없어 프리시드 L4↔L5 판별 질문에서 L4 — 규칙의 Avidbots 예시 그대로."),
        "team": (None,
                    "'공동창업자/CEO Faizan Sheikh'는 이름·직함만 있고 소속/이력이 특정된 개인 단위 경력 사실이 없어 §4-1 기준 미달 → 확인 필요."),
    },
    "cocoon": {
        "trl": (None,
                    "'HAX 랩 설비를 활용해 개발'은 입주 후 활동이라 시점 귀속 규칙(§4-2)의 Cocoon Carbon 예시 그대로 입주 시점 TRL 근거 불가이고, 입주 시점 TRL은 '확인 필요'로 명시 → null."),
    },
    "levelzero": {
        "team": (None,
                    "'Ula Rustamova / Irene Jia — Entrepreneur First 출신'은 §4-1이 명시한 대로 프로그램 선발 사실일 뿐 개인 단위 소속/직무/이력이 아니어서 확인 필요."),
    },
    "unspun": {
        "manufacturing": (None,
                    "BOM·공급사/CM·DFM 관련 사실이 전무하고 '창업팀·입주 시점 TRL·고객'이 모두 '확인 필요'라 양산 경로 축을 뒷받침하는 문서 명시 증거가 없어 확인 필요."),
    },
    "saasmetrics": {
        "team": (None,
                    "'팀 규모·공동창업자 구성'이 '확인 필요'이고 Leo Faria는 이름만 있어 개인 단위 이력 사실 부재 — §4-1 기준 미달 → 확인 필요."),
        "moat": (2,
                    "구독 지표 대시보드 SaaS는 전환비용 낮음이 사업 정의에서 확정되는 구조적 성격 — §4-4의 SaaSMetrics Moat L2 예시 그대로 적용."),
    },
    "helpdocs": {
        "traction": (2,
                    "product_note '제품 운영 중'은 운영 사실뿐이고 외부 사용자·매출이 사실로 명시되지 않아('확인 필요') L2↔L3 판별 질문에서 L2 — 규칙의 HelpDocs 예시 그대로."),
        "market": (None,
                    "덱 미제출 상태에서 시장 논증 판정 불가이고 '지식베이스 SaaS 시장은 크다'류 언급만으로 L3을 주는 것은 Market 상향 금지 규칙의 HelpDocs 예시 그대로 금지 → 확인 필요."),
        "moat": (2,
                    "문서화(지식베이스) SaaS는 전환비용 낮음이 정의에서 확정(§4-4 HelpDocs 예시)되고 '업계 인적 네트워크 부재' 자평(문서 명시)이 이를 보강 → L2."),
    },
}
