"""② AC 업체 동향 모니터 전용 설정 (실행: monitor_ac.py).

경로·모델 등 공용 값은 루트 config.py 를 따른다.
"""
import config as root_config

REPORT_SUBDIR = "ac_watch"    # 리포트 폴더명 (output/ac_watch/)

# 비교 시트의 액셀러레이터/컨설팅 업체. pages 의 URL을 직접 보강/수정해서 쓴다.
# (Long Story Short 는 공식 도메인 미확인 — pages 를 채워 넣으면 페이지 감시 활성화,
#  비워 두면 뉴스 검색만 수행)
# data/ac_targets.json 이 있으면 이 기본값 대신 그 파일을 사용한다 (같은 구조의 배열,
# 샘플: data/ac_targets.sample.json).
TARGETS = [
    {
        "name": "Long Story Short",
        "slug": "long-story-short",
        "pages": {},  # 예: {"home": "https://...", "services": "https://.../services"}
        "news_queries": ['"롱스토리숏" 스타트업', '"Long Story Short" 액셀러레이터 한국'],
        "watch_hints": "前 500 Global APAC 총괄 스카우트 예정 언급 있음 — 인력 영입 소식 중점 확인",
    },
    {
        "name": "업라이트컨설팅 (Upright)",
        "slug": "upright",
        "pages": {
            "home": "http://upright.co.kr/",
        },
        "news_queries": ['"업라이트컨설팅"', '"업라이트" IR 컨설팅 스타트업'],
        "watch_hints": "IR 컨설팅 서비스 구성·가격 변경 여부",
    },
    {
        "name": "Intralink",
        "slug": "intralink",
        "pages": {
            "home": "https://www.intralinkgroup.com/ko-kr/",
            "services": "https://www.intralinkgroup.com/ko-kr/corporate-services",
            "news": "https://www.intralinkgroup.com/ko-kr/latest",
        },
        "news_queries": ['"인트라링크" 스타트업 해외진출', '"Intralink" Korea startup'],
        "watch_hints": "해외진출 BD 서비스 범위·가격, 한국 오피스 인력 변동",
    },
]
TARGETS_JSON = root_config.DATA_DIR / "ac_targets.json"
