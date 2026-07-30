import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { es } from "@/strings/es";
import type { GradeSummary } from "@/lib/types";

export default function GradeChip() {
  const [open, setOpen] = useState(false);
  const q = useQuery({
    queryKey: ["grade"],
    queryFn: () => api<GradeSummary[]>("/api/students/me/grade"),
  });

  const total = (q.data ?? []).reduce((acc, g) => acc + g.total, 0);

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="rounded-full bg-primary/10 px-3 py-1 text-sm font-semibold text-primary"
        aria-label={es.grade.title}
      >
        {q.isPending ? "…" : `${total} ${es.grade.points}`}
      </button>

      {open && (
        <div className="fixed inset-0 z-40 flex items-end bg-black/40" onClick={() => setOpen(false)}>
          <div
            className="max-h-[80dvh] w-full overflow-y-auto rounded-t-2xl bg-background p-5"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="text-lg font-bold">{es.grade.title}</h2>
            {q.isError && <p className="mt-3 text-muted-foreground">{es.grade.error}</p>}
            {q.data?.length === 0 && (
              <p className="mt-3 text-muted-foreground">{es.grade.empty}</p>
            )}
            {q.data?.map((g) => (
              <section key={g.class_id} className="mt-4">
                <div className="flex items-baseline justify-between">
                  <h3 className="font-semibold">{g.class_name}</h3>
                  <span className="text-2xl font-bold text-primary">
                    {g.total} {es.grade.points}
                  </span>
                </div>
                <dl className="mt-2 space-y-1 text-sm">
                  <div className="flex justify-between">
                    <dt>🗣️ {es.grade.participaciones}</dt>
                    <dd>{g.counts.participaciones}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt>♥ {es.grade.likes}</dt>
                    <dd>{g.counts.likes_received}</dd>
                  </div>
                </dl>
                <ul className="mt-3 space-y-1 border-t pt-2 text-xs text-muted-foreground">
                  {g.events.slice(0, 15).map((ev, i) => (
                    <li key={i} className="flex justify-between">
                      <span>{ev.source_type === "participacion" ? "🗣️" : "♥"} {new Date(ev.created_at).toLocaleDateString("es-MX")}</span>
                      <span>+{ev.points}</span>
                    </li>
                  ))}
                </ul>
              </section>
            ))}
            <button onClick={() => setOpen(false)} className="mt-5 w-full rounded-md border py-2">
              {es.grade.close}
            </button>
          </div>
        </div>
      )}
    </>
  );
}
