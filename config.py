"""전역 설정 — 시트/열 구조, 스테이지 분류 체계, 우선순위, API/레이트리밋."""
import os
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
CHECKPOINT_DIR = BASE_DIR / "checkpoints"

# ---------------------------------------------------------------- 입력 파일
EXCEL_PATH = DATA_DIR / "Startup_DB.xlsx"
# 1차 조사 완료분(425행)이 기록된 로그 시트. 엑셀에 시트가 없으면 아래 CSV로 대체.
UPDATE_LOG_CSV_FALLBACK = DATA_DIR / "스테이지_업데이트_26.07.csv"
# 스크리닝(1단계) 기완료 50개사 — 1단계 스킵, changed/ambiguous만 2단계 편입
SCREENED_CSV = DATA_DIR / "스크리닝_기완료_50개사.csv"

CHECKPOINT_PATH = CHECKPOINT_DIR / "results.jsonl"

# ---------------------------------------------------------------- 시트 구조
SHEET_ALL = "All(전체기업)"
HEADER_ROW = 3
DATA_START_ROW = 4

COL_BIZNO = "B"        # 사업자등록번호 (키값)
COL_NAME_KR = "C"      # 국문 회사명
COL_NAME_EN = "D"      # 영문 회사명
COL_INDUSTRY = "E"     # 업종
COL_STAGE = "G"        # 투자 스테이지 (수정 대상 — 이 열만 변경)
COL_HTYPE = "H"        # 재단연관기업 분류 (우선순위 기준)
COL_WEBSITE = "M"      # Website

SHEET_UPDATE_LOG = "스테이지 업데이트(26.07)"
SHEET_HISTORY = "업데이트 내역"

UPDATE_LOG_HEADER = [
    "행", "국문 회사명", "기존 스테이지", "최신 스테이지",
    "반영 여부", "신뢰도", "근거", "출처 URL", "비고",
]

# ---------------------------------------------------------------- 분류 체계
STAGES = [
    "Pre-seed", "Seed", "Pre-A", "Series A", "Series B", "Series C",
    "Series D", "Series E ~", "Pre-IPO", "알 수 없음",
]
# IPO('YY) / M&A('YY) 는 연도 표기 필수 — 이 형식이면 '종결 상태'로 조사 제외
TERMINAL_STAGE_RE = re.compile(r"^(M&A|IPO)\((~)?'\d{2}\)$")
# 연도 없는 M&A/IPO — 조사 대상 (연도를 찾아 보정)
BARE_TERMINAL_RE = re.compile(r"^(M&A|IPO)$")
STAGE_WITH_YEAR_RE = re.compile(r"^(M&A|IPO)\((~)?'(\d{2})\)$")

# ---------------------------------------------------------------- 조사 범위
# 조사 대상 우선순위 그룹 (1=Type 1, 2=디데이, 3=Type 2, 4=공란/기타, 5=Type 3)
# 기본: Type 1·디데이·Type 2 만 조사. 전체로 되돌리려면 TARGET_PRIORITIES=1,2,3,4,5
TARGET_PRIORITIES = {
    int(x) for x in os.environ.get("TARGET_PRIORITIES", "1,2,3").split(",") if x.strip()
}

# ---------------------------------------------------------------- 우선순위 (H열)
def priority_of(htype: str) -> int:
    """H열 값 → 우선순위 그룹 (1이 가장 먼저)."""
    h = (htype or "").strip()
    if "Type 1" in h:
        return 1
    if "디데이" in h:
        return 2
    if "Type 2" in h:
        return 3
    if "Type 3" in h:
        return 5
    return 4  # 공란/기타


# ---------------------------------------------------------------- 검색 모드
# "rss"       : 구글 뉴스 RSS로 직접 검색 후 Gemini(무료 티어)가 판단 — 결제 불필요 (기본)
# "grounding" : Gemini Google Search grounding — 유료 티어(결제 등록) 필요
SEARCH_MODE = os.environ.get("SEARCH_MODE", "rss")

# THE VC 페이지 교차 확인 (기본 꺼짐 — 외부 차단으로 재시도 지연 발생해 제외.
# 켜려면 환경변수 THEVC_ENABLED=1)
THEVC_ENABLED = os.environ.get("THEVC_ENABLED", "0") == "1"

# 네이버 뉴스 검색 API (선택 — 키가 있으면 구글 뉴스와 병행 검색, 무료 25,000회/일)
# developers.naver.com 에서 애플리케이션 등록 후 발급
NAVER_CLIENT_ID = os.environ.get("NAVER_CLIENT_ID", "")
NAVER_CLIENT_SECRET = os.environ.get("NAVER_CLIENT_SECRET", "")

# ---------------------------------------------------------------- Gemini API
GEMINI_API_KEY_ENVS = ("GEMINI_API_KEY", "GOOGLE_API_KEY")
MODEL_SCREEN = os.environ.get("MODEL_SCREEN", "gemini-3.5-flash")
MODEL_VERIFY = os.environ.get("MODEL_VERIFY", "gemini-3.5-flash")

# 2단계 검증에 사용할 상위 모델 목록. 빈 값이면 기존처럼 MODEL_CANDIDATES 전체를 허용한다.
VERIFY_MODELS = [m.strip() for m in os.environ.get(
    "VERIFY_MODELS", "gemini-3.5-flash,gemini-3-flash-preview"
).split(",") if m.strip()]

# 무료 티어는 모델별 일일 한도가 따로 있다 (예: 3.5-flash는 20회/일).
# 한 모델의 일일 한도가 소진되면 아래 순서로 자동 전환한다.
MODEL_CANDIDATES = [m.strip() for m in os.environ.get(
    "MODEL_CANDIDATES",
    "gemini-3.5-flash,gemini-3-flash-preview,gemini-3.1-flash-lite,"
    "gemini-2.0-flash,gemini-2.0-flash-lite,gemma-4-31b-it,gemma-4-26b-a4b-it",
).split(",") if m.strip()]

REQUEST_DELAY_SEC = float(os.environ.get("REQUEST_DELAY_SEC", "6"))  # 무료 티어 ~10RPM

# 1단계 스크리닝 배치 크기 — N개 회사를 한 요청에 묶어 일일 요청 한도를 N배 아낌.
# 2단계 정밀 검증은 품질을 위해 항상 회사별 개별 호출. (rss 모드에서만 배치 적용)
SCREEN_BATCH_SIZE = int(os.environ.get("SCREEN_BATCH_SIZE", "8"))
BACKOFF_SECONDS = [2, 4, 8, 16]  # 429/5xx 지수 백오프
RETRYABLE_CODES = {429, 500, 502, 503, 504}

# 2단계 교차 확인 우선 소스 (동명 기업 확인 필수)
TRUSTED_SOURCES = [
    "platum.kr", "venturesquare.net", "wowtale.net",
    "thebell.co.kr", "thevc.kr", "innoforest.co.kr",
]

# 회사명이 너무 짧거나 일반명사성일 때 업종 키워드를 붙이기 위한 휴리스틱
GENERIC_NAME_MAX_LEN = 2

# ================================================================ 모니터링 공통
# 두 모니터가 함께 쓰는 경로/모델 설정만 여기 둔다. 모니터별 설정은 각 폴더의
# config.py 에 분리되어 있다:
#   ① 500 Global 프로그램 추적  → monitors/global500/config.py (실행: monitor_500global.py)
#   ② AC 업체 동향 감시        → monitors/ac_watch/config.py  (실행: monitor_ac.py)
OUTPUT_DIR = BASE_DIR / "output"                    # 리포트 저장 위치 (모니터별 하위 폴더)
SNAPSHOT_DIR = CHECKPOINT_DIR / "snapshots"         # 페이지 스냅샷 (변경 감지용)
MONITOR_LOG_PATH = CHECKPOINT_DIR / "monitor_log.jsonl"
PAGE_MAX_CHARS = int(os.environ.get("PAGE_MAX_CHARS", "12000"))  # 페이지당 수집 상한

# 모니터링에 사용할 Gemini 모델 (스크리닝 모델 재사용)
MODEL_MONITOR = os.environ.get("MODEL_MONITOR", MODEL_SCREEN)
