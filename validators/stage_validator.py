"""스테이지 표기 정규화 + 보수적 반영 정책.

반영 정책:
- confidence=high            → G열 교체
- confidence=medium          → 기존 값이 공란/`알 수 없음`일 때만 기입
- confidence=low 또는 미검증 → 셀 변경 금지, 로그만
- 폐업/영업종료              → 스테이지 유지, 비고 기록
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import config

# 흔한 변형 표기 → 표준 표기
_ALIASES = {
    "pre seed": "Pre-seed", "preseed": "Pre-seed", "pre-seed": "Pre-seed",
    "seed": "Seed", "시드": "Seed", "엔젤": "Seed", "angel": "Seed",
    "pre a": "Pre-A", "pre-a": "Pre-A", "prea": "Pre-A",
    "pre series a": "Pre-A", "pre-series a": "Pre-A", "프리시리즈a": "Pre-A",
    "프리a": "Pre-A",
    "series a": "Series A", "시리즈a": "Series A", "a": "Series A",
    "series b": "Series B", "시리즈b": "Series B",
    "series c": "Series C", "시리즈c": "Series C",
    "series d": "Series D", "시리즈d": "Series D",
    "series e": "Series E ~", "series e ~": "Series E ~", "series e~": "Series E ~",
    "series f": "Series E ~", "series g": "Series E ~",
    "pre ipo": "Pre-IPO", "pre-ipo": "Pre-IPO",
    "알 수 없음": "알 수 없음", "알수없음": "알 수 없음", "unknown": "알 수 없음",
}

_TERMINAL_LOOSE_RE = re.compile(
    r"^(M&A|IPO)\s*\(\s*(~)?\s*['’]?\s*(\d{2}|\d{4})\s*\)$", re.IGNORECASE
)


def normalize_stage(raw: str) -> str | None:
    """자유 표기를 분류 체계 표준 표기로. 실패 시 None."""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    if s in config.STAGES or config.TERMINAL_STAGE_RE.match(s):
        return s
    m = _TERMINAL_LOOSE_RE.match(s)
    if m:
        kind = m.group(1).upper().replace("M&A", "M&A")
        kind = "M&A" if kind.startswith("M") else "IPO"
        tilde = m.group(2) or ""
        yy = m.group(3)[-2:]
        return f"{kind}({tilde}'{yy})"
    return _ALIASES.get(s.lower())


def is_terminal(stage: str) -> bool:
    """연도 확정 IPO/M&A — 조사 제외 대상."""
    return bool(stage and config.TERMINAL_STAGE_RE.match(str(stage).strip()))


# 스테이지별 라운드명 키워드 — 인용문(round_quote)에 이 중 하나가 문자 그대로
# 있어야 해당 스테이지 보고를 신뢰한다 (제목만 보고 추측하는 환각 차단)
_QUOTE_KEYWORDS = {
    "Pre-seed": ["프리시드", "pre-seed", "preseed", "프리 시드"],
    "Seed": ["시드", "seed", "엔젤", "angel"],
    "Pre-A": ["프리a", "프리 a", "프리시리즈a", "프리 시리즈a", "pre-a", "pre a",
              "프리에이", "시리즈a 브릿지"],
    "Series A": ["시리즈a", "series a", "시리즈 a"],
    "Series B": ["시리즈b", "series b", "시리즈 b"],
    "Series C": ["시리즈c", "series c", "시리즈 c"],
    "Series D": ["시리즈d", "series d", "시리즈 d"],
    "Series E ~": ["시리즈e", "series e", "시리즈f", "series f", "시리즈g", "series g"],
    "Pre-IPO": ["프리ipo", "pre-ipo", "pre ipo", "상장 전", "프리 아이피오"],
    "IPO": ["상장", "ipo", "코스닥", "코넥스", "거래소", "공모"],
    "M&A": ["인수", "합병", "m&a", "피인수", "매각"],
}


def check_round_quote(new_stage_raw: str, round_quote: str, confidence: str) -> tuple[str, str]:
    """인용문에 라운드명이 실제로 없으면 신뢰도를 low로 강등.

    반환: (조정된 confidence, 강등 사유 — 강등 없으면 빈 문자열)
    """
    stage = normalize_stage(new_stage_raw) or (new_stage_raw or "").strip()
    if not stage or stage == "알 수 없음" or confidence == "low":
        return confidence, ""
    key = stage
    m = config.STAGE_WITH_YEAR_RE.match(stage)
    if m:
        key = m.group(1)  # IPO('25) → IPO
    keywords = _QUOTE_KEYWORDS.get(key)
    if not keywords:
        return confidence, ""
    quote = (round_quote or "").replace(" ", "").lower()
    if not quote:
        return "low", "라운드명 인용 부재 — 신뢰도 자동 하향"
    # 하위 단계 표현이 상위 단계 키워드를 포함하는 경우 제거 후 매칭
    # (예: "프리시리즈A"가 "시리즈A"로 오인되는 것 방지)
    negatives = {
        "Series A": _QUOTE_KEYWORDS["Pre-A"],
        "Seed": _QUOTE_KEYWORDS["Pre-seed"],
        "IPO": _QUOTE_KEYWORDS["Pre-IPO"],
    }.get(key, [])
    cleaned = quote
    for n in negatives:
        cleaned = cleaned.replace(n.replace(" ", ""), "")
    if not any(k.replace(" ", "") in cleaned for k in keywords):
        return "low", f"인용문에 '{key}' 라운드명 없음 — 신뢰도 자동 하향"
    return confidence, ""


@dataclass
class Decision:
    apply: bool
    final_stage: str      # 반영 시 G열에 들어갈 값
    status: str           # 로그 시트 '반영 여부' 문구
    note: str = ""


def decide(current_stage: str, new_stage_raw: str, confidence: str,
           note: str = "") -> Decision:
    """검증 결과 → 반영 여부 결정 (보수적)."""
    current = (current_stage or "").strip()
    new_stage = normalize_stage(new_stage_raw)

    closed = any(k in (note or "") for k in ("폐업", "영업종료", "청산", "활동 중단"))

    if not new_stage:
        return Decision(False, current, "미반영(스테이지 판독 불가)", note)

    if closed:
        # 폐업/영업종료: 스테이지 유지, 비고에만 기록
        return Decision(False, current, "변경 없음(폐업/종료 — 비고 기록)", note)

    if new_stage == current:
        return Decision(False, current, "변경 없음", note)

    if confidence == "high":
        return Decision(True, new_stage, "반영", note)

    if confidence == "medium":
        if current in ("", "알 수 없음"):
            return Decision(True, new_stage, "반영(공란 채움, medium)", note)
        return Decision(False, current, "미반영(근거 부족)", note)

    return Decision(False, current, "미반영(low/미검증)", note)
