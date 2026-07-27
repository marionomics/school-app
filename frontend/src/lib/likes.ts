import { useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Post } from "@/lib/types";

export function useLikeMutation() {
  return useMutation({
    mutationFn: (post: Post) =>
      api<{ liked: boolean; like_count: number }>(`/api/posts/${post.id}/like`, {
        method: "POST",
      }),
  });
}
