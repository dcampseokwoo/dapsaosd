// ABOUTME: 투자 스테이지 페이지 KPI 카드 그리드 — 총 조사·반영·변경 없음·확인 필요·종결(IPO/M&A)
// ABOUTME: 데이터 배열 .map() 렌더 (하드코딩 반복 JSX 금지 규칙)
import {
  ArrowUpRight,
  Building2,
  CircleAlert,
  CircleCheck,
  Landmark,
  type LucideIcon,
} from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatNumber, formatPercent } from "@/lib/operations/format";

interface StageKpiCardsProps {
  total: number;
  applied: number;
  unchanged: number;
  needsReview: number;
  exited: number;
}

export function StageKpiCards({
  total,
  applied,
  unchanged,
  needsReview,
  exited,
}: StageKpiCardsProps) {
  const pct = (n: number) => (total ? formatPercent((n / total) * 100) : "-");
  const kpis: { title: string; value: string; icon: LucideIcon; desc: string }[] = [
    {
      title: "총 조사 기업",
      value: formatNumber(total),
      icon: Building2,
      desc: "1차 조사 완료 기준",
    },
    {
      title: "스테이지 반영",
      value: formatNumber(applied),
      icon: ArrowUpRight,
      desc: `전체의 ${pct(applied)} — G열 교체 완료`,
    },
    {
      title: "변경 없음",
      value: formatNumber(unchanged),
      icon: CircleCheck,
      desc: `전체의 ${pct(unchanged)} — 기존 기재 유지`,
    },
    {
      title: "확인 필요",
      value: formatNumber(needsReview),
      icon: CircleAlert,
      desc: `전체의 ${pct(needsReview)} — 근거 부족·재검증 대상`,
    },
    {
      title: "IPO·M&A 종결",
      value: formatNumber(exited),
      icon: Landmark,
      desc: "연도 확정 종결 상태",
    },
  ];

  return (
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
  );
}
