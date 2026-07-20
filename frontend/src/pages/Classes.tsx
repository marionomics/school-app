import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { es } from "@/strings/es";
import type { ClassOut, MyClasses, ScheduleBlock } from "@/lib/types";

const EMPTY_BLOCK: ScheduleBlock = { day: 0, start: "10:00", end: "11:00" };

function ClassCard({ klass }: { klass: ClassOut }) {
  const [copied, setCopied] = useState(false);

  async function copyLink() {
    await navigator.clipboard.writeText(`${window.location.origin}/join/${klass.code}`);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div className="flex flex-col gap-2 rounded-lg border p-4">
      <div className="flex items-center justify-between">
        <span className="font-semibold">{klass.name}</span>
        <code className="rounded bg-muted px-2 py-0.5 text-sm">{klass.code}</code>
      </div>
      <p className="text-sm text-muted-foreground">
        {klass.start_date} → {klass.end_date}
      </p>
      <button onClick={copyLink} className="self-start text-sm text-primary underline">
        {copied ? es.classes.linkCopied : es.classes.copyLink}
      </button>
    </div>
  );
}

export default function Classes() {
  const { user } = useAuth();
  const [mine, setMine] = useState<MyClasses | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [showJoin, setShowJoin] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [prefix, setPrefix] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [schedule, setSchedule] = useState<ScheduleBlock[]>([EMPTY_BLOCK]);
  const [joinCode, setJoinCode] = useState("");

  const load = useCallback(async () => {
    setMine(await api<MyClasses>("/api/classes/mine"));
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function createClass(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await api("/api/classes", {
        method: "POST",
        body: JSON.stringify({
          name,
          code_prefix: prefix || "CLASE",
          start_date: startDate,
          end_date: endDate,
          schedule,
        }),
      });
      setShowCreate(false);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    }
  }

  async function joinClass(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await api("/api/classes/join", {
        method: "POST",
        body: JSON.stringify({ code: joinCode }),
      });
      setShowJoin(false);
      setJoinCode("");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    }
  }

  function updateBlock(i: number, patch: Partial<ScheduleBlock>) {
    setSchedule((blocks) => blocks.map((b, j) => (j === i ? { ...b, ...patch } : b)));
  }

  if (!mine) return <div className="p-6 text-muted-foreground">{es.common.loading}</div>;

  const isTeacher = user?.role === "teacher";
  const empty = mine.teaching.length === 0 && mine.enrolled.length === 0;

  return (
    <div className="mx-auto flex max-w-md flex-col gap-4 p-4">
      <h1 className="text-xl font-bold">{es.classes.title}</h1>

      <div className="flex gap-2">
        {isTeacher && (
          <button onClick={() => setShowCreate(!showCreate)} className="rounded-md bg-primary px-3 py-2 text-sm text-primary-foreground">
            {es.classes.create}
          </button>
        )}
        <button onClick={() => setShowJoin(!showJoin)} className="rounded-md border px-3 py-2 text-sm">
          {es.classes.join}
        </button>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {showJoin && (
        <form onSubmit={joinClass} className="flex gap-2">
          <input
            className="flex-1 rounded-md border px-3 py-2"
            placeholder={es.classes.codeLabel}
            value={joinCode}
            onChange={(e) => setJoinCode(e.target.value.toUpperCase())}
          />
          <button className="rounded-md bg-primary px-3 py-2 text-primary-foreground">
            {es.classes.joinSubmit}
          </button>
        </form>
      )}

      {showCreate && (
        <form onSubmit={createClass} className="flex flex-col gap-2 rounded-lg border p-4">
          <input className="rounded-md border px-3 py-2" placeholder={es.classes.name} value={name} onChange={(e) => setName(e.target.value)} required />
          <input className="rounded-md border px-3 py-2" placeholder={es.classes.prefix} value={prefix} onChange={(e) => setPrefix(e.target.value.toUpperCase())} />
          <label className="text-sm">
            {es.classes.startDate}
            <input type="date" className="w-full rounded-md border px-3 py-2" value={startDate} onChange={(e) => setStartDate(e.target.value)} required />
          </label>
          <label className="text-sm">
            {es.classes.endDate}
            <input type="date" className="w-full rounded-md border px-3 py-2" value={endDate} onChange={(e) => setEndDate(e.target.value)} required />
          </label>
          <span className="text-sm font-medium">{es.classes.schedule}</span>
          {schedule.map((block, i) => (
            <div key={i} className="flex items-center gap-2">
              <select className="rounded-md border px-2 py-2" value={block.day} onChange={(e) => updateBlock(i, { day: Number(e.target.value) })}>
                {es.classes.days.map((d, di) => (
                  <option key={di} value={di}>{d}</option>
                ))}
              </select>
              <input type="time" className="rounded-md border px-2 py-2" value={block.start} onChange={(e) => updateBlock(i, { start: e.target.value })} />
              <input type="time" className="rounded-md border px-2 py-2" value={block.end} onChange={(e) => updateBlock(i, { end: e.target.value })} />
            </div>
          ))}
          <button type="button" onClick={() => setSchedule((s) => [...s, EMPTY_BLOCK])} className="self-start text-sm text-primary underline">
            {es.classes.addBlock}
          </button>
          <button type="submit" className="rounded-md bg-primary px-3 py-2 text-primary-foreground">
            {es.classes.createSubmit}
          </button>
        </form>
      )}

      {empty && <p className="text-muted-foreground">{es.classes.empty}</p>}

      {mine.teaching.length > 0 && (
        <>
          <h2 className="font-semibold">{es.classes.teaching}</h2>
          {mine.teaching.map((k) => <ClassCard key={k.id} klass={k} />)}
        </>
      )}
      {mine.enrolled.length > 0 && (
        <>
          <h2 className="font-semibold">{es.classes.enrolled}</h2>
          {mine.enrolled.map((k) => <ClassCard key={k.id} klass={k} />)}
        </>
      )}
    </div>
  );
}
