// ABOUTME: Lazy 차트 레지스트리 — 모든 차트는 여기 등록된 Lazy* 버전으로만 import (필수 규칙)
// ABOUTME: dynamic(ssr:false) + ChartSkeleton 로딩 상태
"use client";

import dynamic from "next/dynamic";

import { ChartSkeleton } from "./chart-skeleton";

export const LazyStageDistributionChart = dynamic(
  () =>
    import("./stage-distribution-chart").then((m) => ({
      default: m.StageDistributionChart,
    })),
  { ssr: false, loading: () => <ChartSkeleton /> }
);

export const LazyUpdateResultChart = dynamic(
  () =>
    import("./update-result-chart").then((m) => ({
      default: m.UpdateResultChart,
    })),
  { ssr: false, loading: () => <ChartSkeleton /> }
);

export const LazyConfidenceChart = dynamic(
  () =>
    import("./confidence-chart").then((m) => ({
      default: m.ConfidenceChart,
    })),
  { ssr: false, loading: () => <ChartSkeleton /> }
);
