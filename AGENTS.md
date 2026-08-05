# AGENTS.md — 에이전트 공통 작업 지침

이 저장소는 Claude Code와 Codex 등 여러 코딩 에이전트가 병렬로 작업한다.
어떤 에이전트든 아래 지침을 동일하게 따른다.

## 프론트엔드 작업 (dashboard/) — 디자인 시스템 필수

`dashboard/` 하위의 모든 프론트엔드 코드는 dcamp 디자인 시스템을 따라야 한다.
지침 원본은 이 저장소에 포함되어 있다 — **코드를 작성하기 전에 반드시 읽을 것**:

- `.claude/skills/ui-standards/SKILL.md` — 핵심 규칙 (Hard Constraints / Required Patterns / 결정 프레임워크)
- `.claude/skills/ui-standards/references/design-system.md` — 디자인 토큰 (OKLCH 색상, 폰트, 간격, 반경)
- `.claude/skills/ui-standards/references/component-patterns.md` — 14종 반복 UI 패턴 + 코드 예제
- `.claude/skills/ui-standards/references/chart-standards.md` — Recharts 차트 규칙 + 색상 팔레트
- `.claude/skills/ui-standards/references/app-scaffold.md` — 앱 기반 구조 (레이아웃, 다크모드, 인증)

요약(상세는 위 파일이 우선):
Pretendard Variable/Geist Mono 외 폰트 금지 · lucide-react 외 아이콘 금지 ·
UI에 raw hex 금지(CSS 변수만) · className은 `cn()` 필수 · Tailwind 유틸리티만 ·
차트 색상은 `@/lib/operations/format`의 팔레트만 · 차트는 `lazy-charts.tsx`의
Lazy* 버전만 import · `React.FC` 금지 · 프로덕션 `console.log` 금지 ·
모든 파일 첫 2줄은 `// ABOUTME:` 설명.

## 빌드·검증

- 대시보드: `cd dashboard && npm install && npm run build` (푸시 전 빌드 성공 필수)
- Python 파이프라인: `python test_pipeline_offline.py`, `python test_500global_offline.py`,
  `python test_ac_watch_offline.py` (API 키·네트워크 불필요)

## 브랜치 규칙

- 작업 단위마다 별도 브랜치를 사용한다. 다른 에이전트의 브랜치에 커밋하지 않는다.
- 취합(머지·충돌 해결)은 조율 담당 세션에서 수행한다.
