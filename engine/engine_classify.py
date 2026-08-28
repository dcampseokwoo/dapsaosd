"""US FORGED — §1 소개문 기반 하드테크 분류 (LLM, 캐시 우선).

업종 라벨 화이트리스트를 폐기하고 **1줄 사업 소개**를 1차 판정 근거로 삼는다. 업종·기술은
프롬프트에 보조 신호로만 첨부하고 사전 필터링에 쓰지 않는다(감사 결함의 뿌리).

실행: 캐시 우선(A). 분류는 LLM(이 세션의 Claude/서브에이전트)이 1회 수행해 캐시에
고정하고, 엔진은 캐시를 결정적으로 읽는다. 캐시 키 = 사업자번호 + 소개문 해시 +
모델명 + 프롬프트 버전 (프롬프트를 고치면 옛 판정이 자동 무효화되게).

분류 순서(파이프라인): 배제(§4) → 스테이지(§3) → **LLM 분류(첫 하드테크 판정)**.
Pre-A 는 스테이지에서 '예외 후보'로만 들어오고, 분류의 physical_product 로 최종 확정한다.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE_PATH = ROOT / "data" / "cache" / "classification.json"

from engine import criteria_pack as _pack   # 활성 기준팩(공고 종속 데이터)

_CRIT = _pack.criteria()
# MODEL 은 캐시 키 구성요소 — 팩 교체와 무관하게 코드에 고정한다(1,159건 캐시 불변 보장, 변경 금지).
MODEL = "claude-agent"
PROMPT_VERSION = _CRIT["prompt_version"]        # 공고 종속 → criteria/<id>/criteria.json
PROGRAM_FIELDS = list(_CRIT["program_fields"])  # 모집 분야 enum(Other Deeptech·None 포함)
VERDICTS = tuple(_CRIT["verdicts"])

PROMPT = _pack.prompt_text()   # 전문: criteria/<id>/prompt.md


import re as _re

# 분류기가 자유 표기한 matched_program_field 를 공고 11개 분야로 정규화
_FIELD_MAP = [
    (r"robot", "Robotics/Automation"),
    (r"physical\s*ai|embodied", "Physical AI"),
    (r"aero|space|위성|우주|drone|satellite", "Aerospace"),
    (r"quantum|양자", "Quantum"),
    (r"semic|반도체|wafer|chip|photonic", "Semiconductor/Advanced Materials"),
    (r"material|소재|ceramic|세라믹|chemical|biomaterial|나노|nano", "Semiconductor/Advanced Materials"),
    (r"sensor|센서|iot|계측|측정|lidar|라이다", "Sensor/Edge Device"),
    (r"medical|헬스|health|의료|바이오\s*디바이스|wearable|진단|cgm|임플란트", "Healthtech Device"),
    (r"energy|배터리|batter|수소|hydrogen|태양|solar|climate|기후|탄소|carbon|ess|전지|storage", "Energy/Climate Tech"),
    (r"manufactur|제조|양산|공정|장비|설비|dfm|가공", "Advanced Manufacturing"),
    (r"industrial|산업용|하드웨어|hardware|기계|장치|module|모듈|전자부품|telecom|통신|display|광학", "Industrial Hardware"),
    (r"process", "Manufacturing Process Innovation"),
]
PROGRAM_FIELDS_SET = set(PROGRAM_FIELDS)


def normalize_field(raw: str) -> str:
    """자유 표기 → 공고 11개 분야 중 하나(불명확하면 Other Deeptech)."""
    if raw in PROGRAM_FIELDS_SET:
        return raw
    t = (raw or "").lower()
    for pat, canon in _FIELD_MAP:
        if _re.search(pat, t):
            return canon
    return "Other Deeptech"


def cache_key(biz_no: str, desc: str) -> str:
    """캐시 키 = 사업자번호 + 소개문 해시 + 모델. 프롬프트 버전은 키가 아니라 **항목 필드**로
    기록한다(v2/v3 선택적 재분류 혼재를 허용·추적). 소개문 해시가 서로 다른 회사를
    구분하므로 placeholder 사업자번호(해외법인 등)도 캐시에선 충돌하지 않는다."""
    h = hashlib.sha256((desc or "").encode("utf-8")).hexdigest()[:16]
    return f"{biz_no}|{h}|{MODEL}"


def load_cache() -> dict:
    if CACHE_PATH.exists():
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    return {}


def save_cache(cache: dict) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def get_cached(rec: dict, cache: dict | None = None) -> dict | None:
    cache = cache if cache is not None else load_cache()
    return cache.get(cache_key(rec.get("biz_no", ""), rec.get("desc", "")))


def put(rec: dict, verdict: dict, cache: dict) -> None:
    verdict.setdefault("prompt_version", PROMPT_VERSION)
    cache[cache_key(rec.get("biz_no", ""), rec.get("desc", ""))] = verdict


def render_input(rec: dict) -> dict:
    """분류기에 넣을 최소 입력(업종·기술은 보조 신호로만)."""
    return {"biz_no": rec.get("biz_no", ""), "name": rec.get("name_ko", ""),
            "1줄_사업_소개": rec.get("desc", ""),
            "업종_보조신호": rec.get("industry", ""), "기술_보조신호": rec.get("tech", "")}
