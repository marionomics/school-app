import { es } from "../strings/es";
import type { StreakLevel, StreakMe } from "./types";

export function daysToNext(s: StreakMe): number | null {
  return s.next_level_at == null ? null : s.next_level_at - s.days;
}

export function multiplierToast(m: number | null | undefined): string | null {
  if (m === 3) {
    return es.streak.toastTriple;
  }
  if (m === 2) {
    return es.streak.toastDouble;
  }
  return null;
}

export function pct(x: number): string {
  return `${Math.round(x * 100)}%`;
}

export function levelsSummary(levels: StreakLevel[]): string {
  return levels.map((level) => level.from_days).join("/");
}
