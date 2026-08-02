import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Navigate } from "react-router-dom";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useToast } from "@/components/Toaster";
import { es } from "@/strings/es";
import type { ClassSettings, Incentive, MyClasses } from "@/lib/types";

export default function Configurar() {
  const { user } = useAuth();
  const [classId, setClassId] = useState<number | null>(null);

  const mine = useQuery({
    queryKey: ["classes-mine"],
    queryFn: () => api<MyClasses>("/api/classes/mine"),
  });
  const teaching = mine.data?.teaching ?? [];
  const activeClass = classId ?? teaching[0]?.id ?? null;

  // The guard has to sit below every hook: returning above them changes the
  // hook order between renders once `user` resolves, which React treats as a
  // fatal error rather than a warning.
  if (user?.role !== "teacher") return <Navigate to="/" replace />;

  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-6 p-4">
      <h1 className="text-lg font-bold">{es.configurar.title}</h1>

      {teaching.length === 0 && (
        <p className="text-muted-foreground">{es.configurar.empty}</p>
      )}

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

      {activeClass != null && (
        <>
          <SettingsSection classId={activeClass} />
          <IncentivesSection classId={activeClass} />
        </>
      )}
    </main>
  );
}

function SettingsSection({ classId }: { classId: number }) {
  const toast = useToast();
  const qc = useQueryClient();
  const [form, setForm] = useState<Partial<ClassSettings>>({});

  const q = useQuery({
    queryKey: ["class-settings", classId],
    queryFn: () => api<ClassSettings>(`/api/classes/${classId}/settings`),
  });

  const save = useMutation({
    mutationFn: (patch: Partial<ClassSettings>) =>
      api<ClassSettings>(`/api/classes/${classId}/settings`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(patch),
      }),
    onSuccess: (data) => {
      qc.setQueryData(["class-settings", classId], data);
      setForm({});
      toast.show(es.configurar.settingsSaved);
    },
    onError: () => toast.show(es.configurar.settingsError),
  });

  if (q.isPending)
    return <p className="text-muted-foreground">{es.common.loading}</p>;
  if (!q.data) return null;

  const current = q.data;

  function field(key: keyof ClassSettings, label: string, step = "1") {
    const val = form[key] !== undefined ? form[key] : current[key];
    return (
      <label key={key} className="flex flex-col gap-1 text-sm">
        <span>{label}</span>
        <input
          type="number"
          step={step}
          inputMode="numeric"
          value={String(val)}
          onChange={(e) =>
            setForm((f) => ({ ...f, [key]: Number(e.target.value) }))
          }
          className="rounded-md border px-2 py-1"
        />
      </label>
    );
  }

  return (
    <section className="flex flex-col gap-4 rounded-lg border p-4">
      <h2 className="font-semibold">{es.configurar.sectionWeights}</h2>
      <div className="grid grid-cols-2 gap-3">
        {field("tareas_weight", es.configurar.tareasWeightLabel)}
        {field("examenes_weight", es.configurar.examenesWeightLabel)}
        {field("tap_value", es.configurar.tapValueLabel, "0.01")}
        {field("like_value", es.configurar.likeValueLabel, "0.01")}
        {field("like_exponent", es.configurar.likeExponentLabel, "0.01")}
      </div>
      <button
        onClick={() => save.mutate(form)}
        disabled={save.isPending || Object.keys(form).length === 0}
        className="self-end rounded-md bg-primary px-4 py-2 text-sm text-primary-foreground disabled:opacity-50"
      >
        {es.configurar.saveSettings}
      </button>
    </section>
  );
}

interface Member {
  id: number;
  name: string;
  username: string | null;
  status: string;
}

function IncentivesSection({ classId }: { classId: number }) {
  const toast = useToast();
  const qc = useQueryClient();
  const key = ["class-incentives", classId];

  const q = useQuery({
    queryKey: key,
    queryFn: () =>
      api<{ incentives: Incentive[] }>(`/api/classes/${classId}/incentives`),
    select: (d) => d.incentives,
  });

  const members = useQuery({
    queryKey: ["class-members", classId],
    queryFn: () => api<{ members: Member[] }>(`/api/classes/${classId}`),
    select: (d) => d.members.filter((m) => m.status === "active"),
  });

  const [newName, setNewName] = useState("");
  const [newPoints, setNewPoints] = useState<number>(5);
  const [deleteId, setDeleteId] = useState<number | null>(null);
  const [awardId, setAwardId] = useState<number | null>(null);
  const [awardStudentId, setAwardStudentId] = useState<number | "">("");

  const create = useMutation({
    mutationFn: (body: { name: string; points: number }) =>
      api<Incentive>(`/api/classes/${classId}/incentives`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: key });
      setNewName("");
      setNewPoints(5);
    },
    onError: () => toast.show(es.configurar.createError),
  });

  const del = useMutation({
    mutationFn: (id: number) =>
      api<void>(`/api/incentives/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: key });
      setDeleteId(null);
    },
    onError: () => toast.show(es.configurar.settingsError),
  });

  const award = useMutation({
    mutationFn: ({
      incentiveId,
      studentId,
    }: {
      incentiveId: number;
      studentId: number;
    }) =>
      api<unknown>(`/api/incentives/${incentiveId}/award`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ student_id: studentId }),
      }),
    onSuccess: () => {
      toast.show(es.configurar.otorgarSuccess);
      void qc.invalidateQueries({ queryKey: ["grade"] });
      setAwardId(null);
      setAwardStudentId("");
    },
    onError: () => toast.show(es.configurar.otorgarError),
  });

  const incentives = q.data ?? [];

  return (
    <section className="flex flex-col gap-4 rounded-lg border p-4">
      <h2 className="font-semibold">{es.configurar.sectionIncentivos}</h2>

      <div className="flex gap-2">
        <input
          placeholder={es.configurar.incentiveNameLabel}
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          className="flex-1 rounded-md border px-2 py-1 text-sm"
        />
        <input
          type="number"
          inputMode="numeric"
          placeholder={es.configurar.incentivePointsLabel}
          value={newPoints}
          onChange={(e) => setNewPoints(Number(e.target.value))}
          className="w-20 rounded-md border px-2 py-1 text-sm"
        />
        <button
          onClick={() => create.mutate({ name: newName, points: newPoints })}
          disabled={!newName.trim() || newPoints <= 0 || create.isPending}
          className="rounded-md bg-primary px-3 py-1 text-sm text-primary-foreground disabled:opacity-50"
        >
          {es.configurar.addIncentive}
        </button>
      </div>

      {incentives.length === 0 && (
        <p className="text-sm text-muted-foreground">
          {es.configurar.noIncentives}
        </p>
      )}

      <ul className="divide-y rounded-lg border">
        {incentives.map((inc) => (
          <li
            key={inc.id}
            className="flex items-center justify-between gap-2 px-3 py-3"
          >
            <div>
              <span className="font-medium">{inc.name}</span>
              <span className="ml-2 text-sm text-muted-foreground">
                +{inc.points} pts
              </span>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => {
                  setAwardId(inc.id);
                  setAwardStudentId("");
                }}
                className="rounded-md border px-2 py-1 text-xs"
              >
                {es.configurar.otorgar}
              </button>
              <button
                onClick={() => setDeleteId(inc.id)}
                className="rounded-md border border-destructive px-2 py-1 text-xs text-destructive"
              >
                {es.configurar.deleteIncentive}
              </button>
            </div>
          </li>
        ))}
      </ul>

      {deleteId != null && (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/40">
          <div className="w-80 rounded-xl bg-background p-5">
            <p className="font-semibold">{es.configurar.deleteConfirm}</p>
            <p className="mt-1 text-sm text-muted-foreground">
              {es.configurar.deleteConfirmBody}
            </p>
            <div className="mt-4 flex justify-end gap-2">
              <button
                onClick={() => setDeleteId(null)}
                className="rounded-md border px-3 py-1 text-sm"
              >
                {es.configurar.cancel}
              </button>
              <button
                onClick={() => del.mutate(deleteId)}
                disabled={del.isPending}
                className="rounded-md bg-destructive px-3 py-1 text-sm text-destructive-foreground"
              >
                {es.configurar.deleteConfirmYes}
              </button>
            </div>
          </div>
        </div>
      )}

      {awardId != null && (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/40">
          <div className="w-80 rounded-xl bg-background p-5">
            <p className="font-semibold">{es.configurar.otorgarTitle}</p>
            <select
              className="mt-3 w-full rounded-md border px-2 py-1 text-sm"
              value={awardStudentId}
              onChange={(e) => setAwardStudentId(Number(e.target.value))}
            >
              <option value="">{es.configurar.pickStudent}</option>
              {(members.data ?? []).map((m) => (
                <option key={m.id} value={m.id}>
                  @{m.username ?? m.name}
                </option>
              ))}
            </select>
            <div className="mt-4 flex justify-end gap-2">
              <button
                onClick={() => setAwardId(null)}
                className="rounded-md border px-3 py-1 text-sm"
              >
                {es.configurar.cancel}
              </button>
              <button
                onClick={() => {
                  if (awardStudentId !== "")
                    award.mutate({
                      incentiveId: awardId,
                      studentId: Number(awardStudentId),
                    });
                }}
                disabled={awardStudentId === "" || award.isPending}
                className="rounded-md bg-primary px-3 py-1 text-sm text-primary-foreground disabled:opacity-50"
              >
                {es.configurar.otorgarConfirm}
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
