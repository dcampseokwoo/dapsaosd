# US FORGED 후보 선별 엔진 — 인수인계 (HANDOFF)

> 이 문서만 읽고 이어서 작업할 수 있게 쓴다. 대상 프로그램: 디캠프 x HAX Hardtech
> Pre-Program "US FORGED". 작업 지시서 원본: `docs/us_forged/US_FORGED_ENGINE_SPEC.md`,
> 공고문: `docs/us_forged/US_FORGED_공고문.docx`.

---

## 0. 작업 완료 상태 ✅ (v1-final-352 · Phase 1 자산분리 · Phase 2 도시에 · Phase 3 크롤러[수집 대기])

**엔진 작업 종료.** 최종 산출물 검수 완료. 완성 지점 = 태그 `v1-final-352`
(브랜치 `claude/file-batch-send-ank4hr` = `us-forged-engine`).

**Phase 1(범용 엔진 전환·자산 분리) 완료**: `screening/uf_*` → **`engine/engine_*` 패키지**,
공고 종속 데이터 → **기준팩 `criteria/237489/`**(prompt.md·criteria.json·exclusions.yaml·
golden_set.yaml), 배제 목록 → `config/global_exclusions.yaml`(공고무관)+기준팩(공고전용).
**로직 불변·위치만 이동** — 재현 검증 통과(352/162/128/62·이메일 172·must_pass 15/15·
must_fail 19/21·스테이지 이탈 0·중복 0·래칫 62/62). 캐시 키 3상수 불변(마이그레이션 불필요).
`screening/`는 레거시(HAX/500)로 표기(`screening/README.md`). 규칙 v3 구현은 Phase 6.

**Phase 2(도시에 스키마 + 캐시 마이그레이션) 완료**: 공고 무관 '사실'을 8축으로 기록하는
`engine/engine_dossier.py`(physical_product·tech_ownership·value_chain_position·end_use·
industry_domains·maturity·regulatory_class·market_orientation, 각 축 {value,evidence,source,
needs_generation}). classification.json 1,157건 → `data/cache/dossier/dossiers.json`
**유도-only(LLM 0)** 변환. 유도 불가 축은 needs_generation 플래그(전량 생성=Phase 4:
tech_ownership 1,139·regulatory 1,142·market 1,148·value_chain 1,042·end_use 846·maturity
561·physical 179·industry 0). 역산 92.1%(제품축 ~95%); 복원 불가 = tech_ownership 갭 50
(rule 9a)+엔티티레이어 35+경계 6. **읽기 전용 파생물** — 파이프라인은 classification.json
사용(352 불변, 롤백 보존). 캐시 키 3상수 불변. 도시에 기반 전환은 Phase 6.

**Phase 3(홈페이지 수집) — 크롤러 완성, 실제 수집 0건(egress 대기). 사용법: `docs/us_forged/CRAWLER.md`**
- 크롤러 `engine/engine_website.py`: robots 존중·딜레이·재개·사명 `<ENTITY_NAME>` 치환·
  MISMATCH/파킹 판별·access_status 7종·텍스트만·per-company `data/cache/website/{id}.json`.
  **순수 함수 테스트 9건 통과. 실제 수집 0건.** 의존성: `requests` 만(나머지 stdlib).
- **중단 사유**: egress 프록시가 **세션 생성 시점에 고정**되어 이 세션에서는 열 수 없음
  (정책을 켜도 현 세션 미반영). 외부 호스트 전부 403.
- **재개 방법(웹 egress 열린 새 세션/로컬)**:
  1. `from engine import engine_website as W; assert W.egress_available()` 프리체크 통과 확인
  2. **발송 리스트 352곳 먼저** → `W.report()` 로 수집률·품질 확인 + 포레·메텔·메타맵 3사 검증
  3. 문제없으면 **전체**(website 있는 전 기업, 3,424곳 100% 채워짐)
- **🚨 `crawl()`이 `EgressBlocked`를 던지면 절대 우회하지 말 것.** try/except 로 삼키거나
  precheck 를 끄면 프록시 403 이 전부 **거짓 `DOMAIN_EXPIRED`** 로 기록되어 3,424곳이
  "홈페이지 없음"으로 오분류되고 그 사실을 영원히 모른다. **환경을 고쳐라(egress 열기), 코드를 우회하지 마라.**

**Phase 4 예산 추정(사전, 수집률 시나리오별 — egress 투자 가치 판단용)**
- 범위: 전 기업 도시에 생성 ≈ **3,400곳**(기존 1,157 + 신규 2,257). 생성 대상 축 = 소개문으로
  안 풀리는 5개(end_use·tech_ownership·value_chain·regulatory·market) = 규칙 v3 판정을 가르는 축 전부.
- **호출 수는 수집률과 거의 무관**(기업당 도시에 생성 1콜; 웹 텍스트는 *호출 수*가 아니라
  *입력 토큰·결과 품질*을 바꿈). 단일 패스 ~3,400콜 / 3회 다수결(불안정 ~22% 가정) ~4,900콜.
  (현재 파이프라인 관련분 1,157곳만 하면 ~1,157단일 / ~1,650다수결.)
- 수집률이 바꾸는 것 = **UNCLEAR 비율(자산 품질)**과 재실행 낭비:

  | 수집률 | 예상 호출 수(전량) | 5개 축 블렌드 UNCLEAR | 결과 |
  |---|---|---|---|
  | **0%**(소개문만) | ~3,400 / ~4,900 | **~50%** | 규칙 핵심 축이 대량 UNCLEAR(메텔·메타맵·포레 유형). 자산으로 못 씀 → 웹 확보 후 **재실행 → 콜 낭비** |
  | **50%** | ~동일 | **~30%** | 절반은 해소, 절반 desc-only. 부분 자산 |
  | **80%** | ~동일 | **~15%** | 대부분 해소 → **한 번 만들면 재사용** 성립 |
- 축별: end_use·tech_ownership·value_chain·regulatory 는 웹으로 크게 개선. **market_orientation 은
  웹으로도 잘 안 풀림**(수출 타겟 명시 드묾) → 높은 UNCLEAR 유지, 별도 소스 필요.
- **판단**: 호출 수가 시나리오 무관 거의 같으므로 **웹 수집은 "예산은 그대로, 품질만 좌우"**.
  0%로 돌리면 같은 콜을 쓰고도 규칙 v3 축(Q1/Q2/Q4/9a)이 반쯤 UNCLEAR → 재실행이 불가피.
  → **egress 확보 후 Phase 4 가 비용 효율적.** (추정치이며 실 수집률·프롬프트로 변동.)

- 최종 산출물: `output/screening/us_forged_shortlist.xlsx`
- 발송 리스트 **352**(T1 162 · T2 128 · T3 62), 이메일 172 / 연락처 필요 180
- 골든 must_pass 15/15 · must_fail 19/21 · 래칫 62/62(회귀 없음) · 스테이지 이탈 0
- **DB 원천 문제는 `docs/us_forged/DB_ISSUES.md`** 로 분리(디캠프 DB 관리자 전달용):
  ⓐ "Seed" 스테이지 오기재 8건(배제한 상장사 전부가 Seed — 패턴) ⓑ 사업자번호 중복·오타
  21건 ⓒ 타겟 국가 98.5% 결측.

### 재개할 때 (필요할 때만)

**① 스냅샷이 갱신되면(새 GBD DB xlsx):**
```
# 1. 새 파일을 data/snapshots/ 에 두고 engine_snapshot.DEFAULT_SNAPSHOT 경로 갱신
# 2. 신규/변경 행만 분류(캐시는 biz_no+소개문해시 키라 기존 행은 캐시 적중, 예산 절약)
python -c "from engine import engine_shortlist as S; print(S.summarize(S.build()))"  # 캐시 미스 확인
#    → 캐시 미스(신규 행)만 소개문으로 분류해 engine_classify.put() 후 save_cache()
# 3. 워크북 재생성 + 회귀 확인
python -c "from engine import engine_xlsx as X; print(X.build())"
python -m pytest tests/ -q && python -m tests.golden_ratchet
```
전체 재분류(1,157 전건)는 **금지** — 예산 자산. 캐시 미스만.

**② 배제 기업을 추가할 때(신규 상장사·therapeutics 발견):** 코드 수정 없이
`config/global_exclusions.yaml` 편집:
- `exclusions`: 확실한 배제(상장사 등) → `excluded_entity` + `명시_배제` 시트. `{biz_no, name, reason}`.
- `established_suspects`: 배제까진 아닌 의심 → T3 강등 + 플래그. `{biz_no, name, note}`.
- `duplicate_merges`: 1자리차로 못 잡는 확인된 동일 회사 → 강제 병합. `{name, biz_nos:[...], note}`.
- 신약 바이오텍은 소개문 재분류로 `therapeutics` 판정(프롬프트 v6). 예: `engine_classify.put()`
  으로 해당 biz_no에 `verdict=therapeutics` 기록(§4 참조).
편집 후 `X.build()` 재실행하면 반영. yaml만 바꾸면 되고 테스트/래칫은 자동 통과.

---

## 1. 현재 상태 (spec §0~§8)

| 섹션 | 내용 | 상태 |
|---|---|---|
| §0 | 목적 재정의(선발 아님=배제+정렬), selected→send 명명 | ✅ |
| §5 | 골든셋 하네스 + 래칫 baseline(전부통과 아니라 "baseline보다 나빠지지 않음") | ✅ |
| §7 | 스냅샷 고정 + diff 모드 **인터페이스만**(candidate_impact 는 shortlist_fn 주입형, 미구현) | ✅(부분) |
| §2 | 중복/신원 판정(병합 전 신원 우선) | ✅ |
| §3 | 스테이지 재작성(명시 매핑·미매칭 예외·Pre-A 예외버킷) | ✅ |
| §1 | 라벨 폐기 → 소개문 LLM 분류(1,157건 캐시, 풀런 시 3회 다수결) | ✅ |
| §4 | 배제 강화(해외법인 3형식·법인격) | ✅ |
| §6 | 출력 스키마(evidence 전문·이메일·uid·소개원문·티어) | ✅ |
| §8 | 자체 채점 + 리젝트 감사(무작위 30) | ✅ |

**최신 산출물**: `output/screening/us_forged_shortlist.xlsx` (프롬프트 v6 반영)
- 발송 리스트 **352** (T1 **162** · T2 **128** · T3 **62**)
- 이메일 보유 **172** / 연락처 확보 필요 **180**
- 핵심 지표: 골든 must_pass **15/15**, must_fail **19/21**(잔여: 마린테크노=T2 플래그 /
  Lihua=§4 배제), 스테이지 이탈 잔류 **0**, 래칫 62/62(회귀 없음)
- v6 결과: 치료제·신약 바이오텍 **15곳 발송 제외**(`excluded_therapeutics`, `치료제_배제`
  시트). 기기·소재·분석장비·약물전달 디바이스는 hardtech 유지(퀀타매트릭스·켈스·아이메디컴·
  티아이·엔도핀·브이에스아이·셀라이온바이오메드 등).
- v4/v5 결과: 뷰티/미용 신호 T1=0. 소비재(스마트 텀블러·홈트·코딩완구·기능성 원단 등)
  용도 축으로 consumer 배제. 산업부품 OEM(선진정공·코엠고)은 hardtech 유지.
- 분야 컬럼(Q1): Other Deeptech 268→**32**(진짜 미분류만), blank **0**. 11개 분야 중
  Quantum만 0(시드 DB에 없음). 원료·시약은 Healthtech Device 아님으로 정정.
- 명시 배제 **8곳**(휴젤 + 상장사 7: 솔루엠·쏠리드·휴마시스·필옵틱스·해성옵틱스·올릭스·
  한국비엔씨), established_suspect **15곳** → T3. 스테이지 'Seed' 오기재 확인 3건(휴젤·
  올릭스·한국비엔씨) 요약 경고에 명시.
- 중복 병합 강화: 정규화 사명 그룹핑(표기차 흡수, 워커린스페이스) + 사업자번호 1자리차
  자동 병합(아폴론·크로스포인트) + 수동 병합 목록(티아이). 4쌍 중복 해소.

---

## 2. 파일 지도 & 실행

> **⚠ 현행 엔진은 `engine/` 패키지다. `screening/`는 레거시(2026-08 이전 HAX/500 엔진)이며
> 현행 파이프라인과 무관하다** — `screening/README.md` 참조. 특히 `screening/rules_v3.py`는
> 우리 판정 규칙 v3(`RULES_v3.md`)와 **이름만 겹치는 무관한 레거시**다(건드리지 말 것).
> 공고 종속 데이터는 **기준팩 `criteria/237489/`**(prompt.md·criteria.json·exclusions.yaml·
> golden_set.yaml)로 분리됨 — 기준팩만 교체하면 다른 공고 평가. 활성 팩 = `engine/criteria_pack.py`
> (env `ENGINE_CRITERIA`, 기본 237489).

**파이프라인 순서** (`engine_shortlist.assess`): **dedup(§2) → 배제(§4) → 스테이지(§3) → 분류(§1) → 티어**

| 모듈 (현행 `engine/`) | 역할 |
|---|---|
| `engine/engine_snapshot.py` | 스냅샷 xlsx 로더 + 사업자번호 정규화(valid/foreign/malformed) + **uid**(placeholder는 사명#행인덱스) + provenance/run_metadata |
| `engine/engine_dedup.py` | §2 신원 판정 중복 병합. **정규화 사명(_norm_name)으로 그룹핑** → 클러스터(동일 사업자번호 / **1자리차 오타 is_one_digit_diff** / `duplicate_merges` 수동목록)로 병합. 2자리차 이상은 similar_biz_no_suspect 플래그 |
| `engine/engine_exclude.py` | §4 해외법인·법인격 배제 + 명시배제(global+pack 병합) |
| `engine/engine_stage.py` | §3 stage_bucket. **정규식·예외규칙을 기준팩 `stage_policy`에서 컴파일** |
| `engine/engine_classify.py` | §1 분류. **PROMPT/enum/version을 기준팩에서 로드**. 캐시 read/write. `MODEL`은 캐시키 상수라 코드에 고정. verdict에 **therapeutics** 포함 |
| `engine/engine_core.py` | 레이어 facade(구 uf_engine). `classify()`=캐시 읽기. entity_verdict는 골든 baseline 비교용으로 레거시 `us_forged._NON_STARTUP` 참조 |
| `engine/engine_golden.py` | 골든셋 로더(**인프라 tests + 기준팩 판정 골든 병합 → 62 케이스**) + evaluate_all |
| `engine/engine_pilot.py` | 파일럿 표본(경계 5유형 층화 + 시드 고정) |
| `engine/engine_fullrun.py` | 전체 분류 집계 + 불안정 서브셋 + **3회 다수결 finalize** |
| `engine/engine_shortlist.py` | **파이프라인 조립**: assess()/build()/tier() |
| `engine/engine_xlsx.py` | §6/§8 산출물 워크북(구 uf_forged_xlsx) |
| `engine/engine_diff.py` | §7 스냅샷 diff |
| `engine/criteria_pack.py` | 활성 기준팩 로더(criteria.json·prompt.md·exclusions.yaml) |
| `engine/engine_dossier.py` | **공고 무관 도시에**(8축 사실). classification.json→`data/cache/dossier/dossiers.json` 유도-only 마이그레이션(migrate/coverage/back_derive_verdict). 읽기 전용 파생물(Phase 6에서 파이프라인 전환) |
| `engine/engine_website.py` | **Phase 3 홈페이지 크롤러**. crawl/crawl_one/report + 순수함수(extract_text·mask_entity·detect_lang·classify_content·discover_pages). egress 필요(egress_available precheck, 차단 시 EgressBlocked). `data/cache/website/{id}.json` |

**기준팩** `criteria/237489/`: `prompt.md`(분류 프롬프트 v6) · `criteria.json`(prompt_version·
program_fields enum·stage_policy·verdicts·fit_rules[데이터만, Phase 6 구현]) · `exclusions.yaml`
(공고 전용, 현재 비어있음) · `golden_set.yaml`(판정 픽스처 must_pass 15/must_fail 21).
**배제 레지스트리**: `config/global_exclusions.yaml`(공고 무관: 상장사 8·suspects 15·법인격·
해외법인·duplicate_merges) + 기준팩 `exclusions.yaml`(공고 전용).

**워크북 빌드**: `python -c "from engine import engine_xlsx as X; print(X.build())"`
**테스트**: `python -m pytest tests/ -q` / **래칫**: `python -m tests.golden_ratchet`

---

## 3. 합의된 판정 규칙 (반드시 지킬 것)

1. **이 엔진은 "선발"이 아니라 "배제 + 우선순위 정렬"이다.** 공고 핵심 요건 중
   **Lab-scale 프로토타입 · 미국 진출 의지 · 창업자/CTO 기술 전문성**은 GBD DB에
   컬럼 자체가 없어 **원리적으로 검증 불가**(타겟 국가 98% 결측). 출력물에
   "선발/요건충족" 표현 금지, 통과 판정엔 이 미검증 요건을 함께 노출.
2. **판정 기준**: "미국 고객에게 팔 수 있는 **물리적 제품·소재·장비·디바이스를 직접
   설계·제조하는가**." SW로 하드웨어를 제어·분석·중개만 하면 software_only.
3. **수직계열화 규칙**: 소재·부품·공정을 **자체 개발/수직계열화**하면 hardtech,
   **완제품 조립·수탁(OEM/ODM)만** 하면 consumer. 최종 제품이 소비자용인지는 기준이
   아니다(소비자용이라도 핵심 소재 자체개발이면 hardtech + consumer_facing 플래그).
4. **애매하면 배제가 아니라 후순위(T3) 또는 플래그.** 이메일 발송은 비용이 없으므로
   unclear·저신뢰는 발송 리스트에 넣고 순위만 낮춘다. (제3의 "검토" 버킷 없음.)
5. **골든셋 수정은 DB 원문(1줄 소개·기술 컬럼)에 명시적 근거가 있을 때만.** 근거가
   없으면 fixture 를 고치지 말고 **프롬프트를 고친다.** (골든셋 상단 주석에도 명시.)
6. **업종(CB) 라벨은 보조 신호일 뿐, 절대 단독 판정 근거로 쓰지 않는다.** 이게 원래
   결함의 뿌리였다(한글 레거시 라벨·다중 라벨이 진짜 하드테크를 전멸시킴).
7. **치료제·신약 바이오텍은 therapeutics(발송 제외, v6).** 치료제·신약 후보물질·백신·
   항체·의약품 **자체**를 개발/제조하면 물리적 하드웨어가 아니므로 verdict=therapeutics →
   `excluded_therapeutics`. **단 진단기기·수술기구·분석장비·약물전달 디바이스·의료용
   소재처럼 '기기·소재'를 만드는 곳은 hardtech 유지.** '약을 만든다'=therapeutics,
   '약을 만들 기기·소재·장비를 만든다'=hardtech. 갈리면 배제 말고 hardtech+low→T3.

**verdict**: hardtech / software_only / consumer / **therapeutics** / not_a_startup / unclear.
**disposition**: send / excluded_entity / excluded_stage / excluded_field /
**excluded_therapeutics** / not_a_startup.
**티어 정의**: T1 = hardtech·confidence high·플래그 없음 / T2 = hardtech인데
consumer_facing 또는 maturity_signal 있음 / T3 = unclear 또는 confidence low.

---

## 4. 분류 캐시 관리 — **⚠ 예산 자산. 함부로 무효화하지 말 것**

`data/cache/classification.json` (약 618KB, **1,157건**; 과거 문서의 '1,159'는 풀런 투입 엔티티 수 라벨로, 실제 저장 캐시는 1,148→1,157). **예산을
들여 만든 자산이다. 캐시 키를 바꾸거나 대량 재분류를 돌리기 전에 반드시 계획 보고.**

- **캐시 키** = `사업자번호(biz_no) | 소개문 SHA256[:16] | 모델명`
  - 프롬프트 버전은 **키가 아니라 항목 필드**(`prompt_version`)로 기록 → v2/v3 선택적
    재분류를 혼재·추적. (v2/v3 를 키에 넣으면 부분 재분류가 캐시 전체를 무효화함.)
  - **식별은 uid**(placeholder 사업자번호 = 사명#행인덱스)로 dedup/finalize 에서 처리.
    캐시 키의 biz_no+소개문해시는 placeholder라도 소개문이 달라 충돌하지 않음.
- **프롬프트 버전 이력** (프롬프트 전문=`criteria/237489/prompt.md`, `PROMPT_VERSION`=criteria.json):
  - **v1**: 핵심 판정 질문 + 경계 5유형(수탁/상사/용역/하드+SaaS/기성제조)
  - **v2**: 수직계열화 규칙 + `consumer_facing_end_product`·`maturity_signal` 필드
  - **v3**: 화장품/뷰티 기본값 명시(소재 자체개발 명시 없으면 consumer) +
    `matched_program_field` **11 enum 강제**
  - **v4**: OEM/ODM **소비재 완제품** 수탁=consumer(산업부품 OEM 제외) + **용도 축**
    (화장품·미용·에스테틱·이너뷰티 용도 소재·기기=consumer, 산업/임상의료 병기 시 예외).
  - **v5**: 용도 축을 **소비재 전반**으로 확장(생활·운동·교육·취미·의류·식음료·반려·주방·
    가구 용도면 센서·전자·소재 내장돼도 consumer). 재분류: 소비재 신호 항목만(나머지 무손상).
  - **v6**: **therapeutics verdict 추가**(치료제·신약·백신·항체·의약품 자체개발=발송 제외,
    기기·소재는 hardtech 유지). 재분류: therapeutics 신호 발송항목 18건만 v6로 덮어씀
    (15 therapeutics 배제 + 엔비언스 hardtech·low + 대명화학·예쉬컴퍼니 consumer).
    나머지 캐시는 v5 그대로(선택적 재분류 — 키에 prompt_version 안 넣는 설계 덕).
  - 분야 라벨 재배정(Q1): `data/cache/field_prompt.txt`(라벨 전용, verdict 불변). 원료·시약은
    Healthtech Device 금지 → 소재/Other. Other Deeptech 허용하되 빈칸 금지.
- **재분류 범위 좁히기**: 신호 있는 항목만 파일로 추려 배치 분류 후 캐시에 덮어쓴다
  (예: 뷰티 신호 64건 → `beauty_out_*.json` → `engine_classify.put`). 전체(1,159) 재실행
  금지. 불안정 서브셋 선별은 `uf_fullrun.recheck_subset()`(low/unclear/consumer_facing/
  maturity), 3회 다수결은 `uf_fullrun.finalize()`.
- 분류 실행 방식(현 세션): 서브에이전트가 `data/cache/classify_prompt.txt`(=PROMPT)와
  항목 JSON을 읽어 배치별 결과 파일 기록 → 집계. 런타임 API 키는 repo에 없음(캐시 우선).

---

## 5. 미해결 이슈

1. **상장사/대기업 혼입 — 스테이지 데이터 오류(부분 처리됨).** §3로 안 잡힘(스테이지 값
   문제). 처리: `config/global_exclusions.yaml`(사업자번호 명시 관리, 골든셋 방식):
   - **exclusions**(8): 휴젤 + 상장사 7(솔루엠 코스피248070·쏠리드 코스닥050890·휴마시스
     205470·필옵틱스 161580·해성옵틱스 076610·올릭스 226950·한국비엔씨 256840)
     → excluded_entity, `명시_배제` 시트 노출. 새 상장사 발견 시 여기에 사업자번호로 추가.
     **스테이지 'Seed' 오기재 확인 3건: 휴젤·올릭스·한국비엔씨**(요약 경고에 명시).
   - **established_suspects**(15): 알테오젠바이오로직스·녹십자수의약품·로킷헬스케어·세미파이브·
     알피니언메디칼·콘텔라·테크로스·대한조선·창명해운·현대피팅 + 네패스라웨·아리셀·우양에이치씨·
     코세스지티·이너트론 → 배제 아니라 established_suspect 플래그 + **T3 강등**(사용자 직접 판단).
     (알테오젠바이오로직스·녹십자수의약품은 v6에서 therapeutics로도 배제됨.)
   - **duplicate_merges**(수동 병합): 티아이(647-85-02411 개인 + 671-81-00456 법인 = 동일
     안과 의료기기 회사). 1자리차 알고리즘이 못 잡는 확인된 동일 기업만 여기에 명시.
   - **미해결**: 스테이지 오기재는 엔진 밖 문제 → **디캠프 DB 관리자에게 별도 통보 필요**.
     `스테이지_미상` 시트(발송 리스트 중 스테이지 미상 ~255)를 사용자가 훑어 배제 목록 추가.
     기성 제조 중소기업 클러스터(서진산업·신영금속·우창공업 등)는 maturity_signal 로 표시됨.
2. **분야 세분(Q1) + 소비재 v5 — 해결됨.** Other Deeptech 268→**32**(진짜 미분류만),
   blank **0**. 11개 분야 중 Quantum만 0(시드 DB에 없음). 원료·시약 Healthtech 오분류 정정
   (에이피테크놀로지·웰진 등). 소비재(에잇컵스·리얼디자인테크·모션블루·제일저지 등) v5로
   consumer 배제. 캐시미스 9건 재분류(워커린스페이스→Aerospace 등). verdict·티어 불변 원칙 유지.
   잔여 0: Manufacturing Process Innovation·Quantum(시드 KR DB에 드문 카테고리, 실제 부재
   가능성). 재배정은 `data/cache/field_prompt.txt`(분야 라벨 전용) 로.
3. **골든 must_fail 19/21**: 잔여 2건 — 마린테크노(화장품 원료, 분류기 hardtech이나 T2+
   consumer_facing 플래그 / 골든 consumer 유지 = 정책상 경계)·Lihua(§4가 배제하므로
   파이프라인상 문제 아님). (v4로 크레신·이지코스텍·파인유얼뷰티는 consumer 전환 완료.)
4. **사업자번호 오타 의심**: 오믈렛 `563-88-23981` vs `563-88-02981`(similar_biz_no_
   suspect), 랜딩 `725-870-2428`(malformed), 스피드플로어 앞뒤 공백. 중복_엔티티 시트에
   노출됨 — DB 관리자 정정 대상.

---

## 6. 작업 관행

- **코드 수정 전 계획을 보고하고 승인받는다.** 큰 변경(분류 방식·캐시 키)은 특히.
- **커밋 시 래칫이 자동 실행**(pre-commit 훅). "baseline보다 나빠지지 않음"을 검사 —
  회귀 시 커밋 차단. 개선했으면 `python -m tests.golden_ratchet --update-baseline`.
- **fixture와 데이터가 충돌하면 데이터(DB 원문)부터 확인**하고 사용자에게 알린다.
  골든셋이 항상 옳다고 가정하지 않는다(지금까지 fixture 오류 5건 교정).
- **지출 한도가 불안정**하다. 대량 서브에이전트 실행 전 핑으로 확인하고, 실패 시
  누락 배치만 재개(파일이 이미 있는 배치는 건너뜀).

---

## 7. 재개 방법

1. 저장소 클론 후 개발 의존성 설치:
   ```
   pip install -r requirements-dev.txt        # pytest, PyYAML, openpyxl
   ln -sf ../../scripts/pre-commit-golden.sh .git/hooks/pre-commit   # 래칫 훅(선택)
   ```
2. 상태 확인:
   ```
   python -m pytest tests/ -q
   python -m tests.golden_ratchet             # baseline 대비 회귀 없음 확인
   python -c "from engine import engine_shortlist as S; print(S.summarize(S.build()))"
   python -c "from engine import engine_xlsx as X; print(X.build())"   # 워크북 재생성
   ```
3. **새 세션 첫 메시지 예시**:
   > "docs/us_forged/HANDOFF.md 읽고 이어서 작업하자. 다음은 [남은 established_suspect·
   > 스테이지 미상 시트 사용자 검토 반영 / §7 diff candidate_impact 구현 / 신규 상장사·
   > therapeutics 추가 발견 시 config 반영] 중 무엇을 하면 돼. 캐시는 예산 자산이니
   > 재분류 범위를 먼저 좁혀서 계획을 보고해줘."

**최근 완료(최종 라운드)**: ① 중복 4쌍 병합(정규화 사명+1자리차+수동목록) ② 상장사 7곳
명시배제 + established_suspect 5곳 추가 + 요약 경고 강화 ③ therapeutics verdict(v6)로
신약 바이오텍 15곳 발송 제외 ④ 필드/verdict 재확인(대명화학·예쉬컴퍼니 consumer 전환).
