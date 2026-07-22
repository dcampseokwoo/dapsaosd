"""① 500 Global 프로그램 모니터 전용 설정 (실행: monitor_500global.py).

경로·모델 등 공용 값은 루트 config.py 를 따른다.
"""
import config as root_config

SLUG = "global500"            # 스냅샷 폴더명 (checkpoints/snapshots/global500/)
REPORT_SUBDIR = "global500"   # 리포트 폴더명 (output/global500/)

# 공식 사이트 크롤링 대상 페이지 (JS 렌더링 페이지는 본문이 부족할 수 있어
# 뉴스 검색·grounding 모드로 보완한다)
PAGES = {
    "flagship":     "https://500.co/founders/flagship",        # 플래그십 AC 요강·마감일
    "founders":     "https://500.co/founders",                 # 프로그램 목록
    "companies":    "https://500.co/companies",                # 포트폴리오 리스트
    "accelerator_blog": "https://500.co/blog/tag/accelerator", # 배치 발표 블로그
}
# 포트폴리오 분석에 쓰는 페이지 (위 PAGES 의 부분집합)
PORTFOLIO_PAGE_LABELS = ("companies", "accelerator_blog")

# 지원 접수 페이지 (rolling admission — 배치별 마감일 존재)
APPLY_URL = "https://flagship.aplica.500.co"

# 뉴스 교차 검색 쿼리 (구글 뉴스 RSS + 네이버 병행)
NEWS_QUERIES = [
    '"500 Global" flagship accelerator batch',
    '"500 Global" accelerator deadline',
    '"500 글로벌" 액셀러레이터 선발',
    '"500 Global" 배치 스타트업',
]

# 마감일 추적 기록 (최초 발견/변경 감지 시 리포트에 알림 표기)
DEADLINE_LOG = root_config.CHECKPOINT_DIR / "global500_deadline.jsonl"
