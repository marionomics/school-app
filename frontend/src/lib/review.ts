// Relative, like every other module in src/lib. The "@/" alias does not
// resolve under vitest, so a module using it makes its own test file
// unrunnable — which is what had happened to review.test.ts.
import { api } from "./api";
import type { Review } from "./types";

export type ItemType = "tarea" | "examen";

/** A tarea is scored 0–100, an examen 1–10. Never mix the two. */
export function scoreRange(itemType: ItemType): [number, number] {
  return itemType === "examen" ? [1, 10] : [0, 100];
}

export function isScoreValid(score: number, itemType: ItemType): boolean {
  if (!Number.isFinite(score)) return false;
  const [low, high] = scoreRange(itemType);
  return score >= low && score <= high;
}

export interface ReviewInput {
  item_post_id: number;
  student_id: number;
  entrega_post_id?: number | null;
  score?: number | null;
  feedback?: string | null;
}

export function saveReview(input: ReviewInput) {
  return api<Review>("/api/reviews", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export function markGraded(postId: number, graded: boolean) {
  return api<{ graded_at: string | null }>(`/api/posts/${postId}/graded`, {
    method: graded ? "POST" : "DELETE",
  });
}

export function setVeto(postId: number, vetoed: boolean, reason?: string) {
  return api<{ status: string; veto_reason: string | null }>(
    `/api/posts/${postId}/veto`,
    vetoed
      ? { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ reason: reason ?? null }) }
      : { method: "DELETE" },
  );
}
