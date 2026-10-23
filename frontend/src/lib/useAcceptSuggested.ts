import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useToast } from "@/components/Toaster";
import { invalidateGrades } from "@/lib/grades";
import { patchFeedPost } from "@/lib/postCache";
import { acceptSuggested } from "@/lib/review";
import { es } from "@/strings/es";

/** One tap grades every entrega on screen with its suggested score. Shared
 *  by the tarea's thread and /revisar so both refresh the same caches. */
export function useAcceptSuggested() {
  const qc = useQueryClient();
  const toast = useToast();
  return useMutation({
    mutationFn: ({ itemId, ids }: { itemId: number; ids: number[] }) =>
      acceptSuggested(itemId, ids),
    onSuccess: ({ graded }, { itemId }) => {
      toast.show(es.revisar.acceptedSuggested.replace("{n}", String(graded)));
      void qc.invalidateQueries({ queryKey: ["thread"] });
      void qc.invalidateQueries({ queryKey: ["review-entregas"] });
      invalidateGrades(qc);
      // The tarea's "N por calificar" in the feed; patched, never refetched.
      patchFeedPost(qc, itemId, (p) => {
        const left = Math.max(0, (p.pending_count ?? 0) - graded);
        return { ...p, pending_count: left > 0 ? left : null };
      });
    },
    onError: () => toast.show(es.revisar.saveError),
  });
}
