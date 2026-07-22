"""② AC 업체 동향 모니터 — 실행 파일.

비교 시트의 액셀러레이터/컨설팅 업체(Long Story Short, Upright, Intralink 등)
웹사이트를 크롤링해 서비스/가격 변경(스냅샷 diff)과 멘토/인력 영입 소식(뉴스)을
감지하고 리포트로 저장한다.

사용 예:
  python monitor_ac.py                       # 전체 업체
  python monitor_ac.py --target intralink    # 특정 업체만 (slug)
  python monitor_ac.py --no-ai               # Gemini 없이 수집/스냅샷/뉴스만 (키 불필요)
  python monitor_ac.py --max-calls 10        # Gemini 호출 한도

출력:
  output/ac_watch/ac_watch_report_{날짜}.md   # 리포트 (마크다운)
  output/ac_watch/ac_watch_status_{날짜}.json # 원본 데이터
  checkpoints/snapshots/{업체slug}/           # 페이지 스냅샷 (변경 감지용)

대상 설정: monitors/ac_watch/config.py 의 TARGETS 기본값.
data/ac_targets.json 이 있으면 그 파일이 우선한다
(샘플: data/ac_targets.sample.json 복사 후 URL 채우기).
"""
import argparse
import logging
import sys


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="AC 업체(LSS·Upright·Intralink 등) 동향 모니터")
    p.add_argument("--target", type=str, help="특정 업체 slug만 (예: intralink)")
    p.add_argument("--no-ai", action="store_true",
                   help="Gemini 호출 없이 수집·스냅샷 비교·뉴스만 수행 (API 키 불필요)")
    p.add_argument("--max-calls", type=int, help="Gemini API 호출 한도")
    p.add_argument("-v", "--verbose", action="store_true")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S",
    )

    from monitors import common
    from monitors.ac_watch import watcher

    client, use_ai = common.make_gemini_client(args.max_calls, args.no_ai)
    path = watcher.run(client, use_ai, only_slug=args.target)

    logging.info("리포트: %s", path)
    if client is not None:
        logging.info("Gemini 호출 수: %d", client.call_count)
    return 0


if __name__ == "__main__":
    sys.exit(main())
