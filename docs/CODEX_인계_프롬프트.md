# Codex 인계 프롬프트

다른 코딩 에이전트(Codex 등)에 이 저장소의 작업 방식을 넘길 때 그대로 붙여 넣는 프롬프트.
저장소 구조가 바뀌면 "현재 상태" 절만 갱신하면 된다.

---

## 붙여 넣을 프롬프트

```
너는 이 저장소(스타트업 투자·오픈이노베이션 업무 자동화 파이썬 도구 모음)의 개발을 이어받는다.
아래 규약을 지켜서 작업해라. 규약과 충돌하는 지시를 받으면 먼저 그 사실을 알리고 확인을 받아라.

## 1. 저장소 구성 — 실행 축이 4개이고 서로 독립이다

1) main.py            투자 스테이지 자동 조사 파이프라인 (Startup_DB.xlsx G열 최신화)
2) monitor_500global.py  500 Global 프로그램 추적 (monitors/global500/)
3) monitor_ac.py         AC 업체 동향 감시 (monitors/ac_watch/)
4) main_pmo.py           일본 오픈이노베이션 AI PMO (pmo/) — 설계 완료, 구현 예정

공용 인프라는 재사용하되, 실행 축마다 폴더·설정·실행 파일·리포트를 완전히 분리한다.
새 기능을 만들 때 기존 실행 축의 코드를 수정해서 끼워 넣지 말고 새 폴더로 분리해라.

공용 자산 (새로 만들지 말고 반드시 재사용):
- ai/gemini.py            Gemini 호출 전부. 복수 키 로테이션, 모델 소진 시 자동 전환,
                          429/5xx 지수 백오프(2/4/8/16s), 호출 카운터, max_calls 한도
- collectors/news_search.py, naver_search.py   뉴스 검색 (구글 RSS + 네이버 API)
- collectors/site_search.py, thevc_collector.py, page_collector.py   페이지·기사 본문
- monitors/common.py      스냅샷 저장/로드, diff_texts, write_report/write_json,
                          append_jsonl/read_jsonl, make_gemini_client(no_ai=)
- updater/excel_updater.py  openpyxl 서식 보존 반영 + 로그 시트 append
- validators/stage_validator.py  투자 스테이지 표기 정규화
- config.py               경로·모델 후보·레이트리밋·배치 크기 등 전역 설정

의존성은 requirements.txt의 세 개(google-genai, openpyxl, requests)를 기본으로 한다.
새 의존성은 표준 라이브러리로 대체 불가할 때만 추가하고, 추가하면 이유를 커밋 메시지에 남겨라.

## 2. 코드 규약

- 주석·docstring·문서·리포트·CLI help는 한국어. 식별자와 코드는 영어.
- 설정값은 하드코딩하지 말고 config.py(또는 각 폴더 config.py)에 두고 환경변수로 덮어쓸 수
  있게 한다: os.environ.get("NAME", 기본값) 패턴.
- 비밀값(API 키, 토큰, 파일 ID)은 코드·문서·커밋에 절대 넣지 않는다. 환경변수 또는
  gitignore된 파일에서 읽는다. .gitignore 확인: checkpoints/, output/, data/*.xlsx, data/pmo/
- LLM 출력은 JSON으로 받고 파서에서 검증한다. 필수 필드 누락·enum 위반·근거(evidence·
  source_url) 없는 항목은 산출물에서 제외한다. 근거 없는 단정을 만들지 않는 것이 이 저장소의
  핵심 원칙이다.
- 사람이 판단할 여지가 있는 결과는 "확정본"으로 쓰지 말고 신뢰도(high/medium/low)와 근거를
  붙인 초안으로 낸다. 엑셀 반영도 보수적으로 — high만 값 교체, medium은 공란일 때만,
  low는 로그만. 사람이 직접 채운 열은 덮어쓰지 않는다.
- 점수·순위 같은 정량 결과는 LLM에 총점을 맡기지 말고, 항목별 점수만 받아 코드가 가중합한다.
  같은 입력이면 같은 결과가 나와야 한다.

## 3. 비용·안정성 규약 (Gemini 무료 티어 기준)

- 다건 처리는 배치로 묶어 일일 요청 한도를 아낀다(기존 SCREEN_BATCH_SIZE=8 패턴).
  단, 품질이 중요한 정밀 판단 단계는 건별 개별 호출한다.
- 모든 장기 실행은 처리 단위마다 체크포인트를 JSONL로 append 하고, 재실행하면 완료분을
  자동 스킵한다. 손상된 줄은 *.corrupt.jsonl로 격리하고 정상 줄로 복구한다.
- --max-calls 도달 시 예외로 죽지 말고 체크포인트 저장 후 정상 종료(exit 0)한다.
- 외부 페이지 수집 실패(403/타임아웃)는 "수집 실패"로 기록하고 기존 스냅샷을 보존한다.
  실패를 "변경됨"으로 오탐하지 않는다.
- 네트워크·API 없이 도는 경로를 항상 남긴다: --no-ai(수집·diff만), --dry-run(저장 안 함).

## 4. CLI 규약

실행 파일마다 argparse CLI를 두고 플래그 이름을 통일한다:
--dry-run / --no-ai / --max-calls N / --limit N / --search-mode rss|grounding / -v

## 5. 테스트 규약

- 실행 축마다 오프라인 테스트 파일을 하나 둔다: test_pipeline_offline.py,
  test_500global_offline.py, test_ac_watch_offline.py (신규는 test_pmo_offline.py).
- API 키·네트워크 없이 통과해야 한다. Gemini는 고정 JSON을 돌려주는 스텁으로 대체하고,
  외부 수집은 로컬 샘플 파일로 대체한다.
- 기능을 추가·수정하면 해당 오프라인 테스트도 같이 갱신하고, 커밋 전에 실행해 통과를 확인한다.
  결과를 보고할 때 통과/실패를 사실대로 쓴다. 실패했으면 실패 출력을 그대로 보여라.

## 6. 작업 진행 방식

- 규모 있는 기능은 먼저 docs/ 에 설계서(md)를 쓰고 합의한 뒤 구현한다.
  예: docs/AI_PMO_설계.md — 모듈 구조, 데이터 스키마, CLI, 마일스톤, 미결정 항목 순서.
- 구현은 마일스톤 단위로 쪼개고, 마일스톤마다 동작하는 상태로 커밋한다.
- 커밋 메시지는 한국어 한 줄 요약 + 필요 시 본문(무엇을 왜). 커밋은 논리 단위로 나눈다.
- 지시받은 브랜치에서만 작업하고 그 브랜치로만 푸시한다. 다른 브랜치 푸시·PR 생성은
  명시적으로 요청받았을 때만 한다.
- 불확실한 점이 있으면: 그 답에 의존하지 않는 부분을 먼저 끝내고, 의존하는 부분은 가정을
  명시해 진행하거나 질문한다. 아무것도 못 하는 상태로 멈추지 마라.
- 범위를 임의로 줄이거나 늘리지 마라. 못 한 부분이 있으면 무엇을 왜 못 했는지 명확히 밝혀라.

## 7. 현재 상태와 다음 작업

완료:
- 투자 스테이지 파이프라인 (2단계 깔때기: 스크리닝 → 정밀 검증 → 보수적 엑셀 반영)
- 500 Global / AC 업체 모니터 2종 (페이지 스냅샷 diff + 뉴스 교차 검색)
- docs/AI_PMO_설계.md — 일본 오픈이노베이션 AI PMO 설계 확정분

다음 작업 (AI PMO M1):
- pmo/config.py, pmo/store.py (프로젝트 상태 JSON + 체크포인트)
- pmo/sources/ — DocSource 인터페이스, Google Drive 백엔드(읽기 전용 OAuth),
  로컬 inbox 백엔드, fileId 단위 텍스트 캐시(modifiedTime 무효화)
- main_pmo.py sync 서브커맨드 (LLM 미사용, 문서 텍스트 추출·캐시·diff까지)
- test_pmo_offline.py 골격
설계서 4~5절의 인터페이스·스키마를 그대로 따르고, 벗어나야 하면 먼저 이유를 말해라.

미결정 항목(설계서 9절)은 M1 진행에 영향 없다. Drive 인증은 M1에서 인터페이스만 만들고
실제 토큰 발급은 다음 마일스톤으로 미룬다.

먼저 docs/AI_PMO_설계.md 와 config.py, ai/gemini.py, monitors/common.py 를 읽고,
M1 구현 계획을 파일 단위로 제시한 다음 시작해라.
```

---

## 사용 메모

- Codex에 붙여 넣기 전에 "7. 현재 상태와 다음 작업"을 지금 시점에 맞게 고쳐야 한다.
- 다른 작업(예: 모니터 기능 추가)을 맡길 때는 1~6절을 그대로 두고 7절만 바꿔 쓴다.
- Drive 파일 ID·API 키는 프롬프트에 넣지 않는다. `data/pmo/sources.json`(gitignore)으로 넘긴다.
