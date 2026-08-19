#!/bin/sh
# US FORGED 골든셋 래칫 — baseline 보다 나빠지면 커밋 차단(§5).
# 설치: ln -sf ../../scripts/pre-commit-golden.sh .git/hooks/pre-commit
cd "$(git rev-parse --show-toplevel)" || exit 1
python -m tests.golden_ratchet || {
  echo "커밋 차단됨. 회귀를 고치거나, 의도된 개선이면: python -m tests.golden_ratchet --update-baseline"
  exit 1
}
