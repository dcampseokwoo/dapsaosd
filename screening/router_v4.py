"""v4 하이브리드 라우터 — 신호 가중 점수 + 자기불확실성 플래그.

v1~v3 의 라우팅은 첫 매칭 키워드로 트랙을 정하는 규칙(gbd_pipeline.route)이었다.
문제: (1) DB 의 tech 태그가 실제와 다르면 오분류(예: 메텍홀딩스 tech='소프트웨어'인데
실제는 메탄 캡슐 하드웨어), (2) 오분류를 '확신에 차서' 조용히 낸다.

v4 의 변경:
  1. **다신호 가중 점수** — 섹터/기술/소개(desc)/영문명을 각각 가중해 bio·hw·sw
     점수를 합산한다. desc(사업 실체) > tech 태그 > 섹터 순으로 가중.
  2. **자기불확실성 플래그** — 1·2위 점수 차가 작거나 신호가 상충하면
     `라우팅 불안정`으로 표시해 사람 확인으로 보낸다(조용한 오분류 방지).
  3. **입력 없음/부족 분리** — 신호가 0이면 '판정 불가(입력 없음)',
     신호가 약하면 '저신뢰 라우팅'.

이 층은 라벨을 보지 않는다. 키워드는 프로그램 정의(HAX=하드웨어/기후/로보틱스,
바이오 치료제=IndieBio, 그 외=500)에서 나온 것이며 합불 분포에 맞추지 않았다.
"""
from __future__ import annotations

import re

# (정규식, 가중치). desc 매칭은 이 가중치를 그대로, tech 는 ×0.7, 섹터는 ×0.5 로 적용.
HW_SIGNALS = [
    (r"로봇|robot", 3), (r"하드웨어|hardware", 3), (r"제조|manufactur|양산", 2),
    (r"반도체|semiconductor|칩|chip|wafer", 3), (r"소재|material", 2),
    (r"배터리|batter|이차전지|셀\b|리튬|lithium", 3), (r"수소|hydrogen|수전해|electroly", 3),
    (r"드론|drone|위성|satellite|우주|aerospace|추력|thruster", 3),
    (r"센서|sensor|웨어러블|wearable|디바이스|device|기기\b", 2),
    (r"장비|machinery|기계|설비|플랜트|plant|모터|motor|변압기|transformer", 2),
    (r"태양광|solar|풍력|wind\s*power|전기차|EV\b|캡슐|capsule", 2),
    (r"정련|smelt|광물|mineral|나노|nano|3d\s*print|양식\s*장치|농기계", 2),
    (r"로보틱스|robotics|actuator|그리퍼|gripper|반도체\s*장비", 3),
]
SW_SIGNALS = [
    (r"소프트웨어|software|saas|플랫폼|platform", 2), (r"\bapp\b|앱\b|어플", 2),
    (r"핀테크|fintech|결제|payment|송금", 2), (r"블록체인|blockchain|crypto|nft", 2),
    (r"콘텐츠|content|미디어|media|웹툰|webtoon|영상|video", 2),
    (r"광고|advertis|marketing|커머스|commerce|이커머스|e-?commerce", 2),
    (r"커뮤니티|community|매칭|matching|중개|brokerage", 2),
    (r"에듀|교육|education|학습|learning", 2), (r"게임|game(?!\s*엔진 하드)", 2),
    (r"ai|인공지능|빅데이터|big\s*data|데이터\s*분석|analytics", 1),
    (r"구독|subscription|saas|api|대시보드|dashboard", 2),
    (r"예약|booking|reservation|배송|delivery(?!\s*robot)", 1),
]
BIO_THERA_SIGNALS = [
    (r"신약|drug\s*discovery|신약개발", 4), (r"치료제(?!.*디지털)|therapeut(?!ic\s*app)", 3),
    (r"항체|antibody|백신|vaccine|mrna|면역항암|immuno-?onco", 4),
    (r"세포치료|cell\s*therapy|유전자\s*치료|gene\s*therapy|줄기세포|stem\s*cell", 4),
    (r"바이오의약품|biopharmaceutical|펩타이드\s*치료|peptide\s*drug|저분자화합물", 3),
]
# 바이오 오분류 차단 (디지털 치료제·진단·의료기기·SW 는 IndieBio 아님)
BIO_BLOCK = re.compile(
    r"digital\s*therapeut|디지털\s*치료|진단|diagnos|의료기기|medical\s*device|"
    r"모니터링|monitoring|플랫폼|platform|소프트웨어|software|\bapp\b|웨어러블")

CONF_MARGIN = 2.0   # 1·2위 점수 차가 이 값 미만이면 저신뢰(라우팅 불안정)


def _score(text: str, signals) -> float:
    return sum(w for pat, w in signals if re.search(pat, text))


def route(sector: str, tech: str, desc: str, name_en: str = "") -> dict:
    """다신호 가중 라우팅. 반환: track, confidence, scores, reason."""
    sector, tech, desc = (sector or "").lower(), (tech or "").lower(), (desc or "").lower()
    name_en = (name_en or "").lower()
    if not (sector or tech or desc or name_en):
        return {"track": "대상외", "confidence": "none",
                "scores": {}, "reason": "입력 없음 (업종·기술·소개 공란)"}

    # desc 가 사업 실체 → 가중 1.0, tech 태그 0.7, 섹터 0.5, 영문명 0.4
    def multi(signals):
        return (_score(desc, signals) * 1.0 + _score(tech, signals) * 0.7
                + _score(sector, signals) * 0.5 + _score(name_en, signals) * 0.4)

    hw, sw = multi(HW_SIGNALS), multi(SW_SIGNALS)
    bio = multi(BIO_THERA_SIGNALS)
    bio_sector = bool(re.search(r"\bbio\b|biotech|pharma|제약", sector))
    if bio_sector and not BIO_BLOCK.search(" ".join((sector, tech, desc))):
        bio += 2.0                         # 바이오 섹터 가산(치료제 문맥일 때만)
    if BIO_BLOCK.search(" ".join((tech, desc))):
        bio = 0.0                          # 디지털·진단·기기 → 바이오 제외

    scores = {"bio_routing": round(bio, 2), "hax": round(hw, 2), "500": round(sw, 2)}
    ranked = sorted(scores.items(), key=lambda x: -x[1])
    (t1, s1), (t2, s2) = ranked[0], ranked[1]

    if s1 == 0:
        return {"track": "판정 보류", "confidence": "low", "scores": scores,
                "reason": "신호 약함 — 업종·소개로 트랙 특정 불가(자료 요청)"}
    # 500 은 섹터 무관 기본값이므로, hw/bio 가 500 을 이기려면 마진 필요
    if t1 == "500":
        track, conf = "500", "high" if s1 - s2 >= CONF_MARGIN else "low"
    else:
        # hw/bio 가 최상위여도 sw 와 접전이면 불안정
        conf = "high" if s1 - s2 >= CONF_MARGIN else "low"
        track = t1
    reason = (f"{track} (bio {scores['bio_routing']} / hax {scores['hax']} / "
              f"500 {scores['500']})")
    if conf == "low":
        reason += " — 신호 접전, 라우팅 불안정(사람 확인 권장)"
    return {"track": track, "confidence": conf, "scores": scores, "reason": reason}
