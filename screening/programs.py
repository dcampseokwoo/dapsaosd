"""프로그램 config — 단일 진실 소스(SSOT). 엔진의 '큰 틀' 안에서 바뀌는 부분만 여기 모음.

왜 이 파일
----------
매니저 요구: **큰 엔진 틀은 그대로 두고, 프로그램이 그때그때 바뀌어도 이 설정만
살짝 고치면 돌아가게** 한다. 그래서 프로그램별로 달라지는 모든 기준 —
우선 섹터·제외 섹터·스테이지 정책·지원 요건 — 을 코드 곳곳이 아니라 이 딕셔너리
한 곳에 선언한다. 라우터(router_v4)·게이트(disqualifiers)·종합판정(engine_programs)이
전부 이 config 를 읽는다.

새 프로그램을 추가하려면: PROGRAMS 에 항목 하나 추가(섹터·스테이지·요건 선언)하면
끝 — 로직 코드는 건드리지 않는다.

섹터 키는 sectors.TAXONOMY 의 **표준키**를 쓴다(자유텍스트 금지) — 섹터가 엔진의
단일 진실 소스가 되도록.

라벨 비의존: 값은 전부 프로그램 공식 정의에서 왔고 합불 분포 튜닝이 아니다.
"""
from __future__ import annotations

# 스테이지 정책 값: "FAIL"(확정 탈락) / "HUMAN"(경계·사람검토) / "OK"(통과)
# 스테이지 밴드: "scaleup"(시리즈B+) / "series_a" / "early"(시드~프리A) / "unknown"

PROGRAMS: dict[str, dict] = {
    "500": {
        "name": "500 Global Flagship",
        "target": "MVP + 유료고객/활성유저, 섹터 무관(주력 SaaS·핀테크·AI)",
        "form": "4개월 실리콘밸리 상주 · 영어 전용",
        "axes": ("traction", "team", "market", "moat"),
        "weights": "트랙션40·팀30·시장20·해자10",
        # --- 섹터 정책 (표준키) : 500 은 섹터 무관 catch-all. 우선섹터는 참고용.
        "sector_first": True,             # 라우팅 섹터 우선 적용
        "target_sectors": ["핀테크", "AI·데이터", "SaaS·B2B", "커머스·리테일",
                            "콘텐츠·게임", "헬스케어SW", "모빌리티·물류", "에듀테크"],
        "excluded_sectors": [],           # 섹터로 탈락시키지 않음(섹터 무관)
        # --- 스테이지 정책 (사람검토 폐지: 시리즈A 는 탈락 아님 → 메일 대상으로 흡수)
        "stage_policy": {"scaleup": "FAIL", "series_a": "OK", "early": "OK"},
        # --- 지원 요건 (확인된 사실이 어길 때만 확정 탈락; 미확인은 설문/조건부)
        "requirements": {
            "language": True,      # 영어 전용
            "product": True,       # 동작 프로토타입/실물
            "commit": True,        # 풀타임·이주
            "priced_conflict": False,
        },
    },
    "hax": {
        "name": "HAX (SOSV)",
        "target": "프리시드~시드 하드테크(기후·산업자동화·로보틱스·소재·헬스HW)",
        "form": "120일 뉴어크 핸즈온 · 캡 없는 SAFE + 지분 ~10%",
        "axes": ("trl", "team", "manufacturing", "customer"),
        "weights": "TRL40·팀30·양산경로20·고객10",
        "sector_first": True,
        "target_sectors": ["로보틱스·자동화", "소재·나노", "배터리·에너지",
                            "우주·항공", "기후·환경", "반도체", "제조·장비",
                            "의료기기·헬스HW"],
        # HAX 절대 제외 섹터(표준키) — 확인 가능한 하드 디스퀄
        "excluded_sectors": ["핀테크", "크립토·블록체인", "커머스·리테일", "보안"],
        # 프리시드~시드 전용: 시리즈A 부터 탈락
        "stage_policy": {"scaleup": "FAIL", "series_a": "FAIL", "early": "OK"},
        "requirements": {
            "language": True,
            "product": True,
            "commit": False,       # 이주 요건 아님
            "priced_conflict": True,   # 캡 없는 SAFE·지분10% 수용 필요
        },
    },
}


def get(track: str) -> dict | None:
    return PROGRAMS.get(track)


def excluded_sectors(track: str) -> list[str]:
    p = PROGRAMS.get(track)
    return list(p["excluded_sectors"]) if p else []


def target_sectors(track: str) -> list[str]:
    p = PROGRAMS.get(track)
    return list(p["target_sectors"]) if p else []
