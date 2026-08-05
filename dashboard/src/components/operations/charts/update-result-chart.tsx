// ABOUTME: 조사 결과(반영 여부) 분포 수직 막대 차트 — 반영/변경 없음/확인 필요
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

interface UpdateResultChartProps {
  data: { group: string; count: number }[];
}

// 그룹별 색상 — INDUSTRY_COLORS 팔레트에서 의미 매핑 (초록=반영, 파랑=유지, 주황=확인, 회색톤=정보없음)
const GROUP_COLOR: Record<string, string> = {
  반영: INDUSTRY_COLORS[7],
  "변경 없음": INDUSTRY_COLORS[10],
  "확인 필요": INDUSTRY_COLORS[4],
  "정보 없음": INDUSTRY_COLORS[13],
};

export function UpdateResultChart({ data }: UpdateResultChartProps) {
  const total = data.reduce((sum, d) => sum + d.count, 0);
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">조사 결과 분포</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="h-[300px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data}>
              <CartesianGrid strokeDasharray="3 3" {...GRID_STYLE} />
              <XAxis dataKey="group" tick={AXIS_TICK_STYLE} />
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
                    key={entry.group}
                    fill={GROUP_COLOR[entry.group] ?? INDUSTRY_COLORS[0]}
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
