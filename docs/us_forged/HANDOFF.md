# US FORGED 후보 선별 엔진 — 인수인계 (HANDOFF)

> 이 문서만 읽고 이어서 작업할 수 있게 쓴다. 대상 프로그램: 디캠프 x HAX Hardtech
> Pre-Program "US FORGED". 작업 지시서 원본: `docs/us_forged/US_FORGED_ENGINE_SPEC.md`,
> 공고문: `docs/us_forged/US_FORGED_공고문.docx`.

---

## 1. 현재 상태 (spec §0~§8)

| 섹션 | 내용 | 상태 |
|---|---|---|
| §0 | 목적 재정의(선발 아님=배제+정렬), selected→send 명명 | ✅ |
| §5 | 골든셋 하네스 + 래칫 baseline(전부통과 아니라 "baseline보다 나빠지지 않음") | ✅ |
| §7 | 스냅샷 고정 + diff 모드 **인터페이스만**(candidate_impact 는 shortlist_fn 주입형, 미구현) | ✅(부분) |
| §2 | 중복/신원 판정(병합 전 신원 우선) | ✅ |
| §3 | 스테이지 재작성(명시 매핑·미매칭 예외·Pre-A 예외버킷) | ✅ |
| §1 | 라벨 폐기 → 소개문 LLM 분류(1,159 전건 + 3회 다수결) | ✅ |
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

**파이프라인 순서** (`uf_shortlist.assess`): **dedup(§2) → 배제(§4) → 스테이지(§3) → 분류(§1) → 티어**

| 모듈 | 역할 |
|---|---|
| `screening/uf_snapshot.py` | 스냅샷 xlsx 로더 + 사업자번호 정규화(valid/foreign/malformed) + **uid**(placeholder는 사명#행인덱스) + provenance/run_metadata + resolve_snapshot |
| `screening/uf_dedup.py` | §2 신원 판정 중복 병합. **정규화 사명(_norm_name: 주식회사·(주)·공백 제거)으로 그룹핑** → 클러스터(동일 사업자번호 / **1자리차 오타 is_one_digit_diff** / config `duplicate_merges` 수동목록)로 병합. 2자리차 이상 근접은 병합 안 하고 similar_biz_no_suspect 플래그. name_collision/canonical_valid, duplicate_report |
| `screening/uf_exclude.py` | §4 해외법인(OC*·외국법인_*·해외법인=사업자번호 형식) + 법인격(투자목적회사·조합·SPC·N호·말미 지주) 배제 |
| `screening/uf_stage.py` | §3 stage_bucket(IN_SCOPE/UNKNOWN/EXCEPTION/OUT_OF_SCOPE, 미매칭 예외), pre_a_bucket(미국+physical), stage_rank |
| `screening/uf_classify.py` | §1 분류 **프롬프트 전문(v6)** + 캐시 read/write + normalize_field(자유표기→11 enum). verdict에 **therapeutics** 포함 |
| `screening/uf_engine.py` | 레이어 facade. `classify()`는 **캐시 읽기**(미스→unclear). stage_bucket/entity_verdict/hardtech_verdict |
| `screening/uf_golden.py` | 골든셋 로더 + evaluate_all(레이어별 케이스 평가, 래칫·리포트 공용) |
| `screening/uf_pilot.py` | 파일럿 표본(경계 5유형 층화 + 시드 고정) |
| `screening/uf_fullrun.py` | 전체 분류 집계 + 불안정 서브셋 선별 + **3회 다수결 finalize**(disagreement 플래그·이력) |
| `screening/uf_shortlist.py` | **파이프라인 조립**: assess()/build()/tier(). disposition= send/excluded_* |
| `screening/uf_forged_xlsx.py` | §6/§8 산출물 워크북 빌드 |
| `screening/uf_diff.py` | §7 스냅샷 diff(column_diff 구현 / candidate_impact 인터페이스만) |

**워크북 빌드**: `python -c "from screening import uf_forged_xlsx as X; print(X.build())"`
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

`data/cache/classification.json` (약 618KB, 1,159건 + 골든/뷰티 재분류). **예산을
들여 만든 자산이다. 캐시 키를 바꾸거나 대량 재분류를 돌리기 전에 반드시 계획 보고.**

- **캐시 키** = `사업자번호(biz_no) | 소개문 SHA256[:16] | 모델명`
  - 프롬프트 버전은 **키가 아니라 항목 필드**(`prompt_version`)로 기록 → v2/v3 선택적
    재분류를 혼재·추적. (v2/v3 를 키에 넣으면 부분 재분류가 캐시 전체를 무효화함.)
  - **식별은 uid**(placeholder 사업자번호 = 사명#행인덱스)로 dedup/finalize 에서 처리.
    캐시 키의 biz_no+소개문해시는 placeholder라도 소개문이 달라 충돌하지 않음.
- **프롬프트 버전 이력** (`uf_classify.PROMPT`, `PROMPT_VERSION`):
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
  (예: 뷰티 신호 64건 → `beauty_out_*.json` → `uf_classify.put`). 전체(1,159) 재실행
  금지. 불안정 서브셋 선별은 `uf_fullrun.recheck_subset()`(low/unclear/consumer_facing/
  maturity), 3회 다수결은 `uf_fullrun.finalize()`.
- 분류 실행 방식(현 세션): 서브에이전트가 `data/cache/classify_prompt.txt`(=PROMPT)와
  항목 JSON을 읽어 배치별 결과 파일 기록 → 집계. 런타임 API 키는 repo에 없음(캐시 우선).

---

## 5. 미해결 이슈

1. **상장사/대기업 혼입 — 스테이지 데이터 오류(부분 처리됨).** §3로 안 잡힘(스테이지 값
   문제). 처리: `config/known_exclusions.yaml`(사업자번호 명시 관리, 골든셋 방식):
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
   python -c "from screening import uf_shortlist as S; print(S.summarize(S.build()))"
   python -c "from screening import uf_forged_xlsx as X; print(X.build())"   # 워크북 재생성
   ```
3. **새 세션 첫 메시지 예시**:
   > "docs/us_forged/HANDOFF.md 읽고 이어서 작업하자. 다음은 [남은 established_suspect·
   > 스테이지 미상 시트 사용자 검토 반영 / §7 diff candidate_impact 구현 / 신규 상장사·
   > therapeutics 추가 발견 시 config 반영] 중 무엇을 하면 돼. 캐시는 예산 자산이니
   > 재분류 범위를 먼저 좁혀서 계획을 보고해줘."

**최근 완료(최종 라운드)**: ① 중복 4쌍 병합(정규화 사명+1자리차+수동목록) ② 상장사 7곳
명시배제 + established_suspect 5곳 추가 + 요약 경고 강화 ③ therapeutics verdict(v6)로
신약 바이오텍 15곳 발송 제외 ④ 필드/verdict 재확인(대명화학·예쉬컴퍼니 consumer 전환).
