"""공고 무관 기업 도시에(Dossier) — 축별 독립 '사실' 기록 (Phase 2 스키마).

■ 왜 존재하는가
verdict(hardtech/consumer/software_only/therapeutics)는 **US FORGED 모양의 답**이다. 소비재
공모전이면 consumer 가 정답이 된다 — 공고가 바뀌면 1,159건을 전부 다시 분류해야 한다.
도시에는 그 대신 **공고 무관한 사실**을 축별로 기록한다. "이 회사가 물리적 제품을 직접
만드는가"는 US FORGED 든 후지츠든 같은 답이다. 한 번 만들면 영원히 쓴다.
공고별 판정(tier·배제)은 이 사실 위에 규칙(fit_rules)을 얹어 산출한다 — 그건 Phase 6.

■ 이번 Phase 의 범위 (Phase 2)
- 도시에는 **읽기 전용 파생물**로 시작한다. 파이프라인은 여전히 classification.json 을 쓴다.
- classification.json 에서 **유도 가능한 축만** 파생한다(LLM 0회). 유도 불가 축은
  UNCLEAR + needs_generation=True 로 남긴다(전량 생성은 Phase 4).
- 캐시 키 3상수(biz_no|desc_sha256[:16]|MODEL)는 건드리지 않는다. 도시에는
  data/cache/dossier/ 에 별도 저장 — classification.json 은 롤백 경로로 그대로 둔다.

■ 축별 값(enum)
각 축은 {value, evidence(근거 원문), source, needs_generation} 를 갖는다. 독립 판정.

■ end_use 정의 (규칙 v3 의 핵심 — 반드시 이 정의로)
end_use 는 **"누구에게 파는가"가 아니라 "이 제품이 최종적으로 기여하는 것이 무엇인가"**.
  - 제일저지: 의류 브랜드에 원단을 팔지만 최종 기여는 개인의 의복 → PERSONAL
  - 크레신:   오디오 브랜드에 ODM 납품하지만 최종 기여는 개인의 음악 감상 → PERSONAL
  - 코리아인스트루먼트: 프로브카드가 반도체 생산 공정에 쓰임 → INDUSTRIAL
이 정의가 아니라 "누구에게 파는가"로 읽으면 소비재 부품사가 전부 INDUSTRIAL 로 통과한다.
(RULES_v3.md 의 Q1 정의와 동일.)
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOSSIER_DIR = ROOT / "data" / "cache" / "dossier"
DOSSIER_PATH = DOSSIER_DIR / "dossiers.json"   # classification.json 과 별도(롤백 경로 보존)

# ── 축 enum ────────────────────────────────────────────────────────────────
PHYSICAL_PRODUCT = ("YES", "SOFTWARE_ONLY", "SERVICE", "UNCLEAR")
TECH_OWNERSHIP = ("OWN", "RESELL_OR_INTEGRATE", "PARTNER_MENTION", "UNCLEAR")
VALUE_CHAIN_POSITION = ("MATERIAL", "COMPONENT", "EQUIPMENT", "FINISHED_GOODS",
                        "CONTRACT_MFG", "PLATFORM", "UNCLEAR")
END_USE = ("INDUSTRIAL", "MEDICAL_CLINICAL", "RESEARCH", "DEFENSE_PUBLIC",
           "PERSONAL", "MIXED", "UNCLEAR")
MATURITY = ("EARLY", "GROWTH", "ESTABLISHED", "LISTED", "UNCLEAR")
REGULATORY_CLASS = ("NONE", "MEDICAL_DEVICE", "DRUG", "FOOD", "COSMETIC",
                    "DEFENSE", "MULTIPLE", "UNCLEAR")
MARKET_ORIENTATION = ("DOMESTIC", "US", "JAPAN", "EU", "GLOBAL", "UNCLEAR")
# industry_domains 는 enum 이 아니라 중립 태그 배열(자유).

AXES = ("physical_product", "tech_ownership", "value_chain_position", "end_use",
        "industry_domains", "maturity", "regulatory_class", "market_orientation")

SCHEMA_VERSION = "dossier-v1"


def _axis(value, evidence="", source="derived:classification", needs_generation=False) -> dict:
    return {"value": value, "evidence": evidence, "source": source,
            "needs_generation": needs_generation}


# ── 유도(파생) 변환: classification.json 항목 → 도시에 (LLM 0회, 읽기 전용) ──
def derive(entry: dict, row: dict | None = None, *,
           is_listed: bool = False, is_suspect: bool = False,
           stage_bucket: str | None = None,
           normalize_field=None) -> dict:
    """기존 분류 항목(entry) + 스냅샷 행(row) → 도시에 dict.

    유도 가능한 축만 값으로 채우고, 불가 축은 UNCLEAR + needs_generation=True.
    normalize_field: engine_classify.normalize_field 주입(자유표기→11 enum). None 이면 원값.
    """
    vd = entry.get("verdict")
    pp = entry.get("physical_product")
    cf = entry.get("consumer_facing_end_product")
    ev = entry.get("evidence", "") or ""
    mat_sig = (entry.get("maturity_signal") or "").strip()
    raw_field = entry.get("matched_program_field", "") or ""
    field = normalize_field(raw_field) if normalize_field else raw_field
    tgt = ((row or {}).get("target") or "").strip()
    cb = ((row or {}).get("industry") or "").strip()

    ax: dict[str, dict] = {}

    # physical_product
    if vd == "software_only":
        ax["physical_product"] = _axis("SOFTWARE_ONLY", ev)
    elif vd == "therapeutics":
        ax["physical_product"] = _axis("YES", ev)          # 약(물질)도 물리적 제품
    elif pp is True:
        ax["physical_product"] = _axis("YES", ev)
    elif vd == "not_a_startup":
        ax["physical_product"] = _axis("UNCLEAR", ev)
    else:
        ax["physical_product"] = _axis("UNCLEAR", ev, needs_generation=True)  # SERVICE 분리 필요

    # tech_ownership — 기존에 저장 안 됨. OEM/수탁 단서만 부분 유도.
    if mat_sig and ("OEM" in mat_sig or "ODM" in mat_sig or "수탁" in mat_sig):
        ax["tech_ownership"] = _axis("RESELL_OR_INTEGRATE", mat_sig)
    else:
        ax["tech_ownership"] = _axis("UNCLEAR", "", needs_generation=True)

    # value_chain_position — 부분 유도(완제품/수탁 단서), 그 외 생성 필요.
    if cf is True and pp is True:
        ax["value_chain_position"] = _axis("FINISHED_GOODS", ev)
    elif mat_sig and "수탁" in mat_sig:
        ax["value_chain_position"] = _axis("CONTRACT_MFG", mat_sig)
    else:
        ax["value_chain_position"] = _axis("UNCLEAR", "", needs_generation=True)

    # end_use — 개인 최종기여(consumer_facing/consumer)만 확정. B2B 세부(산업/의료/연구/국방)는 생성 필요.
    if cf is True or vd == "consumer":
        ax["end_use"] = _axis("PERSONAL", ev)
    elif field == "Healthtech Device":
        ax["end_use"] = _axis("MEDICAL_CLINICAL", ev, needs_generation=True)  # 임상/연구/산업 구분 재확인
    else:
        ax["end_use"] = _axis("UNCLEAR", "", needs_generation=True)

    # industry_domains — 중립 태그 배열. field + CB 라벨로 시드.
    tags = []
    if field and field not in ("None", ""):
        tags.append(field)
    if cb:
        tags.append(f"CB:{cb}")
    ax["industry_domains"] = _axis(tags, "", source="derived:classification+snapshot")

    # maturity — 명시배제(상장)·suspect·스테이지로 유도. 스테이지는 신뢰 낮음(주의).
    if is_listed:
        ax["maturity"] = _axis("LISTED", "config: 명시 배제(상장)", source="derived:config")
    elif is_suspect:
        ax["maturity"] = _axis("ESTABLISHED", "config: established_suspect", source="derived:config")
    elif stage_bucket == "IN_SCOPE":
        ax["maturity"] = _axis("EARLY", f"stage={row.get('stage') if row else ''}", source="derived:snapshot")
    elif stage_bucket == "OUT_OF_SCOPE":
        ax["maturity"] = _axis("GROWTH", f"stage={row.get('stage') if row else ''}", source="derived:snapshot")
    else:
        ax["maturity"] = _axis("UNCLEAR", "", source="derived:snapshot", needs_generation=True)

    # regulatory_class — DRUG(therapeutics)·MEDICAL_DEVICE(Healthtech) 만 확정.
    if vd == "therapeutics":
        ax["regulatory_class"] = _axis("DRUG", ev)
    elif field == "Healthtech Device":
        ax["regulatory_class"] = _axis("MEDICAL_DEVICE", ev, needs_generation=True)
    else:
        ax["regulatory_class"] = _axis("UNCLEAR", "", needs_generation=True)  # NONE/COSMETIC/FOOD/DEFENSE 분리

    # market_orientation — 타겟 국가(98.5% 결측 → 대부분 UNCLEAR).
    if "미국" in tgt or "US" in tgt.upper():
        ax["market_orientation"] = _axis("US", tgt, source="derived:snapshot")
    elif tgt:
        ax["market_orientation"] = _axis("GLOBAL", tgt, source="derived:snapshot", needs_generation=True)
    else:
        ax["market_orientation"] = _axis("UNCLEAR", "", source="derived:snapshot", needs_generation=True)

    return {
        "biz_no": entry.get("biz_no") or (row or {}).get("biz_no", ""),
        "name_ko": (row or {}).get("name_ko", ""),
        "schema_version": SCHEMA_VERSION,
        "axes": ax,
        # provenance 는 결정적으로(타임스탬프 없이) — 재생성 시 diff 노이즈 방지. 시각은 코퍼스 _meta 에.
        "provenance": {
            "from": "classification.json",
            "prompt_version": entry.get("prompt_version"),
            "confidence": entry.get("confidence"),
        },
    }


# ── 검증용: 도시에 → 기존 verdict 역산 (스키마가 옛 판정을 담는지 확인) ──
def back_derive_verdict(dossier: dict) -> str:
    """도시에 축에서 기존 verdict 를 재구성. tech_ownership 없으면 개인 최종기여는 consumer
    로 본다(자체소재 소비재는 hardtech 이나 그 구분엔 tech_ownership 이 필요 → 갭 노출)."""
    ax = dossier["axes"]
    if ax["regulatory_class"]["value"] == "DRUG":
        return "therapeutics"
    phys = ax["physical_product"]["value"]
    if phys == "SOFTWARE_ONLY":
        return "software_only"
    if ax["end_use"]["value"] == "PERSONAL":
        return "consumer"
    if phys == "YES":
        return "hardtech"
    return "unclear"


# ── 코퍼스 I/O + 마이그레이션 (classification.json → dossiers.json, LLM 0회) ──
def load_corpus() -> dict:
    if DOSSIER_PATH.exists():
        return json.loads(DOSSIER_PATH.read_text(encoding="utf-8"))
    return {}


def save_corpus(corpus: dict) -> None:
    DOSSIER_DIR.mkdir(parents=True, exist_ok=True)
    DOSSIER_PATH.write_text(json.dumps(corpus, ensure_ascii=False, indent=2), encoding="utf-8")


def migrate() -> dict:
    """classification.json 전량 → 도시에 코퍼스(유도-only, 재분류 0). 결정적.

    키는 분류 캐시 키(biz_no|desc해시|MODEL) 그대로 → 1:1 대응·롤백 용이.
    반환: {'_meta':..., 'dossiers': {key: dossier}}. 파일로도 저장.
    """
    from engine import engine_classify as C, engine_snapshot as SN
    from engine import engine_exclude as EX, engine_stage as ST
    cache = C.load_cache()
    idx = SN.index_by_biz(SN.load_rows())
    known, susp = set(EX.KNOWN_EXCLUDED), set(EX.ESTABLISHED_SUSPECT)

    dossiers = {}
    for key, entry in cache.items():
        biz = key.split("|")[0]
        row = (idx.get(biz) or [None])[0]
        try:
            sb = ST.stage_bucket((row or {}).get("stage"))
        except Exception:
            sb = None
        dossiers[key] = derive(entry, row, is_listed=biz in known, is_suspect=biz in susp,
                               stage_bucket=sb, normalize_field=C.normalize_field)

    corpus = {
        "_meta": {
            "schema_version": SCHEMA_VERSION,
            "source": "classification.json",
            "count": len(dossiers),
            "migrated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "note": "유도-only(LLM 0). needs_generation=True 축은 Phase 4 생성 대상.",
        },
        "dossiers": dossiers,
    }
    save_corpus(corpus)
    return corpus


def coverage(corpus: dict | None = None) -> dict:
    """축별 needs_generation 건수 + 역산 일치율 리포트."""
    import collections
    corpus = corpus if corpus is not None else load_corpus()
    dossiers = corpus.get("dossiers", {})
    needgen = collections.Counter()
    for d in dossiers.values():
        for a, rec in d["axes"].items():
            if rec.get("needs_generation"):
                needgen[a] += 1
    return {"total": len(dossiers), "needs_generation": dict(needgen)}
