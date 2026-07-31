import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useLikeMutation, openAttachment } from "@/lib/likes";
import { latenessTier } from "@/lib/lateness";
import PostCard from "@/components/PostCard";
import { FeedSkeleton } from "@/components/Skeletons";
import { useToast } from "@/components/Toaster";
import { es } from "@/strings/es";
import type { Post, ThreadResponse } from "@/lib/types";

export default function Thread() {
  const { id } = useParams();
  const { user } = useAuth();
  const qc = useQueryClient();
  const toast = useToast();
  const navigate = useNavigate();
  const like = useLikeMutation();
  const [reply, setReply] = useState("");
  const [replyTo, setReplyTo] = useState<Post | null>(null);
  const [confirming, setConfirming] = useState<Post | null>(null);
  const [isEntrega, setIsEntrega] = useState(false);

  const q = useQuery({
    queryKey: ["thread", id],
    queryFn: () => api<ThreadResponse>(`/api/posts/${id}`),
  });

  const send = useMutation({
    mutationFn: () => {
      const fd = new FormData();
      fd.set("content", reply);
      fd.set("parent_id", String(replyTo ? replyTo.id : id));
      if (isEntrega) fd.set("is_entrega", "true");
      return api<Post>("/api/posts", { method: "POST", body: fd });
    },
    onSuccess: () => {
      setReply("");
      setReplyTo(null);
      setIsEntrega(false);
      void qc.invalidateQueries({ queryKey: ["thread", id] });
      void qc.invalidateQueries({ queryKey: ["feed"] });
    },
    onError: () => toast.show(es.post.replyError),
  });

  const remove = useMutation({
    mutationFn: (post: Post) => api<void>(`/api/posts/${post.id}`, { method: "DELETE" }),
    onSuccess: (_d, post) => {
      setConfirming(null);
      void qc.invalidateQueries({ queryKey: ["feed"] });
      if (post.id === Number(id)) navigate("/", { replace: true });
      else void qc.invalidateQueries({ queryKey: ["thread", id] });
    },
    onError: () => toast.show(es.post.deleteError),
  });

  if (q.isPending) return <FeedSkeleton />;
  if (q.isError || !q.data)
    return <p className="p-6 text-center text-muted-foreground">{es.feed.error}</p>;

  const { post, replies } = q.data;
  const tierLabel = (() => {
    if (post.type !== "tarea" || !post.due_date) return null;
    const { key } = latenessTier(new Date(), new Date(post.due_date));
    return {
      onTime: es.post.entregaOnTime,
      under24h: es.post.entregaUnder24h,
      underWeek: es.post.entregaUnderWeek,
      late: es.post.entregaLate,
    }[key];
  })();
  const canDelete = (p: Post) => user != null && (user.id === p.author.id || user.role === "teacher");
  const level2 = replies.filter((r) => r.parent_id === post.id);
  const childrenOf = (rid: number) => replies.filter((r) => r.parent_id === rid);

  const card = (p: Post, indent: number) => (
    <div key={p.id} style={{ marginLeft: indent * 24 }}>
      <PostCard
        post={p}
        linkToThread={false}
        onLike={(x) => like.mutate(x)}
        canDelete={canDelete(p)}
        onDelete={setConfirming}
        onOpenAttachment={(aid) => void openAttachment(aid, toast.show)}
      />
      {p.id !== post.id && p.parent_id === post.id && (
        <button
          className="mb-2 ml-4 text-xs text-muted-foreground"
          onClick={() => {
            setReplyTo(p);
            setIsEntrega(false);
          }}
        >
          ↩ {es.post.replySubmit}
        </button>
      )}
    </div>
  );

  return (
    <div className="pb-28">
      {card(post, 0)}
      <div className="divide-y border-t">
        {level2.map((r) => (
          <div key={r.id} className="py-1">
            {card(r, 1)}
            {childrenOf(r.id).map((rr) => card(rr, 2))}
          </div>
        ))}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (reply.trim()) send.mutate();
        }}
        className="fixed inset-x-0 bottom-14 border-t bg-background p-3"
      >
        {replyTo && (
          <p className="mb-1 text-xs text-muted-foreground">
            ↩ @{replyTo.author.username ?? replyTo.author.name}{" "}
            <button type="button" onClick={() => setReplyTo(null)}>×</button>
          </p>
        )}
        {post.type === "tarea" && replyTo === null && (
          <div className="mb-1 flex flex-col gap-1">
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={isEntrega}
                onChange={(e) => setIsEntrega(e.target.checked)}
              />
              {es.post.entregaToggle}
            </label>
            {isEntrega && tierLabel && (
              <p className="text-xs text-muted-foreground">{tierLabel}</p>
            )}
          </div>
        )}
        <div className="flex gap-2">
          <input
            className="flex-1 rounded-full border px-4 py-2"
            placeholder={es.post.replyPlaceholder}
            value={reply}
            onChange={(e) => setReply(e.target.value)}
          />
          <button disabled={!reply.trim() || send.isPending} className="rounded-full bg-primary px-4 py-2 text-primary-foreground disabled:opacity-50">
            {es.post.replySubmit}
          </button>
        </div>
      </form>

      {confirming && (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/40 p-6">
          <div className="w-full max-w-sm rounded-xl bg-background p-5">
            <h2 className="font-semibold">{es.post.deleteConfirmTitle}</h2>
            <p className="mt-1 text-sm text-muted-foreground">{es.post.deleteConfirmBody}</p>
            <div className="mt-4 flex justify-end gap-3">
              <button onClick={() => setConfirming(null)} className="px-3 py-2">
                {es.post.cancel}
              </button>
              <button
                onClick={() => remove.mutate(confirming)}
                className="rounded-md bg-destructive px-3 py-2 text-destructive-foreground"
              >
                {es.post.deleteConfirm}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
