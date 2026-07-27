# AI PMO for Japan Open Innovation — 설계서

일본 오픈이노베이션 프로그램(수요 발굴 → 스타트업 선발 → 멘토링 → 현지 피칭)의 실행 업무를
자동화하는 프로그램의 설계 문서. 구현 착수 전 합의용이며, 확정 후 이 문서를 기준으로
`pmo/` 패키지를 단계별로 구현한다.

원칙은 기획안과 동일하다. **AI가 프로젝트를 대신하지 않는다.** AI PMO는 정보와 실행을
연결해 산출물 초안까지 만들고, 관계 구축·협상·최종 판단은 PM이 한다. 따라서 모든 단계의
출력은 "확정본"이 아니라 **근거(출처·인용)가 붙은 초안**이며, 근거 없는 단정은 만들지 않는다.

---

## 1. 범위와 산출물

| 단계 | 실제 업무 | 프로그램이 처리하는 것 | 산출물 |
|---|---|---|---|
| ① 수요 발굴 | 일본 기업 미팅 · 동향 조사 | 회의록·출장보고서 분석, 과제/협업 니즈 구조화, 유사 협업 사례 정리 | 니즈 브리프 (md) |
| ② 스타트업 선발 | 공개 모집 · 스텔스 소싱 · 후보 평가 | 니즈 키워드 기반 후보 소싱, 후보별 원페이지, 가중치 스코어링 | 후보 비교표 (xlsx) + 원페이지 (md) |
| ③ 멘토링 | 협업 아이디어 구체화 | PoC 시나리오·검증 지표·예상 Q&A 생성 | PoC 시나리오 (md) |
| ④ 현지 피칭 | 피칭 · 미팅 · 후속 관리 | 기업별 브리핑, 후속관리표, KPI 집계, 결과보고 초안 | 브리핑·후속관리표·결과보고 초안 |

단계는 **독립 실행 가능**해야 한다. ①의 산출물이 없어도 ②를 수동 입력(니즈 파일 직접 작성)
으로 돌릴 수 있어야 실제 운영에서 쓸 수 있다.

## 2. 기존 자산 재사용

새로 만들지 않고 그대로 쓴다.

| 기존 모듈 | AI PMO에서의 용도 |
|---|---|
| `ai/gemini.py` | LLM 호출 전부. 복수 키 로테이션, 모델 소진 시 자동 전환, 429 지수 백오프(2/4/8/16s), 호출 카운터 |
| `collectors/news_search.py`, `naver_search.py` | ② 후보 소싱·검증, ④ 기업별 최신 동향 |
| `collectors/site_search.py`, `thevc_collector.py` | ② 스타트업 투자·연혁 교차 확인 |
| `collectors/page_collector.py` | 스타트업·일본 기업 웹사이트 본문 확보 |
| `monitors/common.py` | 스냅샷 diff(`load_snapshot`/`save_snapshot`/`diff_texts`), 리포트 저장(`write_report`/`write_json`), JSONL 유틸, `make_gemini_client(no_ai=)` |
| `updater/excel_updater.py` 패턴 | openpyxl 서식 보존 반영 + 로그 시트 append 방식을 후속관리표에 그대로 적용 |
| `config.py` | 모델 후보 목록, 레이트리밋, 배치 크기, 출력·체크포인트 경로 규약 |

새로 필요한 것은 **문서 소스(Google Drive) 연동**, **프로젝트 상태 저장**, **단계별 추출기**뿐이다.

## 3. 모듈 구조

```
main_pmo.py                  CLI (sync / stage1..4 / report)
pmo/
  config.py                  단계 정의, 산출물 경로, 스코어링 가중치, 모델 설정
  store.py                   프로젝트 상태 읽기/쓰기 (JSON + JSONL 이력)
  sources/
    base.py                  DocSource 인터페이스 (list / text / meta)
    drive.py                 Google Drive API 백엔드 (읽기 전용)
    local.py                 로컬 inbox 백엔드 (오프라인·테스트·수동 투입)
    cache.py                 fileId 단위 텍스트 캐시 + modifiedTime 무효화
  stage1_needs.py            회의록·출장보고서 → 니즈 브리프
  stage2_sourcing.py         니즈 → 후보 소싱 · 원페이지 · 비교표
  stage3_poc.py              페어 → PoC 시나리오 · 예상 Q&A
  stage4_pitch.py            기업별 브리핑 · 후속관리표 · KPI
  report.py                  결과보고 초안 (md, 필요 시 docx)
  prompts.py                 단계별 프롬프트 + JSON 파서 (extractors 패턴 준용)
  schema.py                  산출물 JSON 스키마 검증 (필수 필드·enum·근거 유무)
output/pmo/<project>/         산출물 (md · json · xlsx)
data/pmo/
  sources.json               프로젝트별 Drive 폴더/파일 지정 (gitignore)
  inbox/<project>/           로컬 백엔드 입력 파일 (gitignore)
  cache/drive/<fileId>/      meta.json · text.txt (gitignore)
checkpoints/pmo/<project>.jsonl   단계별 실행 이력 (재실행 시 스킵)
test_pmo_offline.py          Gemini·Drive 모킹 오프라인 검증
```

기존 두 모니터와 동일한 원칙 — **폴더·실행 파일·리포트를 완전히 분리**한다. 투자 스테이지
파이프라인(`main.py`)과 모니터(`monitor_*.py`)는 손대지 않는다.

## 4. Google Drive 연동

입력은 Drive에서 가져온다. 확인된 실제 자산 예시(제목만 기재, 파일 ID·폴더 ID는 저장소에
커밋하지 않고 `data/pmo/sources.json`에 두고 gitignore):

- `2024-03 / 2024-11 / 2024-12 일본 출장 결과보고서` (PDF) → ① 니즈·컨택 이력 원천
- `2026 JR East 협업 파트너사 조사` (Google Docs) → ① 대상 기업 과제 정리
- `[계약심의] 일본 프로그램 운영 효율 개선안` (Slides) → 프로그램 운영 제약 조건
- `Startup DB 2024.1.30_일본.xlsx` → ② 후보 풀 시드
- `[Caselet] 일본 기업과 한국 스타트업의 협업 성공사례` (PPTX) → ①·③ 유사 사례 근거

### 4.1 두 개의 백엔드가 필요한 이유

Claude 세션의 Drive 커넥터(MCP)는 **대화 세션 안에서만** 동작한다. 크론·CLI로 돌아가는
파이썬 프로세스는 그 커넥터를 호출할 수 없다. 따라서:

| 백엔드 | 인증 | 용도 |
|---|---|---|
| `sources/drive.py` | `google-api-python-client` + OAuth 데스크톱 플로우, 스코프 `drive.readonly`, 토큰 `data/pmo/.drive_token.json`(gitignore) | 실제 운영. `python main_pmo.py sync`로 지정 폴더를 캐시에 내려받음 |
| `sources/local.py` | 없음 | 오프라인 테스트, 커넥터로 받은 문서를 수동 투입, 인증 준비 전 개발 |

두 백엔드는 `DocSource` 동일 인터페이스를 구현하므로 상위 단계 코드는 어느 쪽인지 모른다.

```python
@dataclass
class DocRef:
    id: str; title: str; mime: str; modified: str; url: str

class DocSource(Protocol):
    def list(self, query: str | None = None) -> list[DocRef]: ...
    def text(self, ref: DocRef) -> str: ...   # 캐시 우선, 미스 시 원격
```

### 4.2 포맷별 텍스트 추출

| MIME | 방법 |
|---|---|
| Google Docs | `files.export(mimeType='text/plain')` |
| Google Sheets | `files.export(mimeType='text/csv')` (시트별) |
| Google Slides | `files.export(mimeType='text/plain')` |
| PDF | 다운로드 → `pypdf` 텍스트, 실패 시 "추출 실패"로 기록하고 스킵 |
| DOCX / PPTX / XLSX | 다운로드 → `python-docx` / `python-pptx` / `openpyxl` |

### 4.3 캐시와 변경 감지

`data/pmo/cache/drive/<fileId>/{meta.json,text.txt}`에 저장하고 `modifiedTime`이 같으면
원격 호출을 생략한다. 텍스트가 바뀌면 `monitors/common.py`의 `diff_texts`로 변경분만
LLM에 넘겨 "지난 실행 이후 새로 생긴 니즈"만 갱신한다 — 모니터에서 이미 검증된 방식이다.

## 5. 데이터 모델

프로젝트 하나 = 일본 기업(또는 배치) 하나. 상태는 `output/pmo/<project>/state.json`에
누적하고, 각 단계 실행은 `checkpoints/pmo/<project>.jsonl`에 append 한다(재실행 시 스킵).

### ① 니즈 브리프

```json
{
  "project": "jr-east-2026",
  "jp_company": {"name": "JR East", "name_ja": "JR東日本", "industry": "철도·인프라", "url": ""},
  "source_docs": [{"id": "", "title": "", "modified": ""}],
  "challenges": [
    {"title": "", "description": "", "domain": "", "urgency": "high|mid|low",
     "evidence": "문서 인용 원문", "source_doc": ""}
  ],
  "collab_needs": [{"need": "", "target_tech": [], "poc_ready": true, "evidence": ""}],
  "constraints": {"budget": "", "timeline": "", "decision_process": "", "language": ""},
  "similar_cases": [{"jp_company": "", "startup": "", "outcome": "", "source_url": ""}],
  "open_questions": ["PM이 다음 미팅에서 확인할 항목"],
  "confidence": "high|medium|low"
}
```

`evidence`가 빈 항목은 `schema.py`에서 탈락시킨다 — 근거 없는 과제는 산출물에 넣지 않는다.

### ② 후보 비교표

```json
{
  "needs_ref": "output/pmo/jr-east-2026/needs.json",
  "candidates": [
    {"name_kr": "", "name_en": "", "stage": "", "industry": "", "website": "",
     "sourcing_channel": "open_call|stealth|db",
     "scores": {"need_fit": 0, "tech_maturity": 0, "japan_readiness": 0, "team": 0},
     "score_total": 0,
     "fit_reason": "", "tech_match": [],
     "japan_readiness": {"jp_entity": false, "jp_language": false, "cert": [], "jp_client": []},
     "risks": [], "sources": [{"title": "", "url": ""}]}
  ]
}
```

**스코어링은 결정론적으로 계산한다.** LLM은 항목별 점수와 근거만 내고, 총점은 코드가
가중합한다(니즈 적합성 40 / 기술 성숙도·PoC 가능성 25 / 일본 진출 준비도 20 / 팀·트랙레코드 15).
같은 입력이면 같은 순위가 나와야 PM이 신뢰할 수 있다. 투자 스테이지 표기는 기존
`validators/stage_validator.py`의 정규화를 재사용한다.

### ③ PoC 시나리오

```json
{
  "pair": {"jp_company": "", "startup": ""},
  "hypothesis": "검증할 가설 한 문장",
  "scope": {"in": [], "out": []},
  "steps": [{"week": "W1-W2", "activity": "", "owner": "jp|startup|dcamp"}],
  "success_metrics": [{"kpi": "", "baseline": "", "target": ""}],
  "data_needs": [], "legal": {"nda": "", "ip": "", "personal_data": ""},
  "expected_qa": [{"q": "", "a": "", "asker": "jp_company|startup"}],
  "risks": [{"risk": "", "mitigation": ""}]
}
```

일본 기업 관점의 예상 Q&A(도입 근거·보안·유지보수·현지 지원 체계)를 반드시 포함한다.

### ④ 브리핑 · 후속관리표

```json
{
  "event": "2026-11 도쿄 피칭",
  "briefs": [{"jp_company": "", "attendees": [], "why_them": "",
              "recent_news": [{"title": "", "url": "", "date": ""}],
              "talking_points": [], "asks": [], "cautions": []}],
  "followups": [{"jp_company": "", "startup": "",
                 "status": "미팅완료|검토중|PoC협의|보류|중단",
                 "next_action": "", "owner": "", "due": "", "last_contact": ""}],
  "kpi": {"meetings": 0, "followup_rate": 0.0, "poc_discussions": 0, "poc_signed": 0}
}
```

후속관리표는 xlsx로도 내보낸다. 기존 엑셀 반영 규칙(값만 교체, 서식 보존, 변경 행 로그
시트 append)을 그대로 따르며 **사람이 직접 적은 열은 덮어쓰지 않는다** — AI는 자기가
만든 열만 갱신하고 나머지는 로그로만 남긴다.

## 6. CLI

```bash
python main_pmo.py sync    --project jr-east-2026          # Drive → 캐시 (LLM 미사용)
python main_pmo.py stage1  --project jr-east-2026          # 니즈 브리프
python main_pmo.py stage2  --project jr-east-2026 --limit 30
python main_pmo.py stage3  --project jr-east-2026 --pair jr-east/acme
python main_pmo.py stage4  --project jr-east-2026 --event 2026-11-tokyo
python main_pmo.py report  --project jr-east-2026
```

공통 플래그는 기존 실행 파일과 통일한다: `--no-ai`(수집·캐시·diff만), `--dry-run`(산출물
저장 안 함), `--max-calls N`, `--search-mode rss|grounding`, `--source drive|local`.

비용 관리도 기존 방식을 따른다 — 후보 원페이지 같은 다건 처리는 `SCREEN_BATCH_SIZE`처럼
배치로 묶고, 판단이 중요한 단계(③ PoC 시나리오)는 건별 개별 호출한다. `--max-calls`
도달 시 체크포인트 저장 후 정상 종료하고 재실행하면 이어서 진행한다.

## 7. 검증

- `test_pmo_offline.py` — API 키·네트워크 없이 전 단계 실행. Gemini는 고정 JSON을 돌려주는
  스텁으로, Drive는 `sources/local.py` + 샘플 문서로 대체한다.
- 스키마 검증: 필수 필드 누락, enum 위반, `evidence` 없는 항목, 점수 범위 이탈을 잡는다.
- 회귀 확인 항목: 재실행 시 체크포인트 스킵 동작, 캐시 히트 시 원격 호출 0건,
  같은 입력 → 같은 후보 순위.

## 8. 개발 순서

| 마일스톤 | 내용 | 완료 기준 |
|---|---|---|
| M1 | `pmo/config.py`, `store.py`, `sources/*`, `main_pmo.py sync`, 오프라인 테스트 골격 | 로컬 백엔드로 문서 텍스트 추출·캐시·diff 동작 |
| M2 | ① 니즈 브리프 | 출장보고서 PDF 1건으로 근거 인용 포함 브리프 생성 |
| M3 | ② 소싱 + 원페이지 + 비교표 xlsx | 니즈 JSON 입력 → 후보 20건 스코어 정렬 |
| M4 | ③ PoC 시나리오 + 예상 Q&A | 페어 1건 시나리오 생성, 스키마 통과 |
| M5 | ④ 브리핑 · 후속관리표 · 결과보고 초안 | 이벤트 1건 전체 산출물 생성 |

Drive 실인증(OAuth)은 M1에서 인터페이스만 만들고, 실제 토큰 발급은 M2 착수 시점에 진행한다.

## 9. 확인 필요 항목

구현 전 결정이 필요한 것들. 미결 상태로도 M1은 진행 가능하다.

1. **Drive 인증 방식** — 개인 OAuth(본인 계정 권한) vs 서비스 계정 + 공유 드라이브 권한 부여.
   자동 실행(크론)까지 갈 거면 후자가 안전하다.
2. **산출물 저장 위치** — 로컬 `output/`만? 아니면 Drive에 다시 업로드까지? 업로드하면
   쓰기 스코프가 필요하고, 실수로 원본을 덮어쓸 위험이 생기므로 별도 폴더 한정을 권장한다.
3. **후속관리표 원본** — 로컬 xlsx인지, Google Sheets를 직접 갱신하는지. Sheets 직접 갱신은
   여러 사람이 동시에 쓰는 문서라 충돌 처리 규칙이 필요하다.
4. **일본어 산출물** — 브리핑·PoC 시나리오를 일본어로도 만들 필요가 있는지.
5. **스텔스 소싱 범위** — 크롤링 대상 사이트와 허용 범위. 기존 파이프라인처럼 뉴스 RSS·
   네이버 API 중심으로 갈지, THE VC·혁신의숲 페이지까지 볼지.
6. **개인정보** — 회의록의 참석자 실명·연락처를 산출물과 캐시에 남길지. 기본은 이름만 남기고
   연락처는 캐시에서 마스킹하는 쪽을 권장한다.
