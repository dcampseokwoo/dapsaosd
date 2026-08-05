// ABOUTME: 숫자/금액 포맷 유틸 + 차트 공유 스타일·색상 팔레트 (디자인 시스템 source of truth)
// ABOUTME: 모든 차트는 여기의 TOOLTIP_STYLE / AXIS_TICK_STYLE / GRID_STYLE / *_COLORS만 사용한다
export function formatNumber(value: number): string {
  return new Intl.NumberFormat("ko-KR").format(value);
}

export function formatPercent(value: number, digits = 1): string {
  return `${value.toFixed(digits)}%`;
}

/** 억원 단위 금액 포맷 — 1조 이상은 조원 단위로 변환 */
export function formatValuation(eok: number): string {
  if (Math.abs(eok) >= 10000) {
    const jo = eok / 10000;
    return `${Number.isInteger(jo) ? jo : jo.toFixed(1)}조원`;
  }
  return `${formatNumber(eok)}억원`;
}

export const TOOLTIP_STYLE = {
  backgroundColor: "var(--color-popover, #fff)",
  border: "1px solid var(--color-border, #e5e7eb)",
  borderRadius: "8px",
  boxShadow:
    "0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)",
  color: "var(--color-popover-foreground, #1f2937)",
  fontSize: "13px",
  padding: "8px 12px",
} as const;

export const AXIS_TICK_STYLE = {
  fill: "var(--color-muted-foreground, #6b7280)",
  fontSize: 12,
} as const;

export const GRID_STYLE = {
  stroke: "var(--color-border, #e5e7eb)",
} as const;

/** 기수별 색상 — 현재/최신 기수는 항상 orange 강조 */
export const BATCH_COLORS: Record<number, string> = {
  1: "#94a3b8",
  2: "#a1a1aa",
  3: "#a3a3a3",
  4: "#78716c",
  5: "#6366f1",
  6: "#8b5cf6",
  7: "#f97316",
};

/** 산업분야 색상 (21색 순환) */
export const INDUSTRY_COLORS = [
  "#6366f1", "#8b5cf6", "#a78bfa", "#c084fc",
  "#f97316", "#fb923c", "#fdba74",
  "#10b981", "#34d399", "#6ee7b7",
  "#3b82f6", "#60a5fa", "#93c5fd",
  "#ef4444", "#f87171",
  "#eab308", "#facc15",
  "#ec4899", "#f472b6",
  "#14b8a6", "#2dd4bf",
] as const;

/** 지역 색상 (17색) */
export const LOCATION_COLORS = [
  "#3b82f6", "#6366f1", "#8b5cf6", "#a78bfa",
  "#10b981", "#14b8a6", "#06b6d4",
  "#f97316", "#eab308", "#ef4444",
  "#ec4899", "#78716c", "#94a3b8",
  "#64748b", "#6b7280", "#71717a", "#737373",
] as const;

/** 투자 스테이지 정렬 순서 (config.py 분류 체계와 동일) */
export const STAGE_ORDER = [
  "Pre-seed", "Seed", "Pre-A", "Series A", "Series B", "Series C",
  "Series D", "Series E ~", "Pre-IPO", "IPO", "M&A", "알 수 없음",
] as const;

/** IPO('24)/M&A('21) 등 연도 표기를 묶기 위한 스테이지 그룹 키 */
export function stageGroup(stage: string): string {
  const s = stage.trim();
  if (s.startsWith("IPO")) return "IPO";
  if (s.startsWith("M&A")) return "M&A";
  return s || "알 수 없음";
}

/** 스테이지별 색상 — INDUSTRY_COLORS에서 순서대로 배정 (하드코딩 금지 규칙 대응) */
export function stageColor(stage: string): string {
  const idx = STAGE_ORDER.indexOf(stageGroup(stage) as (typeof STAGE_ORDER)[number]);
  if (idx < 0) return INDUSTRY_COLORS[INDUSTRY_COLORS.length - 1];
  return INDUSTRY_COLORS[idx % INDUSTRY_COLORS.length];
}
