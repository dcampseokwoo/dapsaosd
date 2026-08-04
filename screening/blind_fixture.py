"""블라인드 재분류용 입력 생성기 — 작업 1-1.

  python -m screening.blind_fixture      # output/screening/blind_input.json 생성

dataset.COMPANIES 에서 **사실만** 추출한다. 다음은 절대 포함하지 않는다:
  levels, LEVELS_V2, FIT, ground_truth, unstable, note, fit_reason,
  sources, needs_confirm
(`note` 에는 정답이 적혀 있고, `levels`/`LEVELS_V2` 는 기존 분류자의 답안이다.
 이 중 하나라도 새어들면 블라인드 측정이 오염된다 — test_blind_input_has_no_leak
 가 이를 고정한다.)
"""
from __future__ import annotations

import json
from pathlib import Path

from screening import dataset

OUT = Path(__file__).resolve().parent.parent / "output" / "screening" / "blind_input.json"

# 허용 필드 화이트리스트 — 이것 외에는 어떤 키도 내보내지 않는다
ALLOWED = (
    "key", "name", "track", "sector_key", "sector_note", "stage_band",
    "facts", "product_note", "priced_round", "cap_table_note", "english_note",
)


def build() -> list[dict]:
    rows = []
    for c in dataset.COMPANIES:
        row = {
            "key": c.key, "name": c.name, "track": c.track,
            "sector_key": c.sector_key, "sector_note": c.sector_note,
            "stage_band": c.stage_band,
            "facts": [{"fact": f, "evidence_grade": g} for f, g in c.facts],
            "product_note": c.product_note,
            "priced_round": c.priced_round,
            "cap_table_note": c.cap_table_note,
            "english_note": c.english_note,
        }
        assert set(row) == set(ALLOWED)
        rows.append(row)
    return rows


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(build(), ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print(f"{OUT} ({len(build())}개사)")


if __name__ == "__main__":
    main()
