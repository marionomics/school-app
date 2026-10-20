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
    // Toggling is its own inverse, so the rollback toggles back.
    onMutate: async (post) => {
      const toggle = (p: Post) => toggleAura(p, isTeacher);
      return { rollback: await patchPostInCaches(qc, post, toggle, toggle) };
    },
    onError: (_e, _post, ctx) => {
      ctx?.rollback();
      toast.show(es.post.likeError);
    },
    onSettled: () => {
      // Never refetch the feed: a refetch re-sorts it whenever someone has
      // posted meanwhile, and the teacher's next tap lands on the wrong card.
      // The optimistic patch is the truth until the user refreshes. The
      // teacher's aura is also a validation, so /revisar changes with it.
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
