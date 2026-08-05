// ABOUTME: 최신 투자 스테이지 분포 수평 막대 차트 — 스테이지별 기업 수
// ABOUTME: 높이 동적(Math.max(350, n*32)), Bar radius [0,4,4,0], margin left 100 (수평 바 표준)
"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  AXIS_TICK_STYLE,
  GRID_STYLE,
  TOOLTIP_STYLE,
  formatNumber,
  stageColor,
} from "@/lib/operations/format";

interface StageDistributionChartProps {
  data: { stage: string; count: number }[];
}

export function StageDistributionChart({ data }: StageDistributionChartProps) {
  const height = Math.max(350, data.length * 32);
  const total = data.reduce((sum, d) => sum + d.count, 0);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">최신 투자 스테이지 분포</CardTitle>
      </CardHeader>
      <CardContent>
        <div style={{ height }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} layout="vertical" margin={{ left: 100 }}>
              <CartesianGrid strokeDasharray="3 3" {...GRID_STYLE} />
              <XAxis type="number" tick={AXIS_TICK_STYLE} allowDecimals={false} />
              <YAxis
                type="category"
                dataKey="stage"
                tick={AXIS_TICK_STYLE}
                width={100}
              />
              <Tooltip
                contentStyle={TOOLTIP_STYLE}
                formatter={(value: number) => [
                  `${formatNumber(value)}개사 (${((value / total) * 100).toFixed(1)}%)`,
                  "기업 수",
                ]}
              />
              <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                {data.map((entry) => (
                  <Cell key={entry.stage} fill={stageColor(entry.stage)} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}
