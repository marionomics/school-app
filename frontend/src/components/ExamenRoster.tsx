import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { openAttachment } from "@/lib/likes";
import { isScoreValid, markGraded, saveReview } from "@/lib/review";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import PostPhotos from "@/components/PostPhotos";
import UserLink from "@/components/UserLink";
import { useToast } from "@/components/Toaster";
import { es } from "@/strings/es";
import type { Author, ExamenRoster } from "@/lib/types";
import { invalidateGrades } from "@/lib/grades";

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
    onSuccess: (_d, { studentId }) => {
      // Teammates share the score: show the server's, not a stale draft —
      // but only for the row just saved; other rows may be mid-typing.
      setDraft((d) => {
        const rest = { ...d };
        delete rest[studentId];
        return rest;
      });
      void qc.invalidateQueries({ queryKey: ["examen-roster", examenId] });
    },
    onError: () => toast.show(es.revisar.saveError),
  });

  const flip = useMutation({
    mutationFn: (graded: boolean) => markGraded(examenId, graded),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["examen-roster", examenId] });
      invalidateGrades(qc);
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
      {/* The consulted exception to one-control-per-line: a roster row is a
          person plus the one thing you are setting. Stacking them would double
          the scrolling for forty students. */}
      <ul className="divide-y border-y">
        {rows.map((r) => (
          <li
            key={r.student.id}
            className="flex items-start justify-between gap-3 py-2"
          >
            {/* Whatever they uploaded, in either modality — the software
                serves the workflow, not the other way round (bug 8). */}
            <div className="flex min-w-0 flex-1 flex-col gap-1">
              <span className="text-sm">
                <UserLink user={r.student} plain />
              </span>
              {r.team_of && (
                <span className="text-xs text-muted-foreground">
                  {es.mentions.inTeamWith} <UserLink user={r.team_of} plain />
                </span>
              )}
              {r.submission && (
                <>
                  {r.submission.content && (
                    <p className="line-clamp-2 text-xs text-muted-foreground">
                      {r.submission.content}
                    </p>
                  )}
                  {r.submission.attachments.length > 0 && (
                    <PostPhotos
                      attachments={r.submission.attachments}
                      author={{ ...(r.team_of ?? r.student), avatar_url: null, role: "student" } satisfies Author}
                      onOpenFile={(id) => void openAttachment(id, toast.show)}
                    />
                  )}
                  <Link
                    to={`/post/${r.submission.post_id}`}
                    className="text-xs text-muted-foreground underline"
                  >
                    {es.revisar.openSubmission}
                  </Link>
                </>
              )}
            </div>
            <Input
              type="number"
              inputMode="numeric"
              min={1}
              max={10}
              className="w-20 shrink-0 text-right tabular-nums"
              value={
                draft[r.student.id] ??
                (r.score != null ? String(r.score) : "")
              }
              onChange={(e) => {
                const value = e.target.value;
                setDraft((d) => ({ ...d, [r.student.id]: value }));
              }}
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
      <Button
        variant={examen.graded_at == null ? "default" : "outline"}
        onClick={() => flip.mutate(examen.graded_at == null)}
      >
        {examen.graded_at == null
          ? es.revisar.markGraded
          : es.revisar.unmarkGraded}
      </Button>
    </div>
  );
}
