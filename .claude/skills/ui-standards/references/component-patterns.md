# Component Patterns

batchIntelli에서 반복되는 14종 UI 패턴. 새 기능 구현 시 이 패턴을 따르세요.

> 참조 파일을 찾을 수 없으면 `src/components/` 하위에서 패턴명이나 키워드로 검색하세요.

## 1. KPI Card Grid

**용도**: 대시보드 상단 핵심 지표
**참조**: `src/components/operations/kpi-cards.tsx`

```tsx
const kpis = [
  { title: "총 지원", value: formatNumber(total), icon: Building2, desc: "..." },
  // ...
];

<div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
  {kpis.map((kpi) => (
    <Card key={kpi.title}>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          {kpi.title}
        </CardTitle>
        <kpi.icon className="h-4 w-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{kpi.value}</div>
        <p className="mt-1 text-xs text-muted-foreground">{kpi.desc}</p>
      </CardContent>
    </Card>
  ))}
</div>
```

## 2. Stats Card (Compact)

**용도**: 섹션 내 요약 통계 (CardHeader 없이)
**참조**: `src/components/overview/stat-card.tsx`

```tsx
<div className={cn("rounded-[10px] border bg-card p-6", className)}>
  <div className="flex items-center justify-between">
    <p className="text-sm font-medium text-muted-foreground">{title}</p>
    {Icon && <Icon className="h-4 w-4 text-muted-foreground" />}
  </div>
  <p className="mt-2 text-2xl font-bold">{value}</p>
  {description && <p className="mt-1 text-xs text-muted-foreground">{description}</p>}
</div>
```

## 3. Filter Bar

**용도**: 데이터 필터링 컨트롤
**참조**: `src/components/repeat-applicants/filter-bar.tsx`

```tsx
<div className="flex items-center gap-2 flex-wrap">
  <span className="text-xs text-muted-foreground">라벨:</span>
  {options.map((opt) => (
    <Button
      key={opt}
      variant={isActive(opt) ? "secondary" : "ghost"}
      size="sm"
      className="text-xs h-7"
      onClick={() => toggle(opt)}
    >
      {opt}
    </Button>
  ))}
  <div className="w-px h-4 bg-border mx-1" />  {/* 구분선 */}
  <span className="text-xs text-muted-foreground ml-auto">
    {filteredCount}건
  </span>
</div>
```

## 4. Page Header

**용도**: 모든 페이지 상단

```tsx
<div>
  <h1 className="text-xl md:text-2xl font-bold">페이지 제목</h1>
  <p className="text-sm text-muted-foreground mt-1">한 줄 설명</p>
</div>
```

액션 버튼이 있는 경우:
```tsx
<div className="flex items-center justify-between">
  <div>
    <h1 className="text-xl md:text-2xl font-bold">제목</h1>
    <p className="text-sm text-muted-foreground mt-1">설명</p>
  </div>
  <Button variant="outline" size="sm">액션</Button>
</div>
```

## 5. Page Guide

**용도**: 경영진용 접이식 설명
**참조**: `src/components/dashboard/page-guide.tsx`

```tsx
<PageGuide
  title="이 페이지에서 볼 수 있는 것"
  items={[
    "항목 1 설명",
    "항목 2 설명",
  ]}
/>
```

## 6. Chart Card

**용도**: 모든 Recharts 시각화
**참조**: `src/components/operations/charts/*.tsx`

```tsx
<Card>
  <CardHeader>
    <CardTitle className="text-base">차트 제목</CardTitle>
  </CardHeader>
  <CardContent>
    <div className="h-[300px]">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data}>...</BarChart>
      </ResponsiveContainer>
    </div>
  </CardContent>
</Card>
```

## 7. Table in Card

**용도**: 데이터 테이블
**참조**: `src/components/operations/weekly-table.tsx`

```tsx
<Card>
  <CardHeader>
    <CardTitle className="text-base">테이블 제목</CardTitle>
  </CardHeader>
  <CardContent>
    <div className="max-h-[400px] overflow-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>컬럼</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.map((row) => (
            <TableRow key={row.id}>
              <TableCell>{row.value}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  </CardContent>
</Card>
```

## 8. Detail Dialog

**용도**: 레코드 상세 보기
**참조**: `src/components/operations/shared/application-detail-dialog.tsx`

```tsx
<Dialog open={open} onOpenChange={onClose}>
  <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto">
    <DialogHeader>
      <DialogTitle>상세 정보</DialogTitle>
    </DialogHeader>
    {/* 상세 그리드 */}
    <div className="space-y-2">
      {fields.map(({ label, value }) => (
        <div key={label} className="grid grid-cols-[140px_1fr] gap-2 py-1.5 border-b border-border last:border-0">
          <div className="text-sm font-medium text-muted-foreground">{label}</div>
          <div className="text-sm">{value}</div>
        </div>
      ))}
    </div>
  </DialogContent>
</Dialog>
```

## 9. Badge Row

**용도**: 태그/상태 표시

```tsx
<div className="flex flex-wrap gap-1.5">
  <Badge variant="secondary" className="text-xs">{status}</Badge>
  <Badge variant="outline" className="text-xs">{tag}</Badge>
</div>
```

## 10. Tabs Navigation

**용도**: 멀티뷰 페이지
**참조**: `src/app/(dashboard)/repeat-applicants/page.tsx`

```tsx
<Tabs defaultValue="tab1" className="space-y-4">
  <TabsList>
    <TabsTrigger value="tab1" className="gap-1 text-xs">
      <Icon className="w-3.5 h-3.5" /> 탭 1
    </TabsTrigger>
    <TabsTrigger value="tab2" className="gap-1 text-xs">
      <Icon className="w-3.5 h-3.5" /> 탭 2
    </TabsTrigger>
  </TabsList>
  <TabsContent value="tab1">...</TabsContent>
  <TabsContent value="tab2">...</TabsContent>
</Tabs>
```

## 11. Loading Skeletons

**용도**: 비동기 콘텐츠 로딩 상태 (필수)
**참조**: `src/components/operations/shared/dashboard-skeleton.tsx`

```tsx
// KPI 스켈레톤
<div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
  {Array.from({ length: 5 }).map((_, i) => (
    <Card key={i}>
      <CardHeader className="pb-2"><Skeleton className="h-4 w-24" /></CardHeader>
      <CardContent><Skeleton className="h-8 w-16" /></CardContent>
    </Card>
  ))}
</div>

// 차트 스켈레톤
<Card>
  <CardHeader><Skeleton className="h-5 w-32" /></CardHeader>
  <CardContent><Skeleton className="h-[300px] w-full" /></CardContent>
</Card>
```

## 12. Responsive Grid

**용도**: 멀티 컬럼 레이아웃

```tsx
{/* KPI: 5열 */}
<div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">

{/* 차트: 2열 */}
<div className="grid grid-cols-1 gap-4 lg:grid-cols-2">

{/* 통계: 3열 */}
<div className="grid grid-cols-1 gap-4 md:grid-cols-3">
```

## 13. Sidebar Navigation

**용도**: 이미 구축됨 — 재구현 금지
**참조**: `src/components/dashboard/sidebar.tsx`

새 메뉴 추가 시 `navGroups` 배열에 항목 추가:
```tsx
{ href: "/new-page", label: "새 페이지", icon: SomeIcon }
```

## 14. Lazy Chart Loading

**용도**: 모든 차트 컴포넌트 (필수)
**참조**: `src/components/operations/charts/lazy-charts.tsx`

```tsx
// lazy-charts.tsx에 등록
export const LazyNewChart = dynamic(
  () => import('./new-chart').then(m => ({ default: m.NewChart })),
  { ssr: false, loading: () => <ChartSkeleton /> }
);

// 페이지에서 사용
import { LazyNewChart } from '@/components/operations/charts/lazy-charts';
<LazyNewChart data={data} />
```
