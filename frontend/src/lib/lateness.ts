export type LatenessKey = "onTime" | "under24h" | "underWeek" | "late";

const HOUR = 3600_000;
const DAY = 24 * HOUR;

/** Mirrors backend lateness_score. Boundaries closed at the top:
 *  exactly 24h is 50, exactly 7 days is 20. */
export function latenessTier(
  entregaAt: Date,
  dueAt: Date,
): { pct: number; key: LatenessKey } {
  const delta = entregaAt.getTime() - dueAt.getTime();
  if (delta <= 0) return { pct: 100, key: "onTime" };
  if (delta < DAY) return { pct: 90, key: "under24h" };
  if (delta < 7 * DAY) return { pct: 50, key: "underWeek" };
  return { pct: 20, key: "late" };
}
