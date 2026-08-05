// ABOUTME: 차트 로딩 스켈레톤 — Lazy 차트의 loading 상태 (필수 패턴 11)
// ABOUTME: Card + h-[300px] Skeleton 구조로 실제 차트 카드와 동일한 자리 차지
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export function ChartSkeleton() {
  return (
    <Card>
      <CardHeader>
        <Skeleton className="h-5 w-32" />
      </CardHeader>
      <CardContent>
        <Skeleton className="h-[300px] w-full" />
      </CardContent>
    </Card>
  );
}
