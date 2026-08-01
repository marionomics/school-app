import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { isScoreValid, markGraded, saveReview } from "@/lib/review";
import { useToast } from "@/components/Toaster";
import { es } from "@/strings/es";
import type { ExamenRoster } from "@/lib/types";

export default function ExamenRosterPanel({ examenId }: { examenId: number }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [draft, setDraft] = useState<Record<number, string>>({});

  const q = useQuery({
    queryKey: ["examen-roster", examenId],
    queryFn: () => api<ExamenRoster>(`/api/review/examenes/${examenId}`),
  });

  const save = useMutation({
    mutationFn: ({
      studentId,
      score,
    }: {
      studentId: number;
      score: number;
    }) => saveReview({ item_post_id: examenId, student_id: studentId, score }),
    onError: () => toast.show(es.revisar.saveError),
  });

  const flip = useMutation({
    mutationFn: (graded: boolean) => markGraded(examenId, graded),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["examen-roster", examenId] });
      void qc.invalidateQueries({ queryKey: ["grade"] });
    },
    onError: () => toast.show(es.revisar.saveError),
  });

  if (q.isPending) return <p className="text-muted-foreground">…</p>;
  if (q.isError)
    return <p className="text-muted-foreground">{es.feed.error}</p>;

  const { examen, rows } = q.data;
  const missing = rows.filter((r) => r.score == null).length;

  function commit(studentId: number, raw: string) {
    const score = Number(raw);
    if (raw === "" || !isScoreValid(score, "examen")) return;
    save.mutate({ studentId, score });
  }

  return (
    <div className="flex flex-col gap-3">
      <ul className="divide-y rounded-lg border">
        {rows.map((r) => (
          <li
            key={r.student.id}
            className="flex items-center justify-between px-3 py-2"
          >
            <span>@{r.student.username ?? r.student.name}</span>
            <input
              type="number"
              inputMode="numeric"
              min={1}
              max={10}
              className="w-20 rounded-md border px-2 py-1 text-right"
              value={
                draft[r.student.id] ??
                (r.score != null ? String(r.score) : "")
              }
              onChange={(e) =>
                setDraft({ ...draft, [r.student.id]: e.target.value })
              }
              onBlur={(e) => commit(r.student.id, e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") (e.target as HTMLInputElement).blur();
              }}
            />
          </li>
        ))}
      </ul>

      {examen.graded_at == null && missing > 0 && (
        <p className="text-xs text-muted-foreground">
          {es.revisar.markGradedWarning.replace("{n}", String(missing))}
        </p>
      )}
      <button
        onClick={() => flip.mutate(examen.graded_at == null)}
        className="rounded-full border px-4 py-2 text-sm"
      >
        {examen.graded_at == null
          ? es.revisar.markGraded
          : es.revisar.unmarkGraded}
      </button>
    </div>
  );
}
