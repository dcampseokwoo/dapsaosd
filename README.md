# 스타트업 투자 스테이지 자동 조사 파이프라인

스타트업 DB 엑셀(`data/Startup_DB.xlsx`)의 G열(투자 스테이지)을 Gemini **Google Search
grounding** 웹 검색으로 최신화하는 파이프라인. 비용 절약을 위해 2단계 깔때기 구조를 쓴다.

> **모니터링 도구 추가** — 같은 인프라(Gemini 래퍼·뉴스 검색·체크포인트)를 재사용하는
> 두 가지 크롤러가 `monitor.py` 로 실행된다. 아래 [모니터링](#모니터링-monitorpy--500-global--ac-업체) 섹션 참고.
> ① 500 Global 프로그램 최신 정보(지원 요건·마감일·배치 일정·포트폴리오·선발 공통점 분석)
> ② AC 업체(Long Story Short·Upright·Intralink 등) 서비스/가격 변경·멘토 영입 동향

## 흐름 (pipeline.py)

```
로드: All(전체기업) 시트 (헤더 3행, 데이터 4행~)
  ↓
제외: ① 로그 시트 `스테이지 업데이트(26.07)` 기록분(1차 완료 425행)
      ② G열이 IPO('YY)/M&A('YY) — 연도 확정 종결 상태
  ↓
정렬: H열 우선순위  Type 1 → 디데이 → Type 2 → 공란/기타 → Type 3
  ↓
[1단계 스크리닝]  기업당 검색 1회
      쿼리: "{국문 회사명} 투자 유치"  →  changed / unchanged / no_info / ambiguous
      * `data/스크리닝_기완료_50개사.csv` 에 있는 행은 1단계 스킵 (verdict 재사용)
      * unchanged/no_info 는 여기서 종료 (실측상 전체의 ~70-85%)
  ↓
[2단계 정밀 검증]  changed / ambiguous / 연도없는 M&A·IPO 만 (검색 2-3회)
      플래텀·벤처스퀘어·와우테일·더벨·THE VC·혁신의숲 교차 확인, 동명 기업 검증
      → new_stage / confidence(high·medium·low) / evidence / source_url
  ↓
판정 (validators/stage_validator.py — 보수적):
      high → G열 교체 | medium → 공란·`알 수 없음`일 때만 | low → 로그만
      폐업/영업종료 → 스테이지 유지, 비고 기록
  ↓
체크포인트: 기업 단위 즉시 checkpoints/results.jsonl append (재실행 시 자동 스킵)
  ↓
엑셀 반영 (updater/excel_updater.py): G열 값만 변경, 로그 시트 append(반영 행 노란 배경),
      `업데이트 내역` 이력 1행, `{원본명}_updated_{날짜}.xlsx` 로 저장
```

## 검색 모드 (결제 등록 여부에 따라 선택)

| 모드 | 검색 방법 | 비용 | 비고 |
|---|---|---|---|
| `rss` (기본) | 구글 뉴스 RSS(+네이버 뉴스 API)를 프로그램이 직접 검색 → Gemini(무료 티어)가 결과를 읽고 판단 | **무료** | 결제 등록 불필요. 검색 결과 0건이면 Gemini 호출 없이 no_info 처리 |
| `grounding` | Gemini Google Search grounding | 유료 티어 필요 (일 1,500회 무료) | `--search-mode grounding` 또는 `SEARCH_MODE=grounding` |

### 네이버 뉴스 검색 API (선택, 무료 — 검색 커버리지 대폭 향상)

1. https://developers.naver.com → 로그인 → **Application > 애플리케이션 등록**
2. 사용 API에 **"검색"** 선택, 환경은 WEB 아무 주소나(예: http://localhost) 입력
3. 발급된 **Client ID / Client Secret** 을 실행 전에 환경변수로 설정:
   ```bat
   set NAVER_CLIENT_ID=발급받은ID
   set NAVER_CLIENT_SECRET=발급받은Secret
   ```
   (맥/리눅스는 `export`) — 무료 25,000회/일, 카드 등록 불필요.
   키가 설정되면 구글 뉴스와 병행 검색(제목+요약 확보), 없으면 구글만 사용.

## 모듈

| 파일 | 역할 |
|---|---|
| `config.py` | 시트/열 구조, 분류 체계, 우선순위, 모델·레이트리밋 설정 |
| `ai/gemini.py` | google-genai SDK 래퍼 (grounding, 딜레이, 429 지수 백오프 2/4/8/16s, 호출 카운터) |
| `collectors/url_collector.py` | 검색 쿼리 생성 (일반명사성 이름엔 업종 키워드 추가) |
| `collectors/news_search.py` | 구글 뉴스 RSS 검색 (무료 모드의 검색 엔진) |
| `collectors/page_collector.py` | 기사 원문 텍스트 확보 (선택적) |
| `extractors/investment_extractor.py` | 스크리닝/검증 프롬프트 + JSON 응답 파서 |
| `validators/stage_validator.py` | 표기 정규화(`시리즈B`→`Series B`, `IPO(25)`→`IPO('25)`), 반영 정책 |
| `updater/excel_updater.py` | openpyxl 서식 보존 반영 + 로그/이력 시트 |
| `pipeline.py` | 오케스트레이션 + 체크포인트 |
| `main.py` | CLI |

## 실행

```bash
pip install -r requirements.txt
export GEMINI_API_KEY=...          # Google AI Studio 키
# 복수 키는 GEMINI_API_KEYS=key1,key2 로 지정 (단일 키 변수와 하위 호환)
# data/Startup_DB.xlsx 를 놓은 뒤:

python main.py --test                      # 소량(5개사) 드라이런 테스트
python main.py --priority 1 --limit 50     # Type 1 그룹 50개 조사 + 반영
python main.py --dry-run --max-calls 200   # 조사만, 호출 200회 한도
python main.py --apply-only                # 체크포인트를 엑셀에 일괄 반영
python main.py --report                    # 반영/확인필요 검수 CSV 생성
python main.py --verify-models gemini-3.5-flash,gemini-3-flash-preview
```

- `--priority 1..5` = Type 1 / 디데이 / Type 2 / 공란·기타 / Type 3
- **조사 범위**: 기본은 Type 1·디데이·Type 2 만 조사 (공란/기타·Type 3 제외).
  전체로 되돌리려면 `set TARGET_PRIORITIES=1,2,3,4,5` 후 실행
- `--max-calls` 도달 시 체크포인트 저장 후 정상 종료 (재실행하면 이어서 진행)
- `GEMINI_API_KEYS`의 현재 키에서 모든 후보 모델이 소진되면 다음 키로 자동 전환
- 키·모델별 소진 상태를 독립 관리하므로 검증 모델 소진 후에도 다른 키의 스크리닝 모델을 재사용
- `--verify-models` = 2단계 검증에 허용할 모델 목록. 빈 값(`--verify-models ""`)이면 제한 없음.
  제한 모델이 모두 소진된 회사는 체크포인트에 기록하지 않아 다음 실행에서 재시도됨.
- `--report` = `checkpoints/review_반영.csv`, `review_확인필요.csv` 생성 (UTF-8-BOM)
  `review_반영.csv`는 실제 엑셀 저장 성공 건을 기준으로 하며 행 불일치 건은 확인필요로 분류
- 손상된 체크포인트 줄은 `results.corrupt.jsonl`에 보관하고 정상 줄로 자동 복구
- RSS 스크리닝 검색 결과는 2단계 검증에서 병합·재사용하여 중복 수집을 줄임
- `--batch-size N` = 1단계 스크리닝을 N개씩 묶어 한 요청으로 처리 (기본 8, `1`=배치 끔).
  Gemini 무료 티어의 **일일 요청 한도**를 N배 아껴 하루 처리량을 크게 늘림.
  2단계 정밀 검증은 품질을 위해 항상 회사별 개별 호출. (rss 모드에서만 적용)
- 오프라인 검증: `python test_pipeline_offline.py` (API 키 불필요, Gemini 모킹)

## 분류 체계 (G열 — 이 표기만 사용)

`Pre-seed, Seed, Pre-A, Series A, Series B, Series C, Series D, Series E ~, Pre-IPO,
IPO('YY), M&A('YY), 알 수 없음` — IPO/M&A는 2자리 연도 필수. Pre-A=프리시리즈A 브릿지,
엔젤/시드 언급은 Seed.

## 검증 원칙

- "누적 투자 N억" 기사만으로 스테이지 단정 금지 — 라운드명 명시 기사 필요
- 기록 과대 기재 발견 시(명시적 기사 근거 있으면) 하향도 반영
- 연도 없는 `M&A`/`IPO` 값은 연도를 찾아 `M&A('YY)` 형식으로 보정
- 동명 기업은 업종·웹사이트·서비스명 일치 확인 후에만 채택

## 모니터링 (monitor.py) — 500 Global / AC 업체

투자 스테이지 파이프라인과 같은 인프라(`ai/gemini.py`, `collectors/news_search.py`,
`collectors/naver_search.py`)를 재사용하는 별도 CLI. 리포트는 `output/`에
마크다운+JSON으로 저장되고, 페이지 스냅샷은 `checkpoints/snapshots/`에 남아
**다음 실행 때 무엇이 바뀌었는지(diff)** 자동 감지한다.

```bash
python monitor.py 500                        # ① 500 Global 프로그램 리포트
python monitor.py ac                         # ② AC 업체 동향 리포트
python monitor.py ac --target intralink      #    특정 업체만
python monitor.py all                        # 둘 다
python monitor.py 500 --no-ai                # Gemini 없이 수집·스냅샷·뉴스만 (키 불필요)
python monitor.py 500 --search-mode grounding # 유료 티어: Gemini 검색 직접 사용 (권장)
python test_monitor_offline.py               # 오프라인 검증 (API 키/네트워크 불필요)
```

### ① 500 Global 프로그램 (`monitors/global500.py`)

500.co 공식 페이지(Flagship 요강·프로그램 목록·포트폴리오·블로그) + 뉴스 교차 검색으로:

- **다음 배치 지원 마감일 추적** — `checkpoints/global500_deadline.jsonl`에 이력을 남기고,
  이전 실행과 마감일이 달라지면 리포트 상단에 ⚠️ 변경 알림 표기 (D-day 계산 포함)
- 지원 요건 / 투자 조건($150K for 6% 등) / 배치 일정 구조화 추출
- 최근 선발 포트폴리오사 리스트 + **선발 기업 공통점 분석**
  (섹터·스테이지·지역·비즈니스 모델·팀 프로필 — 어떤 프로필이 잘 뽑히는지)

주의: 500.co는 JS 렌더링 페이지가 많아 단순 크롤링으로는 본문이 빈약할 수 있다.
유료 티어 키가 있으면 `--search-mode grounding`이 가장 정확하다.

### ② AC 업체 동향 (`monitors/ac_watch.py`)

비교 시트의 액셀러레이터/컨설팅 업체 웹사이트를 크롤링해:

- **서비스/가격 변경 여부** — 이전 스냅샷과 줄 단위 diff 비교 후 Gemini가
  실질 변경(서비스 신설·가격 변경)과 잡음(연도 표기 등)을 구분해 요약
- **멘토/인력 영입 소식** — 뉴스 검색 + 페이지 변경에서 인력 변동 추출
  (예: "前 500 Global APAC 총괄 스카우트" 같은 영입 시그널 중점 확인)
- 비교 시트 갱신이 필요한 변경이면 리포트 상단에 ⚠️ alert 표기

대상 목록은 `config.py`의 `AC_TARGETS` 기본값(Upright·Intralink는 URL 확인됨,
Long Story Short는 도메인 미확인이라 뉴스 검색만) 대신 `data/ac_targets.json`이
있으면 그 파일을 우선 사용한다 — `data/ac_targets.sample.json`을 복사해 URL을 채우면 된다.
일부 사이트는 봇 차단(403)이 있을 수 있다 — 그 페이지는 "수집 실패"로 표기되고
기존 스냅샷은 보존된다(오탐 방지).
