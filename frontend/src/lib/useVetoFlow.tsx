import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import VetoDialog from "@/components/VetoDialog";
import { useToast } from "@/components/Toaster";
import { patchPostInCaches } from "@/lib/postCache";
import { setVeto } from "@/lib/review";
import { es } from "@/strings/es";
import type { Post } from "@/lib/types";

/** Veto from the feed or a thread: confirm before vetoing, never before
 *  lifting a veto (that is the safe direction). Optimistic, with rollback. */
export function useVetoFlow() {
  const qc = useQueryClient();
  const toast = useToast();
  const [confirming, setConfirming] = useState<Post | null>(null);

  const m = useMutation({
    mutationFn: ({ post, vetoed }: { post: Post; vetoed: boolean }) =>
      setVeto(post.id, vetoed),
    onMutate: async ({ post, vetoed }) => ({
      rollback: await patchPostInCaches(
        qc,
        post,
        (p) => ({ ...p, status: vetoed ? "vetoed" : "active" }),
        (p) => ({ ...p, status: post.status }),
      ),
    }),
    onError: (_e, _v, ctx) => {
      ctx?.rollback();
      toast.show(es.revisar.saveError);
    },
    // Not the feed: a refetch re-sorts it under the teacher's thumb. The
    // optimistic patch stands until the user refreshes.
    onSettled: () => {
      for (const k of ["thread", "review-participaciones", "grade", "profile"])
        void qc.invalidateQueries({ queryKey: [k] });
    },
  });

  const request = (post: Post) =>
    post.status === "vetoed"
      ? m.mutate({ post, vetoed: false })
      : setConfirming(post);

  const dialog = (
    <VetoDialog
      open={confirming != null}
      onCancel={() => setConfirming(null)}
      onConfirm={() => {
        if (confirming) m.mutate({ post: confirming, vetoed: true });
        setConfirming(null);
      }}
    />
  );

  return { request, dialog };
}
