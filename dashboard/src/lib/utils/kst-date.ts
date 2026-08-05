// ABOUTME: KST(한국 표준시) 날짜 유틸 — UTC 직접 비교 금지 규칙 대응
// ABOUTME: todayKst()로 오늘 날짜(YYYY-MM-DD)를 얻고 D-day 계산에 사용한다
const KST_OFFSET_MS = 9 * 60 * 60 * 1000;

/** 오늘 날짜를 KST 기준 YYYY-MM-DD 문자열로 반환 */
export function todayKst(): string {
  const kst = new Date(Date.now() + KST_OFFSET_MS);
  return kst.toISOString().slice(0, 10);
}

/** YYYY-MM-DD 날짜까지 남은 일수 (KST 기준, 지났으면 음수) */
export function daysUntilKst(dateStr: string): number | null {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) return null;
  const target = Date.parse(`${dateStr}T00:00:00+09:00`);
  const today = Date.parse(`${todayKst()}T00:00:00+09:00`);
  return Math.round((target - today) / (24 * 60 * 60 * 1000));
}
