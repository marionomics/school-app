import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { RiFireFill, RiFireLine } from "@remixicon/react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { daysToNext, pct } from "@/lib/streak";
import { es } from "@/strings/es";
import type { StreakMe } from "@/lib/types";

export default function StreakChip() {
  const [open, setOpen] = useState(false);
  const q = useQuery({
    queryKey: ["streak"],
    queryFn: () => api<StreakMe>("/api/streak/me"),
  });

  const s = q.data;
  const days = s?.days ?? 0;
  const pending = s != null && !s.today_done;
  const next = s ? daysToNext(s) : null;
  const off = s != null && s.levels.every((l) => l.x2 === 0 && l.x3 === 0);

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        aria-label={es.streak.title}
        className={`flex shrink-0 flex-col items-center whitespace-nowrap rounded-full px-1 py-0.5 leading-none ${
          pending || days === 0 ? "text-muted-foreground" : "text-orange-600"
        }`}
      >
        <span className="inline-flex items-center gap-0.5 text-sm font-semibold">
          {days === 0 ? <RiFireLine className="size-4" /> : <RiFireFill className="size-4" />}
          {q.isPending ? "…" : es.streak.days.replace("{n}", String(days))}
        </span>
        {pending && <span className="mt-0.5 text-[10px]">{es.streak.todayPending}</span>}
      </button>

      {open && (
        <div className="fixed inset-0 z-40 flex items-end bg-black/40" onClick={() => setOpen(false)}>
          <div
            className="max-h-[80dvh] w-full overflow-y-auto rounded-t-2xl bg-background p-5"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="flex items-center gap-2 text-lg font-bold">
              <RiFireFill className="size-5 text-orange-600" />
              {es.streak.title} · {es.streak.days.replace("{n}", String(days))}
            </h2>
            <p className="mt-2 text-sm text-muted-foreground">{es.streak.sheetIntro}</p>
            {s && off && <p className="mt-4 text-sm font-medium">{es.streak.off}</p>}
            {s && !off && (
              <>
                <ul className="mt-4 space-y-2">
                  {s.levels.map((l) => (
                    <li
                      key={l.from_days}
                      className={`rounded-md border p-2 text-sm ${
                        s.level?.from_days === l.from_days ? "border-orange-500 bg-orange-500/10" : ""
                      }`}
                    >
                      <div className="flex justify-between gap-2">
                        <span className="font-semibold">
                          {es.streak.levelFrom.replace("{n}", String(l.from_days))}
                        </span>
                        {s.level?.from_days === l.from_days && (
                          <span className="text-xs font-semibold text-orange-600">{es.streak.current}</span>
                        )}
                      </div>
                      <div className="text-muted-foreground">
                        {es.streak.double.replace("{p}", pct(l.x2))} · {es.streak.triple.replace("{p}", pct(l.x3))}
                      </div>
                    </li>
                  ))}
                </ul>
                <p className="mt-4 text-sm font-medium">
                  {next == null
                    ? es.streak.maxLevel
                    : next === 1
                      ? es.streak.toNextOne
                      : es.streak.toNext.replace("{n}", String(next))}
                </p>
              </>
            )}
            <Button variant="outline" className="mt-5 w-full" onClick={() => setOpen(false)}>
              {es.streak.close}
            </Button>
          </div>
        </div>
      )}
    </>
  );
}
