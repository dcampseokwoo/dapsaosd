"""CLI 진입점.

사용 예:
  python main.py --priority 1                # Type 1 그룹만 조사 + 엑셀 반영
  python main.py --priority 1 --limit 50     # 50개만
  python main.py --dry-run --limit 20        # 엑셀 반영 없이 조사만
  python main.py --max-calls 200             # API 호출 200회 도달 시 저장 후 종료
  python main.py --test                      # 소량(5개사) 드라이런 테스트
  python main.py --apply-only                # 체크포인트 결과만 엑셀에 반영 (API 호출 없음)
"""
import argparse
import logging
import sys

import config


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="스타트업 투자 스테이지 자동 조사 파이프라인")
    p.add_argument("--priority", type=int, choices=[1, 2, 3, 4, 5],
                   help="우선순위 그룹만 실행 (1=Type 1, 2=디데이, 3=Type 2, 4=공란/기타, 5=Type 3)")
    p.add_argument("--limit", type=int, help="처리 기업 수 제한")
    p.add_argument("--dry-run", action="store_true", help="엑셀 반영 없이 조사만")
    p.add_argument("--max-calls", type=int, help="API 호출 한도 (도달 시 저장 후 정상 종료)")
    p.add_argument("--batch-size", type=int,
                   help=f"1단계 스크리닝 배치 크기 (기본 {config.SCREEN_BATCH_SIZE}, 1=배치 끔)")
    p.add_argument("--test", action="store_true", help="소량(5개사) 드라이런 테스트")
    p.add_argument("--apply-only", action="store_true",
                   help="API 호출 없이 checkpoints/results.jsonl 을 엑셀에 반영")
    p.add_argument("--report", action="store_true",
                   help="체크포인트에서 반영/확인필요 검수 CSV 생성")
    p.add_argument("--verify-models", type=str,
                   help="2단계 검증 모델 목록(쉼표 구분, 빈 값이면 제한 없음)")
    p.add_argument("--redo-changed", action="store_true",
                   help="체크포인트에서 changed/ambiguous(2단계 검증분) 기록을 지워 재조사 대상으로 되돌림")
    p.add_argument("--search-mode", choices=["rss", "grounding"],
                   help="rss=구글 뉴스 RSS(무료, 기본) / grounding=Gemini 검색(유료 티어)")
    p.add_argument("--excel", type=str, help=f"엑셀 경로 (기본: {config.EXCEL_PATH})")
    p.add_argument("-v", "--verbose", action="store_true")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.search_mode:
        config.SEARCH_MODE = args.search_mode
    if args.verify_models is not None:
        config.VERIFY_MODELS = [m.strip() for m in args.verify_models.split(",") if m.strip()]
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S",
    )

    from pathlib import Path
    excel_path = Path(args.excel) if args.excel else config.EXCEL_PATH
    if not excel_path.exists() and not (args.apply_only or args.report):
        logging.error("엑셀 파일이 없습니다: %s — data/ 에 Startup_DB.xlsx 를 두세요.", excel_path)
        return 1

    import pipeline
    from updater import excel_updater

    if args.report:
        applied_path, applied_count, review_path, review_count = pipeline.export_review_reports()
        logging.info("검수 리포트 생성: %s (%d건), %s (%d건)",
                     applied_path, applied_count, review_path, review_count)
        return 0

    if args.redo_changed:
        done = pipeline.load_checkpoint()
        if not done:
            logging.error("체크포인트가 비어 있습니다.")
            return 1
        keep = [r for r in done.values()
                if r["verdict"] not in ("changed", "ambiguous") and not r.get("applied")]
        removed = len(done) - len(keep)
        import datetime as _dt
        backup = config.CHECKPOINT_PATH.with_name(
            f"results_{_dt.datetime.now().strftime('%y%m%d_%H%M%S')}.jsonl.bak")
        config.CHECKPOINT_PATH.rename(backup)
        import json as _json
        with open(config.CHECKPOINT_PATH, "w", encoding="utf-8") as f:
            for r in keep:
                f.write(_json.dumps(r, ensure_ascii=False) + "\n")
        logging.info("재조사 대상으로 되돌림: %d건 (유지 %d건, 백업: %s)",
                     removed, len(keep), backup.name)
        return 0

    if args.apply_only:
        results = list(pipeline.load_checkpoint().values())
        if not results:
            logging.error("체크포인트가 비어 있습니다: %s", config.CHECKPOINT_PATH)
            return 1
        before_apply = {r["row"]: (r.get("excel_applied"), r.get("apply_error"),
                                    r.get("excel_row"))
                        for r in results}
        excel_updater.apply_results(results, "체크포인트 일괄 반영", excel_path)
        for rec in results:
            outcome = (rec.get("excel_applied"), rec.get("apply_error"),
                       rec.get("excel_row"))
            if outcome != before_apply.get(rec["row"]):
                pipeline.append_checkpoint(rec)
        return 0

    if args.test:
        logging.info("=== 소량 테스트: 5개사, dry-run ===")
        pipeline.run(priority=args.priority, limit=5, dry_run=True,
                     max_calls=args.max_calls or 20, excel_path=excel_path)
        return 0

    pipeline.run(priority=args.priority, limit=args.limit, dry_run=args.dry_run,
                 max_calls=args.max_calls, batch_size=args.batch_size,
                 excel_path=excel_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
