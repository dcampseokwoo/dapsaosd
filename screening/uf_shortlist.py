"""US FORGED — 최종 파이프라인 조립(배제 → 스테이지 → 분류 → Pre-A 확정).

목적: "명백히 부적합한 기업을 배제하고, 남은 기업을 설문 발송 우선순위대로 정렬"한다.
(선발이 아니다. 통과 판정에는 unverifiable_requirements 를 함께 낸다 — §6.)

파이프라인 순서(사용자 합의): §4 배제 → §3 스테이지 → §1 분류 → Pre-A 예외 확정.
disposition:
  outreach        : 발송 후보(hardtech, 스테이지 OK, 미배제)
  review          : 분류 unclear(저신뢰 — 사람 검토)
  excluded_entity : 해외법인·비스타트업 법인격(§4)
  excluded_stage  : 스테이지 이탈(시리즈A+·Pre-A 예외 미충족)
  excluded_field  : software_only / consumer (공고 명시 배제)
  not_a_startup   : 분류상 비스타트업
"""
from __future__ import annotations

from screening import uf_classify, uf_dedup, uf_engine, uf_exclude, uf_snapshot, uf_stage

# DB로 검증 불가한 공고 핵심 요건(모든 통과 판정에 함께 출력 — §0/§6)
UNVERIFIABLE = ["Lab-scale 프로토타입", "미국 진출 의지(타겟국가 98% 결측)",
                "창업자·CTO 기술 전문성·특허"]


def _stage_note(target: str) -> list[str]:
    notes = list(UNVERIFIABLE)
    if "미국" not in (target or ""):
        pass  # 이미 UNVERIFIABLE 에 포함
    return notes


def assess(entity: dict) -> dict:
    """엔티티 하나 → 최종 판정 dict(모든 필드 포함)."""
    rec = {"biz_no": entity["biz_no"], "desc": entity.get("desc", "")}
    c = uf_engine.classify(rec)
    stage_b = uf_stage.stage_bucket(entity.get("stage"))
    excl, ereason = uf_exclude.entity_exclusion(entity)

    out = {**entity, **{f"cls_{k}": v for k, v in c.items()},
           "stage_bucket": stage_b, "unverifiable_requirements": UNVERIFIABLE}

    # 1) §4 배제 우선
    if excl:
        out["disposition"] = "excluded_entity"; out["reason"] = ereason
        return out
    # 2) §3 스테이지 이탈
    if stage_b == uf_stage.OUT_OF_SCOPE:
        out["disposition"] = "excluded_stage"; out["reason"] = f"스테이지 이탈({entity.get('stage')})"
        return out
    # 3) 분류
    v = c["verdict"]
    if v == "not_a_startup":
        out["disposition"] = "not_a_startup"; out["reason"] = "분류: 비스타트업"
        return out
    if v in ("software_only", "consumer"):
        out["disposition"] = "excluded_field"; out["reason"] = f"분류: {v}"
        return out
    if v == "unclear":
        out["disposition"] = "review"; out["reason"] = "분류 불확실(저신뢰 — 사람 검토)"
        return out
    # v == hardtech → Pre-A 예외 확정
    if stage_b == uf_stage.EXCEPTION:
        if uf_stage.pre_a_bucket(entity.get("target", ""), c.get("physical_product")) != "stage_exception":
            out["disposition"] = "excluded_stage"
            out["reason"] = "Pre-A 예외 미충족(미국+물리제품 아님)"
            return out
    out["disposition"] = "outreach"; out["reason"] = "hardtech 발송 후보"
    return out


def build(rows: list[dict] | None = None) -> list[dict]:
    rows = rows if rows is not None else uf_snapshot.load_rows()
    ents = uf_dedup.resolve_entities(rows)
    # 스테이지 통과 전 단계까지 전 엔티티 평가(리젝트 감사 §8 위해 전량 판정)
    return [assess(e) for e in ents]


def summarize(assessed: list[dict]) -> dict:
    from collections import Counter
    return dict(Counter(a["disposition"] for a in assessed).most_common())
