import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/Toaster";
import { es } from "@/strings/es";
import type { FaltaRow } from "@/lib/types";
import { invalidateGrades } from "@/lib/grades";

/** "2026-09-14" as a local calendar date. new Date("2026-09-14") is UTC
 *  midnight, which in Mexico City is the evening before. */
function formatDay(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("es-MX", {
    weekday: "short",
    day: "numeric",
    month: "short",
  });
}

/** Every absence of one student. A justified one stays visible, crossed out
 *  with its tag — it just stops costing (Mario, 2026-10-17). */
export default function FaltasList({
  classId,
  studentId,
}: {
  classId: number;
  studentId: number;
}) {
  const qc = useQueryClient();
  const toast = useToast();
  const key = ["faltas", classId, studentId];

  const q = useQuery({
    queryKey: key,
    queryFn: () =>
      api<{ faltas: FaltaRow[] }>(
        `/api/classes/${classId}/students/${studentId}/faltas`,
      ),
  });

  const justify = useMutation({
    mutationFn: ({ recordId, justified }: { recordId: number; justified: boolean }) =>
      api<{ record_id: number; justified: boolean }>(
        `/api/attendance/${recordId}/justification`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ justified }),
        },
      ),
    onMutate: async ({ recordId, justified }) => {
      await qc.cancelQueries({ queryKey: key });
      const prev = qc.getQueryData<{ faltas: FaltaRow[] }>(key);
      qc.setQueryData<{ faltas: FaltaRow[] }>(key, (old) =>
        old
          ? {
              faltas: old.faltas.map((f) =>
                f.record_id === recordId ? { ...f, justified } : f,
              ),
            }
          : old,
      );
      return { prev };
    },
    onError: (_e, _v, ctx) => {
      if (ctx?.prev) qc.setQueryData(key, ctx.prev);
      toast.show(es.faltas.saveError);
    },
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: key });
      invalidateGrades(qc);
      void qc.invalidateQueries({ queryKey: ["roster", classId] });
    },
  });

  if (q.isPending || q.isError || q.data.faltas.length === 0) return null;

  return (
    <section className="mt-5">
      <h3 className="text-xs font-semibold uppercase text-muted-foreground">
        {es.faltas.title}
      </h3>
      {/* A date plus the one thing you set on it — the same exception to
          one-control-per-line as pasar lista. */}
      <ul className="mt-2 divide-y border-y">
        {q.data.faltas.map((f) => (
          <li
            key={f.record_id}
            className="flex items-center justify-between gap-3 py-2 text-sm"
          >
            <span className="flex items-center gap-2">
              <span
                className={
                  f.justified ? "text-muted-foreground line-through" : undefined
                }
              >
                {formatDay(f.date)}
              </span>
              {f.justified && (
                <Badge variant="secondary">{es.faltas.justified}</Badge>
              )}
            </span>
            <Button
              size="sm"
              variant={f.justified ? "ghost" : "outline"}
              onClick={() =>
                justify.mutate({ recordId: f.record_id, justified: !f.justified })
              }
            >
              {f.justified ? es.faltas.unjustify : es.faltas.justify}
            </Button>
          </li>
        ))}
      </ul>
    </section>
  );
}
