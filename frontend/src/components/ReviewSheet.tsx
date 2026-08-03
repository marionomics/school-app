import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import {
  isScoreValid,
  saveReview,
  scoreRange,
  type ItemType,
} from "@/lib/review";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/components/Toaster";
import { formatPoints } from "@/lib/points";
import { es } from "@/strings/es";
import type { QueueStudent } from "@/lib/types";

/** The one place a score is entered, wherever grading was started from —
 *  the Revisar queue or an entrega in the feed thread. */
export default function ReviewSheet({
  item,
  student,
  entregaPostId,
  autoScore,
  initialScore,
  initialFeedback,
  onSaved,
  onClose,
}: {
  item: { id: number; type: ItemType };
  student: QueueStudent;
  entregaPostId: number | null;
  autoScore: number | null;
  initialScore: number | null;
  initialFeedback: string;
  onSaved: () => void;
  onClose: () => void;
}) {
  const toast = useToast();
  const [low, high] = scoreRange(item.type);
  const [score, setScore] = useState<string>(
    String(initialScore ?? autoScore ?? ""),
  );
  const [feedback, setFeedback] = useState(initialFeedback);
  const value = Number(score);
  const valid = score !== "" && isScoreValid(value, item.type);

  const save = useMutation({
    mutationFn: () =>
      saveReview({
        item_post_id: item.id,
        student_id: student.id,
        entrega_post_id: entregaPostId,
        score: value,
        feedback: feedback.trim() || null,
      }),
    onSuccess: () => {
      onSaved();
      onClose();
    },
    onError: () => toast.show(es.revisar.saveError),
  });

  return (
    <div
      className="fixed inset-0 z-40 flex items-end bg-black/40"
      onClick={onClose}
    >
      <div
        className="max-h-[85dvh] w-full overflow-y-auto border-t bg-background p-4"
        onClick={(e) => e.stopPropagation()}
      >
        <p className="text-sm font-semibold">
          @{student.username ?? student.name}
        </p>
        {autoScore != null && (
          <p className="text-xs text-muted-foreground">
            {es.revisar.autoScore.replace("{n}", String(autoScore))}
          </p>
        )}

        <Label htmlFor="review-score" className="mt-4 block">
          {es.revisar.scoreLabel}
        </Label>
        <Input
          id="review-score"
          type="number"
          inputMode="numeric"
          min={low}
          max={high}
          className="mt-2 w-28"
          value={score}
          onChange={(e) => setScore(e.target.value)}
        />
        {/* A tarea is scored 0–100, an examen 1–10. Showing the décima
            equivalent keeps the two scales from blurring together. */}
        {valid && item.type === "tarea" && (
          <p className="mt-1 text-xs text-muted-foreground">
            {formatPoints(value)}
          </p>
        )}
        {!valid && score !== "" && (
          <p className="mt-1 text-xs text-destructive">
            {es.revisar.scoreInvalid
              .replace("{low}", String(low))
              .replace("{high}", String(high))}
          </p>
        )}

        <Label htmlFor="review-feedback" className="mt-4 block">
          {es.revisar.feedbackLabel}
        </Label>
        <textarea
          id="review-feedback"
          className="mt-2 min-h-24 w-full border bg-transparent p-2 text-sm"
          value={feedback}
          onChange={(e) => setFeedback(e.target.value)}
        />

        <Button
          className="mt-4 w-full"
          disabled={!valid || save.isPending}
          onClick={() => save.mutate()}
        >
          {es.revisar.save}
        </Button>
      </div>
    </div>
  );
}
