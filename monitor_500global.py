"""① 500 Global 프로그램 모니터 — 실행 파일.

500.co 공식 사이트에서 지원 요건·다음 배치 마감일(D-day/변경 알림)·배치 일정·
최근 선발 포트폴리오를 수집하고, 선발 기업 공통점을 분석해 리포트로 저장한다.

사용 예:
  python monitor_500global.py                          # 기본 실행
  python monitor_500global.py --no-ai                  # Gemini 없이 수집/스냅샷/뉴스만 (키 불필요)
  python monitor_500global.py --search-mode grounding  # 유료 티어: Gemini 검색 직접 사용 (권장)
  python monitor_500global.py --max-calls 10           # Gemini 호출 한도

출력:
  output/global500/global500_report_{날짜}.md   # 리포트 (마크다운)
  output/global500/global500_status_{날짜}.json # 원본 데이터
  checkpoints/global500_deadline.jsonl          # 마감일 추적 이력
  checkpoints/snapshots/global500/              # 페이지 스냅샷 (변경 감지용)

설정: monitors/global500/config.py (크롤링 페이지·뉴스 쿼리)
"""
import argparse
import logging
import sys

import config


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="500 Global 프로그램 모니터")
    p.add_argument("--no-ai", action="store_true",
                   help="Gemini 호출 없이 수집·스냅샷 비교·뉴스만 수행 (API 키 불필요)")
    p.add_argument("--max-calls", type=int, help="Gemini API 호출 한도")
    p.add_argument("--search-mode", choices=["rss", "grounding"],
                   help="rss=페이지+뉴스 텍스트를 Gemini에 제공(기본) / grounding=Gemini 검색(유료 티어)")
    p.add_argument("-v", "--verbose", action="store_true")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.search_mode:
        config.SEARCH_MODE = args.search_mode
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S",
    )

    from monitors import common
    from monitors.global500 import crawler

    client, use_ai = common.make_gemini_client(args.max_calls, args.no_ai)
    path = crawler.run(client, use_ai)

    logging.info("리포트: %s", path)
    if client is not None:
        logging.info("Gemini 호출 수: %d", client.call_count)
    return 0


if __name__ == "__main__":
    sys.exit(main())
