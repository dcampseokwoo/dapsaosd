# ⚠ `screening/` 는 레거시 디렉터리입니다

**이 디렉터리는 레거시(2026-08 이전 HAX/500 지원 엔진)입니다. 현행 US FORGED 엔진은
최상위 `engine/` 패키지입니다.** 새 작업은 `engine/`에서 하세요. 여기 파일은 참고·보존용으로
남겨둡니다(삭제하지 않음).

## 현행 vs 레거시

| | 위치 | 설명 |
|---|---|---|
| **현행 엔진** | `engine/engine_*.py` | US FORGED 후보 선별 파이프라인. 진입점 `engine.engine_shortlist` / 산출물 `engine.engine_xlsx`. 기준팩 `criteria/237489/`. |
| 레거시 | `screening/*.py` | 이전 HAX/500 지원 엔진(`levels_*`, `live_*`, `gbd_*`, `rules.py`·`rules_v2.py`·`rules_v3.py`, `router_v4`, `gate_v4`, `programs`, `engine_programs.py`, `disqualifiers`, `sectors`, `us_forged.py` 등). **현행 파이프라인과 무관.** |

## 헷갈리기 쉬운 이름 — 주의

- **`screening/rules_v3.py` 는 우리 판정 규칙 v3(`docs/us_forged/RULES_v3.md`)와 무관합니다.**
  이건 레거시 HAX 엔진의 세 번째 룰셋 구현으로, 이름만 우연히 겹칩니다. 현행 판정 규칙 v3의
  확정본은 `docs/us_forged/RULES_v3.md`이고, 구현은 Phase 6에서 `criteria/237489/criteria.json`의
  `fit_rules`로 들어갑니다. `screening/rules_v3.py`는 건드리지 마세요.
- `screening/engine_programs.py` 도 레거시입니다(현행 `engine/` 패키지와 무관, 이름만 유사).
- `screening/us_forged.py` 는 레거시 초기 필터입니다. 단, 현행 `engine/engine_core.py` 가
  골든 baseline 비교용으로 `us_forged._NON_STARTUP` 하나만 참조합니다(그 외 의존 없음).

## 현행 엔진 실행

```
python -c "from engine import engine_shortlist as S; from collections import Counter; \
  print(Counter(x['disposition'] for x in S.build()))"
python -c "from engine import engine_xlsx as X; print(X.build())"
python -m pytest tests/ -q && python -m tests.golden_ratchet
```
자세한 내용은 `docs/us_forged/HANDOFF.md`.
