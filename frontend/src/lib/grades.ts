import type { QueryClient } from "@tanstack/react-query";

/** Every cache that shows a computed grade: the student's chip, the class
 *  panel's student sheet and the profile's private grades. Anything that
 *  moves points calls this, so no surface is left showing the old total. */
export const GRADE_QUERY_KEYS = [["grade"], ["student-grade"], ["profile"]] as const;

export function invalidateGrades(qc: QueryClient): void {
  for (const queryKey of GRADE_QUERY_KEYS) void qc.invalidateQueries({ queryKey: [...queryKey] });
}

/** A team change moves a shared grade on every surface that shows the
 *  entrega: the thread, the examen roster, the /revisar queue and the totals. */
export function invalidateTeamChange(qc: QueryClient): void {
  for (const queryKey of [["thread"], ["examen-roster"], ["review-entregas"], ["feed"]])
    void qc.invalidateQueries({ queryKey });
  invalidateGrades(qc);
}
