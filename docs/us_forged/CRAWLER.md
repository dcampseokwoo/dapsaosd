# Phase 3 홈페이지 크롤러 사용법 (`engine/engine_website.py`)

> 상태(2026-08): **크롤러 완성·순수함수 테스트 9건 통과. 실제 수집 0건**(이 세션 egress 차단).
> 웹 egress 허용 세션 또는 로컬에서 실행. 결과는 공고 무관 영구 자산.

---

## ⚠ 가장 중요 — `EgressBlocked` 를 절대 우회하지 말 것

`crawl()` 은 시작 전 `egress_available()` 로 외부 접근을 프리체크한다. 막혀 있으면
**`EgressBlocked` 예외로 즉시 중단**한다. 이걸 try/except 로 삼키거나 우회하면,
프록시 403 이 전부 거짓 `DOMAIN_EXPIRED` 로 기록되어 **3,424곳이 "홈페이지 없음"으로
오분류**되고 우리는 그 사실을 영원히 모른다. 예외가 뜨면 **환경을 고쳐라(egress 열기),
코드를 우회하지 마라.**

---

## 필요한 패키지

- **`requests` 만 있으면 된다.** 나머지는 표준 라이브러리(`urllib`, `html.parser`).
- bs4/lxml 불필요(stdlib `html.parser` 로 텍스트 추출).
- 프록시 환경이면 `requests` 가 `HTTPS_PROXY` 를 자동 사용. 프록시가 자체 CA 를 쓰면
  `/root/.ccr/ca-bundle.crt` 를 자동으로 `verify` 에 적용(있을 때). 로컬 직접 실행이면 무관.

```
pip install requests
```

## 실행 명령

먼저 egress 확인(선택):
```python
from engine import engine_website as W
print(W.egress_available())   # False 면 크롤 불가 — 환경부터 열 것
```

**발송 리스트 352곳 먼저**(수집률·품질 확인용):
```python
from engine import engine_shortlist as S, engine_website as W
send = [a for a in S.build() if a["disposition"] == "send"]
W.crawl(send, delay=2.0)      # egress 막혀 있으면 EgressBlocked 발생(정상)
print(W.report())             # 수집률·access_status 분포·텍스트 길이 분포
```

**문제없으면 전체**(website 있는 전 기업):
```python
from engine import engine_snapshot as SN, engine_website as W
rows = [r for r in SN.load_rows() if (r.get("website") or "").strip()]
W.crawl(rows, delay=2.0)
print(W.report())
```

`delay` 는 요청 간 대기(초, 기본 2.0). robots.txt 는 자동 존중.

## 출력 경로·파일 구조

- 디렉터리: `data/cache/website/`
- 파일: `{company_id}.json` (company_id = 사업자번호 기반, 파일명 안전화)
```json
{
  "company_id": "...", "biz_no": "...", "url": "https://...",
  "fetched_at": "2026-...Z",
  "access_status": "OK|NOT_FOUND|TIMEOUT|BLOCKED|NO_URL|DOMAIN_EXPIRED|MISMATCH",
  "pages": { "main": "<본문…사명은 <ENTITY_NAME> 치환>", "about": "...",
             "product": "...", "technology": "...", "usecase": "..." },
  "text_length": 1234, "lang": "ko|en|mixed|unknown"
}
```
- **사명·서비스명은 `<ENTITY_NAME>` 로 치환 저장**(사명 오염 방지). 텍스트만(이미지·스크립트 제외).

### access_status 의미(재시도 가능/불가 구분)
| status | 의미 | 재시도 |
|---|---|---|
| `OK` | 정상 수집 | — |
| `NOT_FOUND` | HTTP 404 | 불가(URL 오류) |
| `TIMEOUT` | 응답 시간 초과 | **가능** |
| `BLOCKED` | 403/401 또는 robots 금지 | 조건부 |
| `NO_URL` | DB Website 비어있음 | 불가 |
| `DOMAIN_EXPIRED` | DNS 실패·연결 거부·파킹·만료 | 불가 |
| `MISMATCH` | 접속되나 다른 회사(낡은 URL) | 불가(URL 갱신 필요) |

## 재개 방법

- **이미 수집된 건 자동 skip**: `data/cache/website/{id}.json` 이 있으면 건너뛴다.
  중단 후 다시 `crawl()` 하면 남은 것만 수집한다.
- 특정 기업을 다시 받으려면 `crawl_one(row, force=True)` 또는 해당 json 삭제 후 재실행.
- `TIMEOUT` 만 골라 재시도하려면 그 json 들을 지우고 다시 돌리면 된다.

## 검증 포인트(수집 후 반드시 확인)

`W.report()` 로 수집률·access_status 분포·텍스트 길이 분포를 본 뒤, **세 회사가 홈페이지로
판정되는지** 확인한다(홈페이지 보강이 실제 작동하는지의 증거):
- **포레** — 가정용 vs 업소용
- **메텔** — "Smart Pillow" 4단어를 넘어서는 실체
- **메타맵** — 초음파 건조기가 산업용인지
