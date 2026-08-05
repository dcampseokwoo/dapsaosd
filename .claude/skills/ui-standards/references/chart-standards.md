# Chart Standards

Recharts 기반 차트 규칙. 모든 차트는 이 표준을 따릅니다.

> 색상/스타일 상수: `src/lib/operations/format.ts`

## Shared Styles

모든 차트에서 import하여 사용:

```tsx
import {
  TOOLTIP_STYLE,
  AXIS_TICK_STYLE,
  GRID_STYLE,
  BATCH_COLORS,
  INDUSTRY_COLORS,
  LOCATION_COLORS,
} from '@/lib/operations/format';
```

### TOOLTIP_STYLE

```ts
{
  backgroundColor: 'var(--color-popover, #fff)',
  border: '1px solid var(--color-border, #e5e7eb)',
  borderRadius: '8px',
  boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)',
  color: 'var(--color-popover-foreground, #1f2937)',
  fontSize: '13px',
  padding: '8px 12px',
}
```

### AXIS_TICK_STYLE

```ts
{ fill: 'var(--color-muted-foreground, #6b7280)', fontSize: 12 }
```

### GRID_STYLE

```ts
{ stroke: 'var(--color-border, #e5e7eb)' }
```

## Color Palettes

### BATCH_COLORS (기수별)

```ts
{
  1: '#94a3b8',  // slate-400
  2: '#a1a1aa',  // zinc-400
  3: '#a3a3a3',  // neutral-400
  4: '#78716c',  // stone-500
  5: '#6366f1',  // indigo-500
  6: '#8b5cf6',  // violet-500
  7: '#f97316',  // orange-500 (현재 기수 강조)
}
```

규칙: **현재/최신 기수는 항상 orange (#f97316)**로 강조.

### INDUSTRY_COLORS (산업분야, 21색 순환)

```ts
[
  '#6366f1', '#8b5cf6', '#a78bfa', '#c084fc',  // 보라 계열
  '#f97316', '#fb923c', '#fdba74',              // 주황 계열
  '#10b981', '#34d399', '#6ee7b7',              // 초록 계열
  '#3b82f6', '#60a5fa', '#93c5fd',              // 파랑 계열
  '#ef4444', '#f87171',                         // 빨강 계열
  '#eab308', '#facc15',                         // 노랑 계열
  '#ec4899', '#f472b6',                         // 핑크 계열
  '#14b8a6', '#2dd4bf',                         // 청록 계열
]
```

### LOCATION_COLORS (지역, 17색)

```ts
[
  '#3b82f6', '#6366f1', '#8b5cf6', '#a78bfa',
  '#10b981', '#14b8a6', '#06b6d4',
  '#f97316', '#eab308', '#ef4444',
  '#ec4899', '#78716c', '#94a3b8',
  '#64748b', '#6b7280', '#71717a', '#737373',
]
```

## Chart Component Structure

모든 차트 파일은 이 구조를 따릅니다:

```tsx
// ABOUTME: 차트 설명 한 줄
// ABOUTME: 상세 설명 한 줄

'use client';

import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { TOOLTIP_STYLE, AXIS_TICK_STYLE, GRID_STYLE } from '@/lib/operations/format';

interface ChartNameProps {
  data: SomeType;
}

export function ChartName({ data }: ChartNameProps) {
  // 데이터 가공
  const chartData = /* ... */;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">차트 제목</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="h-[300px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" {...GRID_STYLE} />
              <XAxis dataKey="name" tick={AXIS_TICK_STYLE} />
              <YAxis tick={AXIS_TICK_STYLE} />
              <Tooltip contentStyle={TOOLTIP_STYLE} />
              <Bar dataKey="value" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}
```

## Chart Types & Patterns

### Vertical Bar Chart (수직 막대)

- 높이: `h-[300px]` 고정
- Bar radius: `[4, 4, 0, 0]` (상단 모서리만 둥글게)
- 참조: `valuation-chart.tsx`

### Horizontal Bar Chart (수평 막대)

- 높이: **동적** — `Math.max(350, data.length * 32)`
- layout: `"vertical"` on BarChart
- Bar radius: `[0, 4, 4, 0]` (오른쪽 모서리만 둥글게)
- margin: `{ left: 100 }` (Y축 라벨 공간)
- 참조: `industry-chart.tsx`

### Line Chart (라인)

- 높이: `h-[350px]`
- 현재 기수: `strokeWidth={4}`, 불투명, orange
- 이전 기수: `strokeWidth={2.5}`, `opacity={0.7}`
- 과거 기수: `strokeWidth={1.2}`, `opacity={0.35}`
- `dot={false}`, `connectNulls={false}`
- 참조: `cumulative-chart.tsx`

### Scatter Chart (산점도)

- 참조: `valuation-scatter-chart.tsx`

## Tooltip Formatting

항상 수치 + 단위/퍼센트 포함:

```tsx
<Tooltip
  contentStyle={TOOLTIP_STYLE}
  formatter={(value: number) => [`${formatNumber(value)}건`, '지원수']}
/>
```

복합 포맷: `${value}건 (${pct}%)`

## Lazy Loading (필수)

모든 차트는 `lazy-charts.tsx`에 등록 후 사용:

```tsx
// 1. 차트 컴포넌트 생성: charts/my-chart.tsx
export function MyChart({ data }: MyChartProps) { ... }

// 2. lazy-charts.tsx에 등록
export const LazyMyChart = dynamic(
  () => import('./my-chart').then(m => ({ default: m.MyChart })),
  { ssr: false, loading: () => <ChartSkeleton /> }
);

// 3. 페이지에서 Lazy 버전만 import
import { LazyMyChart } from '@/components/operations/charts/lazy-charts';
```

직접 import 금지: ~~`import { MyChart } from './charts/my-chart'`~~

## ReferenceLine

목표선/이벤트 표시:

```tsx
// 타겟 구간
<ReferenceLine y={targetValue} stroke="#f97316" strokeDasharray="3 3" label="타겟" />

// 이벤트 마커
<ReferenceLine x={eventDate} stroke="#ef4444" strokeDasharray="4 2" label="이벤트" />
```

- 타겟: orange (#f97316), `strokeDasharray="3 3"`
- 이벤트: red (#ef4444), `strokeDasharray="4 2"`
