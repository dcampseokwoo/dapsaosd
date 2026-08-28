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
  excluded_therapeutics : 치료제·신약·백신 자체개발(v6 — 하드테크 아님, 발송 제외)
  not_a_startup   : 분류상 비스타트업
"""
from __future__ import annotations

from engine import engine_classify, engine_dedup, engine_core, engine_exclude, engine_snapshot, engine_stage

# DB로 검증 불가한 공고 핵심 요건(모든 통과 판정에 함께 출력 — §0/§6)
UNVERIFIABLE = ["Lab-scale 프로토타입", "미국 진출 의지(타겟국가 98% 결측)",
                "창업자·CTO 기술 전문성·특허"]


def _stage_note(target: str) -> list[str]:
    notes = list(UNVERIFIABLE)
    if "미국" not in (target or ""):
        pass  # 이미 UNVERIFIABLE 에 포함
    return notes


def tier(disposition: str, cls: dict) -> str:
    """발송 리스트 우선순위 티어(컬럼). T1 최우선 → T3 후순위."""
    if disposition != "send":
        return "—"
    v, conf = cls.get("verdict"), cls.get("confidence")
    flagged = cls.get("consumer_facing_end_product") or bool((cls.get("maturity_signal") or "").strip())
    if v == "hardtech" and conf == "high" and not flagged:
        return "T1"
    if v == "hardtech":
        return "T2"          # hardtech 인데 consumer_facing/maturity 플래그
    return "T3"              # unclear 또는 confidence low


def assess(entity: dict) -> dict:
    """엔티티 하나 → 최종 판정 dict. 목적: 배제 + 우선순위 정렬(제3의 '검토' 버킷 없음).

    disposition: send(발송 리스트) / excluded_entity / excluded_stage / excluded_field /
                 not_a_startup. 애매(unclear·저신뢰)는 배제하지 않고 send 에 넣어 T3 로 강등.
    """
    rec = {"biz_no": entity["biz_no"], "desc": entity.get("desc", "")}
    stage_b = engine_stage.stage_bucket(entity.get("stage"))
    excl, ereason = engine_exclude.entity_exclusion(entity)
    us = "미국" in (entity.get("target") or "")

    out = {**entity, "stage_bucket": stage_b, "unverifiable_requirements": UNVERIFIABLE}

    # 1) §4 배제 우선 (분류 불필요)
    if excl:
        out.update(disposition="excluded_entity", reason=ereason, tier="—")
        return out
    # 2) §3 스테이지 이탈. Pre-A(EXCEPTION)는 미국 아니면 여기서 이탈(분류 불필요).
    if stage_b == engine_stage.OUT_OF_SCOPE:
        out.update(disposition="excluded_stage", reason=f"스테이지 이탈({entity.get('stage')})", tier="—")
        return out
    if stage_b == engine_stage.EXCEPTION and not us:
        out.update(disposition="excluded_stage", reason="Pre-A 예외 미충족(미국 타겟 아님)", tier="—")
        return out
    # 3) 분류
    c = engine_core.classify(rec)
    out.update({f"cls_{k}": v for k, v in c.items()})
    v = c["verdict"]
    if v == "not_a_startup":
        out.update(disposition="not_a_startup", reason="분류: 비스타트업", tier="—")
        return out
    if v == "therapeutics":
        out.update(disposition="excluded_therapeutics",
                   reason="분류: therapeutics(치료제·신약·백신 자체개발 — 발송 제외)", tier="—")
        return out
    if v in ("software_only", "consumer"):
        out.update(disposition="excluded_field", reason=f"분류: {v}(공고 명시 배제)", tier="—")
        return out
    # Pre-A + 미국 이지만 물리제품 아니면 이탈
    if stage_b == engine_stage.EXCEPTION and not c.get("physical_product"):
        out.update(disposition="excluded_stage", reason="Pre-A 예외 미충족(물리제품 아님)", tier="—")
        return out
    # hardtech / unclear → 발송 리스트(unclear 는 T3 로 강등, 배제 아님)
    out["disposition"] = "send"
    out["tier"] = tier("send", c)
    out["reason"] = ("hardtech 발송" if v == "hardtech" else "unclear → 후순위(T3) 발송")
    # 상장/대형 의심(명시 목록) → 배제 아니라 플래그 + T3 강등(사용자 직접 판단)
    susp = engine_exclude.established_suspect(entity)
    if susp:
        out["established_suspect"] = susp
        out["tier"] = "T3"
        out["reason"] += f" | 상장/대형 의심({susp}) → T3"
    return out


def build(rows: list[dict] | None = None) -> list[dict]:
    rows = rows if rows is not None else engine_snapshot.load_rows()
    ents = engine_dedup.resolve_entities(rows)
    # 스테이지 통과 전 단계까지 전 엔티티 평가(리젝트 감사 §8 위해 전량 판정)
    return [assess(e) for e in ents]


def summarize(assessed: list[dict]) -> dict:
    from collections import Counter
    return dict(Counter(a["disposition"] for a in assessed).most_common())
