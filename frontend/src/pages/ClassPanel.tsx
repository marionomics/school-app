import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { es } from "@/strings/es";
import type {
  ClassDetailWithMembers,
  RosterStudent,
  SessionOut,
  StudentGradeView,
} from "@/lib/types";

type Tab = "roster" | "calificaciones";

export default function ClassPanel() {
  const { id } = useParams<{ id: string }>();
  const classId = Number(id);
  const { user } = useAuth();
  const isTeacher = user?.role === "teacher";
  const [tab, setTab] = useState<Tab>("roster");
  const [selectedStudentId, setSelectedStudentId] = useState<number | null>(null);
  const qc = useQueryClient();
  const navigate = useNavigate();

  const detail = useQuery({
    queryKey: ["class-detail", classId],
    queryFn: () => api<ClassDetailWithMembers>(`/api/classes/${classId}`),
    enabled: !isNaN(classId),
  });

  const activeSession = useQuery({
    queryKey: ["session-active", classId],
    queryFn: () => api<SessionOut | null>(`/api/classes/${classId}/sessions/active`),
    enabled: isTeacher && !isNaN(classId),
  });

  const roster = useQuery({
    queryKey: ["roster", classId],
    queryFn: () =>
      api<{ students: RosterStudent[] }>(`/api/classes/${classId}/roster`),
    enabled: isTeacher && tab === "calificaciones" && !isNaN(classId),
    select: (d) => d.students,
  });

  const studentGrade = useQuery({
    queryKey: ["student-grade", classId, selectedStudentId],
    queryFn: () =>
      api<StudentGradeView>(
        `/api/classes/${classId}/students/${selectedStudentId}/grade`,
      ),
    enabled: selectedStudentId !== null,
  });

  const openSession = useMutation({
    mutationFn: () =>
      api<SessionOut>(`/api/classes/${classId}/sessions`, { method: "POST" }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["session-active", classId] });
    },
    onError: () => alert(es.panel.openSessionError),
  });

  const closeSession = useMutation({
    mutationFn: (sessionId: number) =>
      api<void>(`/api/classes/${classId}/sessions/${sessionId}`, {
        method: "DELETE",
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["session-active", classId] });
    },
    onError: () => alert(es.panel.closeSessionError),
  });

  const klass = detail.data;
  const session = activeSession.data ?? null;

  return (
    <div className="mx-auto flex max-w-md flex-col gap-4 p-4">
      <button
        onClick={() => navigate("/clases")}
        className="self-start text-sm text-primary underline"
      >
        ← {es.asistencia.back}
      </button>

      <h1 className="text-xl font-bold">
        {klass?.name ?? es.common.loading}
      </h1>

      {isTeacher && (
        <div className="flex items-center justify-between rounded-lg border p-3 text-sm">
          <span>
            {session ? es.panel.sessionOpen : es.panel.noActiveSession}
          </span>
          {session ? (
            <div className="flex gap-2">
              <button
                onClick={() =>
                  navigate(`/pasar-lista/${classId}/${session.id}`)
                }
                className="rounded-md bg-primary px-3 py-1 text-xs text-primary-foreground"
              >
                {es.panel.tomarLista}
              </button>
              <button
                onClick={() => closeSession.mutate(session.id)}
                disabled={closeSession.isPending}
                className="rounded-md border px-3 py-1 text-xs"
              >
                {es.panel.closeSession}
              </button>
            </div>
          ) : (
            <button
              onClick={() => openSession.mutate()}
              disabled={openSession.isPending}
              className="rounded-md bg-primary px-3 py-1 text-xs text-primary-foreground"
            >
              {es.panel.openSession}
            </button>
          )}
        </div>
      )}

      {isTeacher && (
        <div className="flex gap-2">
          {(["roster", "calificaciones"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`rounded-full px-3 py-1 text-sm ${
                tab === t ? "bg-primary text-primary-foreground" : "border"
              }`}
            >
              {t === "roster" ? es.panel.tabRoster : es.panel.tabCalificaciones}
            </button>
          ))}
        </div>
      )}

      {tab === "roster" && (
        <ul className="divide-y rounded-lg border">
          {detail.isPending && (
            <li className="px-4 py-3 text-sm text-muted-foreground">
              {es.panel.loadingRoster}
            </li>
          )}
          {detail.isError && (
            <li className="px-4 py-3 text-sm text-destructive">
              {es.panel.errorRoster}
            </li>
          )}
          {!detail.isPending &&
            (detail.data?.members ?? []).length === 0 && (
              <li className="px-4 py-3 text-sm text-muted-foreground">
                {es.panel.rosterEmpty}
              </li>
            )}
          {(detail.data?.members ?? []).map((m) => (
            <li key={m.id} className="flex items-center gap-3 px-4 py-3">
              {m.status === "ghost" && (
                <span>{es.panel.statusGhost}</span>
              )}
              {m.status === "polizon" && (
                <span>{es.panel.statusPolizon}</span>
              )}
              <span className="font-medium">{m.name}</span>
              {m.username && (
                <span className="text-sm text-muted-foreground">
                  @{m.username}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}

      {tab === "calificaciones" && isTeacher && (
        <ul className="divide-y rounded-lg border">
          {roster.isPending && (
            <li className="px-4 py-3 text-sm text-muted-foreground">
              {es.panel.loadingCalif}
            </li>
          )}
          {roster.isError && (
            <li className="px-4 py-3 text-sm text-destructive">
              {es.panel.errorCalif}
            </li>
          )}
          {(roster.data ?? []).map((s) => (
            <li
              key={s.id}
              onClick={() => setSelectedStudentId(s.id)}
              className="flex cursor-pointer items-center justify-between px-4 py-3 hover:bg-accent"
            >
              <div className="flex items-center gap-2">
                {s.status === "ghost" && (
                  <span>{es.panel.statusGhost}</span>
                )}
                {s.status === "polizon" && (
                  <span>{es.panel.statusPolizon}</span>
                )}
                <span className="font-medium">{s.name}</span>
              </div>
              <div className="flex flex-col items-end text-sm">
                <span className="font-semibold text-primary">
                  {s.grade} {es.grade.points}
                </span>
                {s.faltas > 0 && (
                  <span className="text-xs text-destructive">
                    {s.faltas} {es.panel.faltas}
                  </span>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}

      {selectedStudentId !== null && (
        <div
          className="fixed inset-0 z-40 flex items-end bg-black/40"
          onClick={() => setSelectedStudentId(null)}
        >
          <div
            className="max-h-[80dvh] w-full overflow-y-auto rounded-t-2xl bg-background p-5"
            onClick={(e) => e.stopPropagation()}
          >
            {studentGrade.isPending && (
              <p className="text-muted-foreground">{es.common.loading}</p>
            )}
            {studentGrade.data && (
              <>
                <h2 className="text-lg font-bold">
                  {roster.data?.find((s) => s.id === selectedStudentId)?.name}
                </h2>
                <div className="mt-3 text-3xl font-bold text-primary">
                  {studentGrade.data.total} {es.grade.points}
                </div>
                <dl className="mt-3 space-y-2 text-sm">
                  <div className="flex justify-between">
                    <dt>📌 {es.grade.tareas}</dt>
                    <dd>
                      {studentGrade.data.tareas.evaluated
                        ? `${studentGrade.data.tareas.points} / ${studentGrade.data.tareas.weight}`
                        : es.grade.notEvaluated}
                    </dd>
                  </div>
                  <div className="flex justify-between">
                    <dt>📝 {es.grade.examenes}</dt>
                    <dd>
                      {studentGrade.data.examenes.evaluated
                        ? `${studentGrade.data.examenes.points} / ${studentGrade.data.examenes.weight}`
                        : es.grade.notEvaluated}
                    </dd>
                  </div>
                  <div className="flex justify-between">
                    <dt>🗣️ {es.grade.participaciones}</dt>
                    <dd>{studentGrade.data.ledger.participaciones}</dd>
                  </div>
                  {studentGrade.data.faltas.count > 0 && (
                    <div className="flex justify-between text-destructive">
                      <dt>🚫 {es.grade.faltas}</dt>
                      <dd>−{studentGrade.data.faltas.points}</dd>
                    </div>
                  )}
                </dl>
              </>
            )}
            <button
              onClick={() => setSelectedStudentId(null)}
              className="mt-5 w-full rounded-md border py-2 text-sm"
            >
              {es.grade.close}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
