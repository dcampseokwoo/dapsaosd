"""표준 섹터 분류 축 (canonical sector taxonomy) — 엔진의 척추.

왜 이 모듈
----------
미국(500·HAX)은 VC 성격상 **섹터 우선 분류**가 핵심이다(일본은 기업 우선). 그런데
섹터를 라우팅 1순위 신호로 쓰려면, DB 의 자유텍스트 업종 필드가 표준화돼야 한다:

    "핀테크" / "금융" / "fintech" / "결제 서비스"  → 전부 표준키 `핀테크`(500 트랙)
    "로봇" / "로보틱스" / "산업용 로봇" / "robotics"  → 전부 표준키 `로보틱스·자동화`(HAX)

이 모듈은 (1) 표준 섹터 카테고리 목록(TAXONOMY)과 (2) 지저분한 텍스트를 표준키로
매핑하는 정규화 함수(classify/track_scores/primary)를 제공한다. 라우터·게이트·
프로그램 config·유사합격사 매칭이 모두 이 표준키를 공유한다 — 섹터가 엔진 전체의
단일 진실 소스가 되도록.

라벨 비의존: 트랙 매핑은 프로그램 공식 정의(HAX=하드테크, 바이오 치료제=IndieBio,
그 외=500)에서 나온 것이지 합불 분포 튜닝이 아니다.
"""
from __future__ import annotations

import re

# ---------------------------------------------------------------- 표준 섹터 축
# key(표준키): (표시명, 트랙, 정규식)
#   트랙 ∈ {"hax"(하드테크), "500"(SW·서비스), "bio"(치료제 → IndieBio)}
# 순서는 우선순위(먼저 매칭된 것이 primary 후보). 하드테크·치료제를 앞에 둔다 —
# "AI 로봇"처럼 SW 수식어가 붙어도 물리 실체(로봇)를 우선 인식하기 위해.
TAXONOMY: dict[str, tuple[str, str, str]] = {
    # ---- 바이오 치료제 (→ IndieBio) : 신약·치료제 개발만. 진단·기기·디지털은 제외(BIO_BLOCK)
    "바이오치료제": ("바이오 치료제(신약)", "bio",
        r"신약|drug\s*discovery|신약개발|치료제|therapeut|항체|antibody|"
        r"백신|vaccine|mrna|면역항암|immuno-?onco|세포치료|cell\s*therapy|"
        r"유전자\s*치료|gene\s*therapy|줄기세포|stem\s*cell|바이오의약품|"
        r"biopharmaceutical|펩타이드\s*치료|peptide\s*drug"),

    # ---- 하드테크 (→ HAX)
    "로보틱스·자동화": ("로보틱스·자동화", "hax",
        r"로봇|robot|로보틱스|robotics|actuator|액추에이터|그리퍼|gripper|"
        r"산업\s*자동화|industrial\s*automation|자율\s*주행|무인\s*이송"),
    "소재·나노": ("소재·나노", "hax",
        r"신소재|소재\b|advanced\s*material|정련|smelt|나노|nano|"
        r"복합소재|composite|촉매|catalyst|광물|mineral|섬유\b"),
    "배터리·에너지": ("배터리·에너지", "hax",
        r"배터리|batter|이차전지|이차\s*전지|리튬|lithium|배터리\s*셀|"
        r"수소|hydrogen|수전해|electroly|연료전지|fuel\s*cell|"
        r"태양광|solar|풍력|wind\s*power|에너지\s*저장|\bess\b|전력\s*변환"),
    "우주·항공": ("우주·항공", "hax",
        r"우주|위성|satellite|space|aerospace|발사체|추력|thruster|"
        r"드론|drone|uav|도심\s*항공|uam"),
    "기후·환경": ("기후·환경", "hax",
        r"기후|climate|탄소\s*포집|carbon\s*capture|ccus|온실가스|"
        r"재활용|recycl|친환경\s*소재|sustainab|폐기물|waste\b"),
    "반도체": ("반도체", "hax",
        r"반도체|semiconductor|웨이퍼|wafer|칩\b|chip\b|파운드리|foundry|"
        r"전공정|후공정|패키징\s*장비"),
    "양자·퀀텀": ("양자·퀀텀", "hax",
        r"양자|퀀텀|quantum"),
    "Physical AI": ("Physical AI", "hax",
        r"physical\s*ai|피지컬\s*ai|임베디드\s*ai|엣지\s*디바이스|edge\s*device|"
        r"자율\s*주행|autonomous\s*driving"),
    "제조·장비": ("제조·장비", "hax",
        r"제조\s*장비|manufactur|양산\s*설비|공정\s*장비|장비\b|machinery|"
        r"모터|motor|변압기|transformer|플랜트|plant|3d\s*print|농기계|"
        r"스마트팜\s*장치|양식\s*장치"),
    "의료기기·헬스HW": ("의료기기·헬스HW", "hax",
        r"의료기기|medical\s*device|진단\s*기기|웨어러블|wearable|"
        r"바이오센서|biosensor|디바이스\b|device\b|임플란트|implant"),
    "센서·IoT": ("센서·IoT", "hax",
        r"센서|sensor|\biot\b|사물인터넷|계측|계장|스마트\s*센서"),

    # ---- SW·서비스 (→ 500, 섹터 무관 catch-all 이지만 우선섹터로 명시)
    "핀테크": ("핀테크", "500",
        r"핀테크|fintech|결제|payment|송금|remittance|대출|lending|"
        r"보험|insur|금융\b|financial|자산\s*관리|wealth"),
    "크립토·블록체인": ("크립토·블록체인", "500",
        r"블록체인|blockchain|crypto|암호화폐|가상자산|nft|web3|토큰\b"),
    "커머스·리테일": ("커머스·리테일", "500",
        r"커머스|commerce|이커머스|e-?commerce|유통|리테일|retail|"
        r"쇼핑|shopping|판매\s*플랫폼|d2c|틱톡\s*샵"),
    "보안": ("보안", "500",
        r"사이버\s*보안|cyber\s*security|정보\s*보안|정보보호|네트워크\s*보안|"
        r"엔드포인트\s*보안|보안\s*솔루션|보안\s*관제|infosec|침입\s*탐지|"
        r"penetration\s*test|암호화\s*솔루션"),
    "AI·데이터": ("AI·데이터", "500",
        r"\bai\b|인공지능|머신러닝|machine\s*learning|\bml\b|\bllm\b|"
        r"빅데이터|big\s*data|데이터\s*분석|analytics|생성형|generative"),
    "콘텐츠·게임": ("콘텐츠·게임", "500",
        r"게임|game|콘텐츠|content|미디어|media|웹툰|webtoon|영상|video|"
        r"엔터|버추얼|아이돌|메타버스|metaverse"),
    "에듀테크": ("에듀테크", "500",
        r"에듀|교육|education|이러닝|e-?learning|학습\b|learning\b|학원"),
    "헬스케어SW": ("헬스케어SW", "500",
        r"디지털\s*치료|digital\s*therapeut|디지털\s*헬스|digital\s*health|"
        r"헬스케어\s*플랫폼|의료\s*플랫폼|원격\s*진료|telemedicine|"
        r"건강\s*관리\s*앱"),
    "모빌리티·물류": ("모빌리티·물류", "500",
        r"모빌리티|mobility|배송|delivery|물류\s*플랫폼|라스트마일|"
        r"예약|booking|reservation|카셰어|ride\s*hail"),
    "SaaS·B2B": ("SaaS·B2B", "500",
        r"saas|b2b\b|솔루션|solution|플랫폼|platform|자동화\s*소프트웨어|"
        r"업무\s*자동화|워크플로|workflow|\bapi\b|대시보드|dashboard|"
        r"소프트웨어|software|\bapp\b|어플|구독|subscription"),
}

# 바이오 오분류 차단: 디지털 치료제·진단·의료기기·모니터링·SW·앱 은 IndieBio 아님.
BIO_BLOCK = re.compile(
    r"digital\s*therapeut|디지털\s*치료|진단|diagnos|의료기기|medical\s*device|"
    r"모니터링|monitoring|플랫폼|platform|소프트웨어|software|\bapp\b|앱\b|"
    r"웨어러블|wearable")

# 섹터 필드가 대략적 바이오(치료제 문맥일 때만 가산)
_BIO_SECTOR = re.compile(r"\bbio\b|biotech|pharma|제약|바이오\b")

_COMPILED = {k: (disp, tr, re.compile(pat)) for k, (disp, tr, pat) in TAXONOMY.items()}


def classify(text: str) -> list[str]:
    """텍스트에서 매칭되는 표준 섹터 키 목록(TAXONOMY 정의 순서 = 우선순위)."""
    t = (text or "").lower()
    if not t.strip():
        return []
    return [k for k, (_disp, _tr, rx) in _COMPILED.items() if rx.search(t)]


def primary(text: str) -> str | None:
    """가장 우선하는 표준 섹터 키(없으면 None)."""
    ks = classify(text)
    return ks[0] if ks else None


def display(key: str) -> str:
    return TAXONOMY.get(key, ("—",))[0]


def track_of(key: str) -> str | None:
    v = TAXONOMY.get(key)
    return v[1] if v else None


def track_scores(text: str) -> dict[str, float]:
    """텍스트가 각 트랙(hax/500/bio)으로 얼마나 지지되는지 — 매칭된 표준 섹터 수."""
    sc = {"hax": 0.0, "500": 0.0, "bio": 0.0}
    for k in classify(text):
        sc[TAXONOMY[k][1]] += 1.0
    return sc


# ================================================================ 업종(CB 그룹) 축
# **업종 ≠ 분야.** 업종 = Crunchbase 40개 그룹(거칠다). 분야 = 위 TAXONOMY(세밀,
# 사업 실체). 업종은 소개가 비어도 채워지는 거친 사전분류(prior)일 뿐이고, 실제
# 라우팅·탈락 판정은 **분야**가 authoritative 하다. 둘이 어긋나면(예: 업종=Hardware인데
# 분야=커머스) 그 자체가 신호다.
#
# CB 그룹(ENG) → (분야 표시명, 거친 트랙). 트랙: hax(하드테크)만 배타적 좁은 축이고
# 500 은 섹터 무관 catch-all. bio(IndieBio)는 코스로 확정하지 않고 분야에서 치료제가
# 확인될 때만 발동한다(Biotechnology 그룹도 진단·기기·플랫폼이면 bio 아님).
CB_GROUP: dict[str, tuple[str, str]] = {
    # ---- 하드테크(HAX 거친 prior)
    "hardware": ("하드웨어", "hax"),
    "manufacturing": ("제조·양산", "hax"),
    "science and engineering": ("과학·엔지니어링", "hax"),
    "science & engineering": ("과학·엔지니어링", "hax"),
    "sustainability": ("기후·환경", "hax"),
    # ---- 그 외(500 catch-all). 분야명은 참고 표시용.
    "agriculture and farming": ("농업·AgTech", "500"),
    "artificial intelligence": ("AI·데이터", "500"),
    "biotechnology": ("바이오", "500"),      # 치료제면 분야에서 bio 발동
    "bio": ("바이오", "500"),
    "blockchain & cryptocurrency": ("크립토·블록체인", "500"),
    "clothing and apparel": ("패션·의류", "500"),
    "commerce and shopping": ("커머스·리테일", "500"),
    "community and lifestyle": ("커뮤니티·라이프", "500"),
    "pet": ("펫", "500"),
    "kids": ("키즈·출산", "500"),
    "consumer goods": ("소비재", "500"),
    "beauty/cosmetic": ("뷰티", "500"),
    "publishing": ("출판", "500"),
    "entertainment/art": ("엔터·예술", "500"),
    "video": ("비디오", "500"),
    "audio": ("오디오", "500"),
    "media": ("미디어", "500"),
    "data and analytics": ("AI·데이터", "500"),
    "design": ("디자인", "500"),
    "education": ("에듀테크", "500"),
    "events": ("행사·이벤트", "500"),
    "financial services": ("핀테크", "500"),
    "food and beverage": ("식음료", "500"),
    "food & beverage": ("식음료", "500"),
    "game": ("콘텐츠·게임", "500"),
    "government and military": ("정부·국방", "500"),
    "healthcare": ("헬스케어", "500"),       # 기기면 분야에서 hax
    "navigation and mapping": ("지도·측위", "500"),
    "privacy and security": ("보안", "500"),
    "professional services": ("전문서비스", "500"),
    "hr": ("HR", "500"),
    "real estate": ("부동산", "500"),
    "sales and marketing": ("세일즈·마케팅", "500"),
    "sales & marketing": ("세일즈·마케팅", "500"),
    "software": ("소프트웨어", "500"),
    "sports": ("스포츠", "500"),
    "logistics": ("물류", "500"),
    "mobility": ("모빌리티", "500"),
    "travel and tourism": ("여행", "500"),
}


def cb_group(sector_raw: str) -> tuple[str, str] | None:
    """업종(CB) 원문 → (분야 prior 표시명, 거친 트랙). 다중값이면 첫 그룹 사용."""
    s = (sector_raw or "").strip().lower()
    if not s:
        return None
    first = re.split(r"[;,/]", s)[0].strip()
    return CB_GROUP.get(first) or CB_GROUP.get(s)


def field_of(sector_raw: str, tech: str, desc: str, svc: str = "") -> dict:
    """**분야 판정** — 업종(거친)과 분리해 사업 실체로 세밀 분야를 정한다.

    반환: {field, field_track, cb_group, cb_track, mismatch, bio}
      - field/field_track: 분야(세밀) 표시명·트랙 (라우팅·탈락의 authoritative 신호)
      - cb_group/cb_track: 업종(CB 그룹) prior 표시명·트랙 (참고·폴백)
      - mismatch: 업종 트랙 ≠ 분야 트랙 (신호)
      - bio: 치료제 확인(IndieBio 리퍼럴 대상)
    """
    fine_text = " ".join((desc or "", tech or "", svc or "")).lower()
    blob = " ".join((sector_raw or "", fine_text)).lower()
    fine_keys = classify(fine_text)
    cb = cb_group(sector_raw)
    cb_disp, cb_trk = cb if cb else (None, None)

    # 치료제(bio) — 분야에서 확인될 때만, 디지털·진단·기기·SW 면 차단
    bio = ("바이오치료제" in fine_keys) and not BIO_BLOCK.search(blob)

    fine_primary = fine_keys[0] if fine_keys else None
    if bio:
        field, ftrack = "바이오 치료제(신약)", "bio"
    elif fine_primary:
        field, ftrack = display(fine_primary), track_of(fine_primary)
    elif cb_disp:
        field, ftrack = cb_disp, cb_trk        # 소개가 비면 업종 prior 로 분야 추정
    else:
        field, ftrack = "미분류", None

    mismatch = bool(cb_trk and ftrack and cb_trk != ftrack and not bio)
    return {"field": field, "field_track": ftrack,
            "cb_group": cb_disp, "cb_track": cb_trk,
            "mismatch": mismatch, "bio": bio, "fine_keys": fine_keys}
