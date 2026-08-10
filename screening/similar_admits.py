"""유사 합격사 매칭 (원 설계서 모듈 4) — 점수화 대상에 비슷한 500/HAX 합격사 제시.

리서치 최대 공백이던 '합격자 프로필'을 수동이 아니라 기능으로 해결한다. 우리가
수집한 **실제 500·HAX 포트폴리오/합격사**를 풀로 삼아, 지원사와 트랙·스테이지·섹터가
비슷한 합격 사례를 붙여 담당자 판단을 돕는다(비교는 **동일 트랙·동일 스테이지 밴드**
우선).

풀 출처: data/portfolio_500.json(실제 500 투자 15) + portfolio_hax.json(실제 HAX 12)
        + dataset 의 admitted 8개사. 합불 라벨을 컷오프 튜닝에 쓰지 않는다 — 사람에게
        보여주는 참고 사례일 뿐이다.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"

# 섹터·소개에서 뽑는 카테고리 태그 (매칭 신호)
_TAGS = {
    "로봇": r"로봇|robot|로보틱스", "소재": r"소재|material|정련|나노|섬유",
    "배터리·에너지": r"배터리|batter|수소|hydrogen|에너지|energy|태양광|solar|전지",
    "우주": r"우주|위성|satellite|space|추력|aerospace",
    "기후·환경": r"기후|climate|탄소|carbon|온실가스|재활용|친환경|sustainab",
    "바이오·의료HW": r"바이오|bio|의료|medical|헬스|health|진단|센서\s*진단|호르몬",
    "핀테크": r"핀테크|fintech|결제|payment|대출|보험|송금",
    "커머스": r"커머스|commerce|이커머스|유통|리테일|쇼핑|판매|틱톡",
    "AI·데이터": r"\bai\b|인공지능|빅데이터|데이터\s*분석|llm|ml\b",
    "게임·엔터": r"게임|game|엔터|버추얼|아이돌|웹툰|미디어|콘텐츠",
    "교육": r"교육|edu|학원|학습",
    "SaaS·B2B": r"saas|b2b|솔루션|플랫폼|자동화|관리",
    "제조·양산": r"제조|manufactur|양산|공정|장비|설비|모터|반도체",
}


def _tagset(text: str) -> set[str]:
    t = (text or "").lower()
    return {name for name, pat in _TAGS.items() if re.search(pat, t)}


def _load_pool() -> list[dict]:
    pool = []
    for f, prog in (("portfolio_500.json", "500"), ("portfolio_hax.json", "hax")):
        for k, v in json.loads((DATA / f).read_text(encoding="utf-8")).items():
            blob = v.get("sector", "") + " " + " ".join(
                x[0] for x in v.get("facts", []))
            pool.append({"name": v["name"], "track": prog,
                         "stage": v.get("stage_band", ""),
                         "tags": _tagset(v.get("sector", "") + " " + blob)})
    # dataset admits
    try:
        from screening import dataset
        for c in dataset.COMPANIES:
            if c.ground_truth.startswith("admitted"):
                pool.append({"name": c.name, "track": c.track,
                             "stage": c.stage_band,
                             "tags": _tagset(c.sector_note)})
    except Exception:
        pass
    return pool


_POOL = None


def pool() -> list[dict]:
    global _POOL
    if _POOL is None:
        _POOL = _load_pool()
    return _POOL


def match(track: str, sector: str, desc: str, stage: str, n: int = 3) -> list[dict]:
    """동일 트랙 합격사 중 태그·스테이지 유사도 상위 n개. track 이 500/hax 아니면 []."""
    if track not in ("500", "hax"):
        return []
    cand = _tagset((sector or "") + " " + (desc or ""))
    band = (stage or "").strip()
    out = []
    for a in pool():
        if a["track"] != track:
            continue
        overlap = cand & a["tags"]
        score = len(overlap) * 2
        if band and a["stage"] and band == a["stage"]:
            score += 1
        if score <= 0:
            continue
        out.append({"name": a["name"], "score": score,
                    "shared": sorted(overlap), "stage": a["stage"]})
    out.sort(key=lambda x: -x["score"])
    return out[:n]


def match_str(track: str, sector: str, desc: str, stage: str, n: int = 3) -> str:
    ms = match(track, sector, desc, stage, n)
    if not ms:
        return "유사 합격사 미확인" if track in ("500", "hax") else "—"
    return " / ".join(f"{m['name']}({'·'.join(m['shared']) or '스테이지'})"
                      for m in ms)
