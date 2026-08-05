// ABOUTME: 검증 신뢰도(high/medium/low) 분포 수직 막대 차트
// ABOUTME: 높이 h-[300px], Bar radius [4,4,0,0] (수직 바 표준)
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
  INDUSTRY_COLORS,
  TOOLTIP_STYLE,
  formatNumber,
} from "@/lib/operations/format";

interface ConfidenceChartProps {
  data: { confidence: string; count: number }[];
}

// high=초록, medium=노랑, low=빨강 계열 — INDUSTRY_COLORS 팔레트 사용
const CONFIDENCE_COLOR: Record<string, string> = {
  high: INDUSTRY_COLORS[7],
  medium: INDUSTRY_COLORS[15],
  low: INDUSTRY_COLORS[13],
};

export function ConfidenceChart({ data }: ConfidenceChartProps) {
  const total = data.reduce((sum, d) => sum + d.count, 0);
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">검증 신뢰도 분포</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="h-[300px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data}>
              <CartesianGrid strokeDasharray="3 3" {...GRID_STYLE} />
              <XAxis dataKey="confidence" tick={AXIS_TICK_STYLE} />
              <YAxis tick={AXIS_TICK_STYLE} allowDecimals={false} />
              <Tooltip
                contentStyle={TOOLTIP_STYLE}
                formatter={(value: number) => [
                  `${formatNumber(value)}건 (${((value / total) * 100).toFixed(1)}%)`,
                  "건수",
                ]}
              />
              <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                {data.map((entry) => (
                  <Cell
                    key={entry.confidence}
                    fill={CONFIDENCE_COLOR[entry.confidence] ?? INDUSTRY_COLORS[0]}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}
