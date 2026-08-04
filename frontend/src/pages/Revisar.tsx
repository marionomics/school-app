import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RiArrowLeftSLine } from "@remixicon/react";
import { api } from "@/lib/api";
import ReviewSheet from "@/components/ReviewSheet";
import ExamenRosterPanel from "@/components/ExamenRoster";
import { FeedSkeleton } from "@/components/Skeletons";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { bulkReviewed, setReviewed, setVeto } from "@/lib/review";
import { formatPoints } from "@/lib/points";
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

export default function Revisar() {
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
      <h1 className="text-sm font-semibold tracking-widest uppercase">
        {es.revisar.title}
      </h1>

      {teaching.length > 1 && (
        <select
          className="border bg-transparent px-2 py-2 text-sm"
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

      <Tabs defaultValue="entregas">
        <TabsList>
          <TabsTrigger value="entregas">{es.revisar.tabEntregas}</TabsTrigger>
          <TabsTrigger value="examenes">{es.revisar.tabExamenes}</TabsTrigger>
          <TabsTrigger value="participaciones">
            {es.revisar.tabParticipaciones}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="entregas">
          {activeClass != null && (
            <EntregasTab
              classId={activeClass}
              onSaved={() => {
                void qc.invalidateQueries({ queryKey: ["review-entregas"] });
              }}
            />
          )}
        </TabsContent>

        <TabsContent value="examenes">
          {activeClass != null && <ExamenesTab classId={activeClass} />}
        </TabsContent>

        <TabsContent value="participaciones">
          {activeClass != null && <ParticipacionesTab classId={activeClass} />}
        </TabsContent>
      </Tabs>
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
      <p className="py-8 text-center text-muted-foreground">
        {es.revisar.empty}
      </p>
    );

  return (
    <div className="flex flex-col gap-5">
      {q.data.groups.map((g) => (
        <section key={g.tarea.id}>
          <h2 className="text-[10px] font-semibold tracking-widest uppercase text-muted-foreground">
            {g.tarea.content.slice(0, 60)} ·{" "}
            {es.revisar.pending.replace("{n}", String(g.pending))}
          </h2>
          <ul className="mt-2 divide-y border-y">
            {g.entregas.map((row) => (
              <li key={row.entrega_post_id}>
                <button
                  className="flex w-full items-center justify-between py-3 text-left"
                  onClick={() => setOpen({ tareaId: g.tarea.id, row })}
                >
                  <span className="text-sm">
                    @{row.student.username ?? row.student.name}
                  </span>
                  <span className="text-xs text-muted-foreground tabular-nums">
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
      <p className="py-8 text-center text-muted-foreground">
        {es.revisar.empty}
      </p>
    );

  if (openId != null)
    return (
      <div className="flex flex-col gap-3">
        <Button
          variant="ghost"
          size="sm"
          className="self-start"
          onClick={() => setOpenId(null)}
        >
          <RiArrowLeftSLine className="size-4" /> {es.configurar.back}
        </Button>
        <ExamenRosterPanel examenId={openId} />
      </div>
    );

  return (
    <ul className="divide-y border-y">
      {q.data.map((x) => (
        <li key={x.id}>
          <button
            className="flex w-full items-center justify-between py-3 text-left"
            onClick={() => setOpenId(x.id)}
          >
            <span className="text-sm">{x.content.slice(0, 50)}</span>
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
  // The queue shows what still needs you. "Vistas" holds everything handled —
  // validated or vetoed — so you can go back and undo either.
  const [showHandled, setShowHandled] = useState(false);
  const [confirmingVeto, setConfirmingVeto] = useState<ParticipacionRow | null>(
    null,
  );
  const key = ["review-participaciones", classId, showHandled];

  const q = useQuery({
    queryKey: key,
    queryFn: () =>
      api<{ items: ParticipacionRow[] }>(
        `/api/review/participaciones?class_id=${classId}&status=${
          showHandled ? "handled" : "pending"
        }`,
      ),
  });

  function patchRow(postId: number, patch: Partial<ParticipacionRow>) {
    qc.setQueryData<{ items: ParticipacionRow[] }>(key, (old) =>
      old
        ? {
            items: old.items.map((i) =>
              i.post_id === postId ? { ...i, ...patch } : i,
            ),
          }
        : old,
    );
  }

  const review = useMutation({
    mutationFn: ({ postId, reviewed }: { postId: number; reviewed: boolean }) =>
      setReviewed(postId, reviewed),
    onMutate: async ({ postId, reviewed }) => {
      await qc.cancelQueries({ queryKey: key });
      const prev = qc.getQueryData<{ items: ParticipacionRow[] }>(key);
      patchRow(postId, { reviewed });
      return { prev };
    },
    onError: (_e, _v, ctx) => {
      if (ctx?.prev) qc.setQueryData(key, ctx.prev);
      toast.show(es.revisar.saveError);
    },
    onSettled: () => void qc.invalidateQueries({ queryKey: key }),
  });

  const bulk = useMutation({
    // rows, not "everything pending": exactly what is on screen.
    mutationFn: (ids: number[]) => bulkReviewed(ids),
    onError: () => toast.show(es.revisar.saveError),
    onSettled: () => void qc.invalidateQueries({ queryKey: key }),
  });

  const toggle = useMutation({
    mutationFn: ({ postId, vetoed }: { postId: number; vetoed: boolean }) =>
      setVeto(postId, vetoed),
    onMutate: async ({ postId, vetoed }) => {
      await qc.cancelQueries({ queryKey: key });
      const prev = qc.getQueryData<{ items: ParticipacionRow[] }>(key);
      patchRow(postId, { vetoed });
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

  const rows = q.data.items;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex gap-1">
        <Button
          variant={showHandled ? "ghost" : "secondary"}
          size="sm"
          onClick={() => setShowHandled(false)}
        >
          {es.revisar.filterPending}
        </Button>
        <Button
          variant={showHandled ? "secondary" : "ghost"}
          size="sm"
          onClick={() => setShowHandled(true)}
        >
          {es.revisar.filterHandled}
        </Button>
      </div>

      {!showHandled && rows.length > 0 && (
        <Button
          className="w-full"
          disabled={bulk.isPending}
          onClick={() => bulk.mutate(rows.map((r) => r.post_id))}
        >
          {es.revisar.validarTodas.replace("{n}", String(rows.length))}
        </Button>
      )}

      {rows.length === 0 && (
        <p className="py-8 text-center text-muted-foreground">
          {showHandled ? es.revisar.noneHandled : es.revisar.empty}
        </p>
      )}

      <ul className="divide-y border-y">
        {rows.map((i) => (
          <li
            key={i.post_id}
            className="flex items-start justify-between gap-3 py-3"
          >
            <div className="min-w-0">
              <p className="text-sm font-medium">
                @{i.student.username ?? i.student.name}
                <span className="ml-2 font-normal text-muted-foreground">
                  ×{i.taps ?? 0} · {formatPoints(i.points)}
                </span>
              </p>
              <p className="truncate text-sm text-muted-foreground">
                {i.content}
              </p>
              {i.vetoed && (
                <p className="text-xs text-destructive">{es.revisar.vetoed}</p>
              )}
              {!i.vetoed && i.reviewed && (
                <p className="text-xs text-muted-foreground">
                  {es.revisar.validated}
                </p>
              )}
            </div>
            <span className="flex shrink-0 gap-1">
              {/* Validar is quiet and reversible. Vetar takes points, so it
                  asks first — the two must never look alike. */}
              {!i.vetoed && (
                <Button
                  variant={i.reviewed ? "outline" : "secondary"}
                  size="sm"
                  onClick={() =>
                    review.mutate({ postId: i.post_id, reviewed: !i.reviewed })
                  }
                >
                  {i.reviewed ? es.revisar.unvalidate : es.revisar.validar}
                </Button>
              )}
              <Button
                variant={i.vetoed ? "outline" : "destructive"}
                size="sm"
                onClick={() =>
                  i.vetoed
                    ? toggle.mutate({ postId: i.post_id, vetoed: false })
                    : setConfirmingVeto(i)
                }
              >
                {i.vetoed ? es.revisar.unveto : es.revisar.veto}
              </Button>
            </span>
          </li>
        ))}
      </ul>

      <Dialog
        open={confirmingVeto != null}
        onOpenChange={() => setConfirmingVeto(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{es.revisar.vetoConfirmTitle}</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            {es.revisar.vetoConfirmBody}
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmingVeto(null)}>
              {es.configurar.cancel}
            </Button>
            <Button
              variant="destructive"
              onClick={() => {
                if (confirmingVeto)
                  toggle.mutate({
                    postId: confirmingVeto.post_id,
                    vetoed: true,
                  });
                setConfirmingVeto(null);
              }}
            >
              {es.revisar.vetoConfirmYes}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
