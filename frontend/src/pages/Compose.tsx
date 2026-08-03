import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useTapWindow } from "@/hooks/useTapWindow";
import { useToast } from "@/components/Toaster";
import { RiAttachment2 } from "@remixicon/react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { es } from "@/strings/es";
import type { MyClasses, Post } from "@/lib/types";

const MIN_PARTICIPACION_CHARS = 10;

export default function Compose() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const toast = useToast();
  const [mode, setMode] = useState<"regular" | "participacion" | "tarea" | "examen">("regular");
  const [examenMode, setExamenMode] = useState<"paper" | "digital">("paper");
  const [dueDate, setDueDate] = useState<string>("");
  const [content, setContent] = useState("");
  const [classId, setClassId] = useState<number | null>(null);
  const [files, setFiles] = useState<File[]>([]);
  const fileInput = useRef<HTMLInputElement>(null);

  const config = useQuery({
    queryKey: ["config"],
    queryFn: () => api<{ file_uploads_enabled: boolean }>("/api/config"),
  });
  const mine = useQuery({
    queryKey: ["classes-mine"],
    queryFn: () => api<MyClasses>("/api/classes/mine"),
  });
  const defaultClass = useQuery({
    queryKey: ["default-class"],
    queryFn: () => api<{ class_id: number | null }>("/api/posts/default-class"),
  });

  useEffect(() => {
    if (classId === null && defaultClass.data?.class_id != null) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- one-time init of local state from a fetched default, not a cascading-render risk
      setClassId(defaultClass.data.class_id);
    }
  }, [defaultClass.data, classId]);

  const publish = useMutation({
    mutationFn: (taps: number | null) => {
      const fd = new FormData();
      fd.set("content", content);
      fd.set("type", mode === "participacion" ? "participacion" : mode);
      if (taps) fd.set("taps", String(taps));
      if (mode === "tarea" && dueDate) {
        fd.set("due_date", new Date(dueDate).toISOString());
      }
      if (mode === "examen") fd.set("examen_mode", examenMode);
      if (classId != null) fd.set("class_id", String(classId));
      for (const f of files) fd.append("files", f);
      return api<Post>("/api/posts", { method: "POST", body: fd });
    },
    onSuccess: (_post, taps) => {
      void qc.invalidateQueries({ queryKey: ["feed"] });
      void qc.invalidateQueries({ queryKey: ["grade"] });
      if (taps) toast.show(es.compose.published.replace("{n}", String(taps)));
      navigate("/", { replace: true });
    },
    onError: () => {
      tapCtl.cancel();
      toast.show(es.compose.error);
    },
  });

  const tapCtl = useTapWindow((taps) => publish.mutate(taps));

  const isStudent = user?.role !== "teacher";
  const enrolled = mine.data?.enrolled ?? [];
  const teaching = mine.data?.teaching ?? [];
  // A teacher picks among the classes they teach; a student among enrollments.
  const pickable = isStudent ? enrolled : teaching;
  const needsClass = (mode === "tarea" || mode === "examen") && classId == null;
  const contentOk = content.trim().length >= MIN_PARTICIPACION_CHARS;
  const ringPct = tapCtl.active ? (tapCtl.msLeft / tapCtl.windowMs) * 100 : 0;

  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col gap-4 p-4">
      <div className="flex items-center justify-between">
        <button onClick={() => navigate(-1)} aria-label={es.post.cancel}>×</button>
        <h1 className="font-bold">{es.compose.title}</h1>
        {mode !== "participacion" ? (
          <button
            disabled={(!content.trim() && files.length === 0) || needsClass || publish.isPending}
            onClick={() => publish.mutate(null)}
            className="rounded-full bg-primary px-4 py-1.5 text-sm text-primary-foreground disabled:opacity-50"
          >
            {publish.isPending ? es.compose.publishing : es.compose.publish}
          </button>
        ) : (
          <span className="w-16" />
        )}
      </div>

      {isStudent && (
        <div className="flex gap-2">
          {(["regular", "participacion"] as const).map((m) => (
            <button
              key={m}
              onClick={() => {
                setMode(m);
                if (m === "participacion") setFiles([]);
              }}
              className={`rounded-full px-3 py-1 text-sm ${mode === m ? "bg-primary text-primary-foreground" : "border"}`}
            >
              {m === "regular" ? es.compose.modeRegular : es.compose.modeParticipacion}
            </button>
          ))}
        </div>
      )}

      {!isStudent && (
        <div className="flex gap-2">
          {(["regular", "tarea", "examen"] as const).map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={`rounded-full px-3 py-1 text-sm ${mode === m ? "bg-primary text-primary-foreground" : "border"}`}
            >
              {m === "regular"
                ? es.compose.modeRegular
                : m === "tarea"
                  ? es.compose.modeTarea
                  : es.compose.modeExamen}
            </button>
          ))}
        </div>
      )}

      {mode === "examen" && (
        <div>
          <Label htmlFor="examen-mode">{es.compose.examenModeLabel}</Label>
          <select
            id="examen-mode"
            className="mt-2 w-full border bg-transparent px-2 py-2 text-sm"
            value={examenMode}
            onChange={(e) =>
              setExamenMode(e.target.value as "paper" | "digital")
            }
          >
            <option value="paper">{es.compose.examenPaper}</option>
            <option value="digital">{es.compose.examenDigital}</option>
          </select>
        </div>
      )}

      {mode === "tarea" && (
        <div>
          <Label htmlFor="due-date">{es.compose.dueLabel}</Label>
          <Input
            id="due-date"
            type="datetime-local"
            className="mt-2"
            value={dueDate}
            onChange={(e) => setDueDate(e.target.value)}
          />
          <p className="mt-1 text-xs text-muted-foreground">
            {es.compose.dueHint}
          </p>
        </div>
      )}

      {(pickable.length > 1 || needsClass) && pickable.length > 0 && (
        <div>
          <Label htmlFor="class-picker">{es.compose.classLabel}</Label>
          <select
            id="class-picker"
            className="mt-2 w-full border bg-transparent px-2 py-2 text-sm"
            value={classId ?? ""}
            onChange={(e) => setClassId(Number(e.target.value))}
          >
            <option value="" disabled>—</option>
            {pickable.map((k) => (
              <option key={k.id} value={k.id}>{k.name}</option>
            ))}
          </select>
        </div>
      )}

      <textarea
        autoFocus
        className="min-h-40 w-full resize-none rounded-lg border p-3"
        placeholder={
          mode === "participacion"
            ? es.compose.participacionPlaceholder
            : mode === "tarea"
              ? es.compose.tareaPlaceholder
              : mode === "examen"
                ? es.compose.examenPlaceholder
                : es.compose.placeholder
        }
        value={content}
        onChange={(e) => setContent(e.target.value)}
      />

      {config.data?.file_uploads_enabled && mode === "regular" && (
        <div>
          <input
            ref={fileInput}
            type="file"
            multiple
            hidden
            onChange={(e) => setFiles(Array.from(e.target.files ?? []).slice(0, 4))}
          />
          <button onClick={() => fileInput.current?.click()} className="rounded-md border px-3 py-1.5 text-sm">
            <RiAttachment2 className="size-4" /> {es.compose.attach}
          </button>
          {files.map((f) => (
            <span key={f.name} className="ml-2 text-xs text-muted-foreground">{f.name}</span>
          ))}
        </div>
      )}

      {mode === "participacion" && (
        <div className="mt-4 flex flex-col items-center gap-3">
          <p className="text-sm text-muted-foreground">
            {contentOk ? es.compose.participacionHint : es.compose.tooShort}
          </p>
          <button
            disabled={!contentOk || publish.isPending}
            onClick={tapCtl.tap}
            aria-label={es.compose.tapToRegister}
            className="relative flex h-36 w-36 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-lg transition-transform active:scale-90 disabled:opacity-40"
            style={
              tapCtl.active
                ? { background: `conic-gradient(var(--primary) ${100 - ringPct}%, color-mix(in srgb, var(--primary) 45%, transparent) 0)` }
                : undefined
            }
          >
            <span className="text-3xl font-bold">
              {tapCtl.count === 0 ? "👏" : `×${tapCtl.count}`}
            </span>
          </button>
          <p className="h-6 text-lg font-semibold">
            {tapCtl.count === 2 && es.compose.double}
            {tapCtl.count === 3 && es.compose.triple}
          </p>
          {tapCtl.active && (
            <button onClick={tapCtl.cancel} className="text-sm text-muted-foreground underline">
              {es.compose.cancelTap}
            </button>
          )}
          {publish.isPending && <p className="text-sm">{es.compose.publishing}</p>}
        </div>
      )}
    </main>
  );
}
