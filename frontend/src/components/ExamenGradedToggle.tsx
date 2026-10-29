import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { markGraded } from "@/lib/review";
import { invalidateGrades } from "@/lib/grades";
import { patchFeedPost } from "@/lib/postCache";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/Toaster";
import { es } from "@/strings/es";
import type { ExamenRoster } from "@/lib/types";

/** "Marcar como calificado" from the examen's own thread, so grading never
 *  needs a trip to /revisar. Reads the same roster as /revisar for the count
 *  of students who would score 0. */
export default function ExamenGradedToggle({ examenId }: { examenId: number }) {
  const qc = useQueryClient();
  const toast = useToast();
  const q = useQuery({
    queryKey: ["examen-roster", examenId],
    queryFn: () => api<ExamenRoster>(`/api/review/examenes/${examenId}`),
  });

  const flip = useMutation({
    mutationFn: (graded: boolean) => markGraded(examenId, graded),
    onSuccess: ({ graded_at }) => {
      void qc.invalidateQueries({ queryKey: ["examen-roster", examenId] });
      void qc.invalidateQueries({ queryKey: ["thread", String(examenId)] });
      patchFeedPost(qc, examenId, (p) => ({ ...p, graded_at }));
      invalidateGrades(qc);
    },
    onError: () => toast.show(es.revisar.saveError),
  });

  if (!q.data) return null;
  const graded = q.data.examen.graded_at != null;
  const missing = q.data.rows.filter((r) => r.score == null).length;

  return (
    <div className="flex flex-col gap-2 px-4 pb-3">
      {!graded && missing > 0 && (
        <p className="text-xs text-muted-foreground">
          {es.revisar.markGradedWarning.replace("{n}", String(missing))}
        </p>
      )}
      <Button
        className="w-full"
        variant={graded ? "outline" : "default"}
        disabled={flip.isPending}
        onClick={() => flip.mutate(!graded)}
      >
        {graded ? es.revisar.unmarkGraded : es.revisar.markGraded}
      </Button>
    </div>
  );
}
