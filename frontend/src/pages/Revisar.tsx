import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import ReviewSheet from "@/components/ReviewSheet";
import ExamenRosterPanel from "@/components/ExamenRoster";
import { FeedSkeleton } from "@/components/Skeletons";
import { setVeto } from "@/lib/review";
import { useToast } from "@/components/Toaster";
import { es } from "@/strings/es";
import type {
  EntregaGroup,
  EntregaRow,
  ExamenListItem,
  MyClasses,
  ParticipacionRow,
  QueueStudent,
} from "@/lib/types";

type Tab = "entregas" | "examenes" | "participaciones";

export default function Revisar() {
  const [tab, setTab] = useState<Tab>("entregas");
  const [classId, setClassId] = useState<number | null>(null);
  const qc = useQueryClient();

  const mine = useQuery({
    queryKey: ["classes-mine"],
    queryFn: () => api<MyClasses>("/api/classes/mine"),
  });
  const teaching = mine.data?.teaching ?? [];
  const activeClass = classId ?? teaching[0]?.id ?? null;

  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-4 p-4">
      <h1 className="font-bold">{es.revisar.title}</h1>

      {teaching.length > 1 && (
        <select
          className="rounded-md border px-2 py-1 text-sm"
          value={activeClass ?? ""}
          onChange={(e) => setClassId(Number(e.target.value))}
        >
          {teaching.map((k) => (
            <option key={k.id} value={k.id}>
              {k.name}
            </option>
          ))}
        </select>
      )}

      <div className="flex gap-2 overflow-x-auto">
        {(["entregas", "examenes", "participaciones"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`whitespace-nowrap rounded-full px-3 py-1 text-sm ${
              tab === t ? "bg-primary text-primary-foreground" : "border"
            }`}
          >
            {t === "entregas"
              ? es.revisar.tabEntregas
              : t === "examenes"
                ? es.revisar.tabExamenes
                : es.revisar.tabParticipaciones}
          </button>
        ))}
      </div>

      {activeClass != null && tab === "entregas" && (
        <EntregasTab
          classId={activeClass}
          onSaved={() => {
            void qc.invalidateQueries({ queryKey: ["review-entregas"] });
          }}
        />
      )}

      {activeClass != null && tab === "examenes" && (
        <ExamenesTab classId={activeClass} />
      )}

      {activeClass != null && tab === "participaciones" && (
        <ParticipacionesTab classId={activeClass} />
      )}
    </main>
  );
}

function EntregasTab({
  classId,
  onSaved,
}: {
  classId: number;
  onSaved: () => void;
}) {
  const [open, setOpen] = useState<{
    tareaId: number;
    row: EntregaRow;
  } | null>(null);

  const q = useQuery({
    queryKey: ["review-entregas", classId],
    queryFn: () =>
      api<{ groups: EntregaGroup[] }>(
        `/api/review/entregas?class_id=${classId}&status=unopened`,
      ),
  });

  if (q.isPending) return <FeedSkeleton />;
  if (q.isError)
    return <p className="text-muted-foreground">{es.feed.error}</p>;
  if (q.data.groups.length === 0)
    return (
      <p className="text-center text-muted-foreground">{es.revisar.empty}</p>
    );

  return (
    <div className="flex flex-col gap-4">
      {q.data.groups.map((g) => (
        <section key={g.tarea.id}>
          <h2 className="text-sm font-bold">
            {g.tarea.content.slice(0, 60)}
            <span className="ml-2 font-normal text-muted-foreground">
              {es.revisar.pending.replace("{n}", String(g.pending))}
            </span>
          </h2>
          <ul className="mt-1 divide-y rounded-lg border">
            {g.entregas.map((row) => (
              <li key={row.entrega_post_id}>
                <button
                  className="flex w-full items-center justify-between px-3 py-3 text-left"
                  onClick={() => setOpen({ tareaId: g.tarea.id, row })}
                >
                  <span>@{row.student.username ?? row.student.name}</span>
                  <span className="text-sm text-muted-foreground">
                    {row.auto_score != null
                      ? es.revisar.autoScore.replace(
                          "{n}",
                          String(row.auto_score),
                        )
                      : ""}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      ))}
      {open && (
        <ReviewSheet
          item={{ id: open.tareaId, type: "tarea" }}
          student={open.row.student as QueueStudent}
          entregaPostId={open.row.entrega_post_id}
          autoScore={open.row.auto_score}
          initialScore={open.row.score}
          initialFeedback=""
          onSaved={onSaved}
          onClose={() => setOpen(null)}
        />
      )}
    </div>
  );
}

function ExamenesTab({ classId }: { classId: number }) {
  const [openId, setOpenId] = useState<number | null>(null);
  const q = useQuery({
    queryKey: ["review-examenes", classId],
    queryFn: () =>
      api<{ items: ExamenListItem[] }>(
        `/api/review/examenes?class_id=${classId}`,
      ),
    select: (data) => data.items,
  });

  if (q.isPending) return <FeedSkeleton />;
  if (!q.data || q.data.length === 0)
    return (
      <p className="text-center text-muted-foreground">{es.revisar.empty}</p>
    );

  if (openId != null)
    return (
      <div className="flex flex-col gap-2">
        <button
          className="self-start text-sm text-muted-foreground"
          onClick={() => setOpenId(null)}
        >
          ←
        </button>
        <ExamenRosterPanel examenId={openId} />
      </div>
    );

  return (
    <ul className="divide-y rounded-lg border">
      {q.data.map((x) => (
        <li key={x.id}>
          <button
            className="flex w-full items-center justify-between px-3 py-3 text-left"
            onClick={() => setOpenId(x.id)}
          >
            <span>{x.content.slice(0, 50)}</span>
            <span className="text-xs text-muted-foreground">
              {x.graded_at ? es.revisar.graded : ""}
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}

function ParticipacionesTab({ classId }: { classId: number }) {
  const qc = useQueryClient();
  const toast = useToast();
  const key = ["review-participaciones", classId];

  const q = useQuery({
    queryKey: key,
    queryFn: () =>
      api<{ items: ParticipacionRow[] }>(
        `/api/review/participaciones?class_id=${classId}`,
      ),
  });

  const toggle = useMutation({
    mutationFn: ({
      postId,
      vetoed,
    }: {
      postId: number;
      vetoed: boolean;
    }) => setVeto(postId, vetoed),
    onMutate: async ({ postId, vetoed }) => {
      await qc.cancelQueries({ queryKey: key });
      const prev = qc.getQueryData<{ items: ParticipacionRow[] }>(key);
      qc.setQueryData<{ items: ParticipacionRow[] }>(key, (old) =>
        old
          ? {
              items: old.items.map((i) =>
                i.post_id === postId ? { ...i, vetoed } : i,
              ),
            }
          : old,
      );
      return { prev };
    },
    onError: (_e, _v, ctx) => {
      if (ctx?.prev) qc.setQueryData(key, ctx.prev);
      toast.show(es.revisar.saveError);
    },
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: key });
      void qc.invalidateQueries({ queryKey: ["grade"] });
    },
  });

  if (q.isPending) return <FeedSkeleton />;
  if (q.isError)
    return <p className="text-muted-foreground">{es.feed.error}</p>;
  if (q.data.items.length === 0)
    return (
      <p className="text-center text-muted-foreground">{es.revisar.empty}</p>
    );

  return (
    <ul className="divide-y rounded-lg border">
      {q.data.items.map((i) => (
        <li
          key={i.post_id}
          className="flex items-start justify-between gap-3 px-3 py-3"
        >
          <div className="min-w-0">
            <p className="text-sm font-medium">
              @{i.student.username ?? i.student.name}
              <span className="ml-2 font-normal text-muted-foreground">
                ×{i.taps ?? 0} · {i.points}
              </span>
            </p>
            <p className="truncate text-sm text-muted-foreground">
              {i.content}
            </p>
          </div>
          <button
            onClick={() =>
              toggle.mutate({ postId: i.post_id, vetoed: !i.vetoed })
            }
            className={`shrink-0 rounded-full px-3 py-1 text-xs ${
              i.vetoed
                ? "border"
                : "bg-destructive text-destructive-foreground"
            }`}
          >
            {i.vetoed ? es.revisar.unveto : es.revisar.veto}
          </button>
        </li>
      ))}
    </ul>
  );
}
