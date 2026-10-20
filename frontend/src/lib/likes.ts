import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { patchPostInCaches, toggleAura } from "@/lib/postCache";
import { es } from "@/strings/es";
import { useToast } from "@/components/Toaster";
import type { Post } from "@/lib/types";

export function useLikeMutation() {
  const qc = useQueryClient();
  const toast = useToast();
  const { user } = useAuth();
  const isTeacher = user?.role === "teacher";
  return useMutation({
    mutationFn: (post: Post) =>
      api<{ liked: boolean; like_count: number }>(`/api/posts/${post.id}/like`, {
        method: "POST",
      }),
    onMutate: async (post) => ({
      rollback: await patchPostInCaches(qc, post, (p) => toggleAura(p, isTeacher)),
    }),
    onError: (_e, _post, ctx) => {
      ctx?.rollback();
      toast.show(es.post.likeError);
    },
    onSettled: () => {
      // Aura no longer bumps last_activity_at, so refetching the feed cannot
      // re-sort it under the reader. The teacher's aura is also a validation,
      // so the /revisar queue changes with it.
      void qc.invalidateQueries({ queryKey: ["feed"] });
      void qc.invalidateQueries({ queryKey: ["thread"] });
      if (isTeacher) void qc.invalidateQueries({ queryKey: ["review-participaciones"] });
    },
  });
}

export async function openAttachment(id: number, onError: (m: string) => void) {
  try {
    const { url } = await api<{ url: string }>(`/api/attachments/${id}/url`);
    window.open(url, "_blank", "noopener");
  } catch {
    onError(es.post.attachmentError);
  }
}
