---
name: ui-standards
description: batchIntelli UI 디자인 시스템. 프론트엔드 코드 작성 시 자동 적용 — 색상, 폰트, 레이아웃, 컴포넌트 패턴, 차트 규칙.
user-invocable: true
---

# batchIntelli UI Design System

## Purpose & Philosophy

경영진용 내부 분석 대시보드. 디자인 원칙:

- **데이터 밀도 > 장식** — 모든 픽셀이 데이터 목적을 가져야 한다
- **Remove decoration test** — 시각 요소를 제거해도 데이터 이해에 영향이 없으면 제거
- **무채색 중립 베이스** — 색상은 데이터 의미 전달에만 사용 (기수 구분, 산업 분류 등)
- **한국어 우선** — Pretendard Variable 본문, 숫자는 억원/조원 단위 포맷
- **일관된 밀도** — 같은 유형의 정보는 같은 패턴으로 표현

## Hard Constraints — DO NOT

- Pretendard Variable / Geist Mono 외 폰트 사용 금지
- lucide-react 외 아이콘 라이브러리 금지
- UI chrome에 raw hex 금지 — 반드시 CSS 변수 (`var(--color-*)`, `bg-primary` 등)
- className에 반드시 `cn()` from `@/lib/utils` 사용
- 커스텀 CSS 클래스 금지 — Tailwind 유틸리티만
- shadcn style은 `base-nova` (~~new-york 아님~~)
- 차트 색상 하드코딩 금지 — `BATCH_COLORS` / `INDUSTRY_COLORS` / `LOCATION_COLORS` from `@/lib/operations/format`
- 차트 컴포넌트 직접 import 금지 — `lazy-charts.tsx`의 `Lazy*` 버전만 사용
- `React.FC` 사용 금지 — named function + Props interface
- `console.log` 프로덕션 코드 금지

## Required Patterns — DO

- shadcn/ui 컴포넌트 사용 (Card, Badge, Button, Dialog, Sheet, Tabs, Table)
- 차트: `Card > CardHeader(title) > CardContent > div(h-[300px]) > ResponsiveContainer`
- KPI 그리드: 데이터 배열 `.map()` — 하드코딩된 반복 JSX 금지
- 모든 비동기 콘텐츠에 스켈레톤 로딩 상태 필수
- 페이지 수직 리듬: `space-y-6` (섹션 간 24px)
- 반응형 그리드: `grid-cols-1 sm:grid-cols-2 lg:grid-cols-N gap-4`
- 숫자 포맷: `formatNumber` / `formatPercent` / `formatValuation` from `@/lib/operations/format`
- 날짜 비교: `todayKst()` from `@/lib/utils/kst-date` (UTC 금지)
- 파일 첫 2줄: `// ABOUTME:` 접두사로 파일 설명
- 새 차트 생성 시 `lazy-charts.tsx`에 `Lazy*` export 등록 필수

## Decision Framework

### 새 페이지 구성 순서

1. **페이지 헤더**: `h1` (text-xl md:text-2xl font-bold) + `p` (text-sm text-muted-foreground mt-1)
2. **PageGuide**: 경영진 설명용 접이식 가이드 (선택)
3. **BatchSelector**: 기수/계열 선택 (해당 시)
4. **KPI 카드 그리드**: `grid-cols-2 lg:grid-cols-5`
5. **콘텐츠 영역**: 차트/테이블 `grid-cols-1 lg:grid-cols-2`

### Button variant 선택

| 상황 | variant |
|------|---------|
| 필터 활성 상태 | `secondary` |
| 필터 비활성 상태 | `ghost` |
| 주요 액션 | `default` |
| 보조 액션 | `outline` |
| 위험 액션 | `destructive` |

### Badge variant 선택

| 상황 | variant |
|------|---------|
| 현재/강조 항목 | `default` |
| 일반 상태 표시 | `secondary` |
| 태그/분류 | `outline` |

### Card padding 선택

| 상황 | CardHeader |
|------|-----------|
| KPI 카드 | `pb-2` (빽빽하게) |
| 콘텐츠 카드 | 기본 `p-6` |
| 컴팩트 카드 | `CardContent pt-4 pb-3 px-4` (CardHeader 없이) |

## File Organization

```
src/app/(dashboard)/[feature]/page.tsx    — 페이지 (서버 or 클라이언트)
src/components/[feature]/*.tsx            — 피처별 컴포넌트
src/components/operations/shared/*.tsx    — 운영 현황 공유 컴포넌트
src/components/operations/charts/*.tsx    — 차트 컴포넌트
src/components/operations/charts/lazy-charts.tsx — Lazy 차트 레지스트리
src/components/dashboard/*.tsx            — 사이드바, 헤더, PageGuide 등
src/components/ui/*.tsx                   — shadcn 관리 (수동 편집 금지)
src/lib/operations/format.ts             — 포맷팅 + 차트 색상/스타일
```

## References

- 디자인 토큰 (색상, 폰트, 간격, 반경): `references/design-system.md`
- 14종 반복 UI 패턴 + 코드 예제: `references/component-patterns.md`
- Recharts 차트 규칙 + 색상 팔레트: `references/chart-standards.md`
- 앱 초기 셋업 (인증, 레이아웃, 다크모드): `references/app-scaffold.md`
