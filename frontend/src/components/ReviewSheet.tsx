import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { isScoreValid, saveReview, scoreRange, type ItemType } from "@/lib/review";
import { useToast } from "@/components/Toaster";
import { es } from "@/strings/es";
import type { QueueStudent } from "@/lib/types";

export default function ReviewSheet({
  item, student, entregaPostId, autoScore, initialScore, initialFeedback, onSaved, onClose,
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
    onSuccess: () => { onSaved(); onClose(); },
    onError: () => toast.show(es.revisar.saveError),
  });

  return (
    <div className="fixed inset-0 z-40 flex items-end bg-black/40" onClick={onClose}>
      <div
        className="max-h-[85dvh] w-full overflow-y-auto rounded-t-2xl bg-background p-4"
        onClick={(e) => e.stopPropagation()}
      >
        <p className="font-bold">@{student.username ?? student.name}</p>
        {autoScore != null && (
          <p className="text-sm text-muted-foreground">
            {es.revisar.autoScore.replace("{n}", String(autoScore))}
          </p>
        )}
        <label className="mt-3 block text-sm">
          {es.revisar.scoreLabel}
          <input
            type="number"
            inputMode="numeric"
            min={low}
            max={high}
            className="ml-2 w-24 rounded-md border px-2 py-1"
            value={score}
            onChange={(e) => setScore(e.target.value)}
          />
        </label>
        {!valid && score !== "" && (
          <p className="mt-1 text-xs text-destructive">
            {es.revisar.scoreInvalid.replace("{low}", String(low)).replace("{high}", String(high))}
          </p>
        )}
        <label className="mt-3 block text-sm">
          {es.revisar.feedbackLabel}
          <textarea
            className="mt-1 min-h-24 w-full rounded-lg border p-2"
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
          />
        </label>
        <button
          disabled={!valid || save.isPending}
          onClick={() => save.mutate()}
          className="mt-3 w-full rounded-full bg-primary py-2 text-primary-foreground disabled:opacity-50"
        >
          {es.revisar.save}
        </button>
      </div>
    </div>
  );
}
