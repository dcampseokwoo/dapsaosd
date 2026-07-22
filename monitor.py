"""모니터링 CLI — 500 Global 프로그램 추적 + AC 업체 동향 감시.

사용 예:
  python monitor.py 500                       # 500 Global 요강/마감일/포트폴리오 리포트
  python monitor.py ac                        # AC 업체(LSS·Upright·Intralink 등) 전체
  python monitor.py ac --target intralink     # 특정 업체만
  python monitor.py all                       # 둘 다
  python monitor.py 500 --no-ai               # Gemini 없이 수집/스냅샷/뉴스만 (키 불필요)
  python monitor.py 500 --search-mode grounding  # 유료 티어: Gemini 검색 직접 사용

리포트는 output/ 에 마크다운+JSON으로 저장되고,
페이지 스냅샷은 checkpoints/snapshots/ 에 남아 다음 실행 때 변경 감지에 쓰인다.
"""
import argparse
import logging
import sys

import config


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="500 Global / AC 업체 모니터링")
    p.add_argument("what", choices=["500", "ac", "all"],
                   help="500=500 Global 프로그램, ac=AC 업체 동향, all=둘 다")
    p.add_argument("--target", type=str, help="ac: 특정 업체 slug만 (예: intralink)")
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

    client, use_ai = None, not args.no_ai
    if use_ai:
        try:
            from ai.gemini import GeminiClient
            client = GeminiClient(max_calls=args.max_calls)
        except RuntimeError as e:
            logging.warning("%s — AI 분석 없이 수집만 진행합니다 (--no-ai 와 동일).", e)
            use_ai = False

    from monitors import ac_watch, global500

    paths = []
    if args.what in ("500", "all"):
        paths.append(global500.run(client, use_ai))
    if args.what in ("ac", "all"):
        paths.append(ac_watch.run(client, use_ai, only_slug=args.target))

    for path in paths:
        logging.info("리포트: %s", path)
    if client is not None:
        logging.info("Gemini 호출 수: %d", client.call_count)
    return 0


if __name__ == "__main__":
    sys.exit(main())
