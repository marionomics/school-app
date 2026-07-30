import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { InfiniteData } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { es } from "@/strings/es";
import { useToast } from "@/components/Toaster";
import type { FeedPage, Post, ThreadResponse } from "@/lib/types";

function flipPost(p: Post): Post {
  return {
    ...p,
    liked_by_me: !p.liked_by_me,
    like_count: p.like_count + (p.liked_by_me ? -1 : 1),
  };
}

export function useLikeMutation() {
  const qc = useQueryClient();
  const toast = useToast();
  return useMutation({
    mutationFn: (post: Post) =>
      api<{ liked: boolean; like_count: number }>(`/api/posts/${post.id}/like`, {
        method: "POST",
      }),
    onMutate: async (post) => {
      await qc.cancelQueries({ queryKey: ["feed"] });
      const prevFeed = qc.getQueryData<InfiniteData<FeedPage>>(["feed"]);
      qc.setQueryData<InfiniteData<FeedPage>>(["feed"], (data) =>
        data
          ? {
              ...data,
              pages: data.pages.map((pg) => ({
                ...pg,
                items: pg.items.map((p) => (p.id === post.id ? flipPost(p) : p)),
              })),
            }
          : data,
      );
      const threadKey = ["thread", String(post.parent_id ?? post.id)];
      const prevThread = qc.getQueryData<ThreadResponse>(threadKey);
      qc.setQueryData<ThreadResponse>(threadKey, (t) =>
        t
          ? {
              post: t.post.id === post.id ? flipPost(t.post) : t.post,
              replies: t.replies.map((r) => (r.id === post.id ? flipPost(r) : r)),
            }
          : t,
      );
      return { prevFeed, prevThread, threadKey };
    },
    onError: (_e, _post, ctx) => {
      if (ctx?.prevFeed) qc.setQueryData(["feed"], ctx.prevFeed);
      if (ctx?.prevThread) qc.setQueryData(ctx.threadKey, ctx.prevThread);
      toast.show(es.post.likeError);
    },
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: ["feed"] });
      void qc.invalidateQueries({ queryKey: ["thread"] });
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
