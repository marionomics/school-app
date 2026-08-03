import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { RiArrowLeftSLine } from "@remixicon/react";
import { Button } from "@/components/ui/button";
import { es } from "@/strings/es";
import type { ClassDetailWithMembers, MemberOut } from "@/lib/types";

type Status = "present" | "absent" | "late";

export default function PasarLista() {
  const { class_id, session_id } = useParams<{
    class_id: string;
    session_id: string;
  }>();
  const classId = Number(class_id);
  const sessionId = Number(session_id);
  const navigate = useNavigate();

  const detail = useQuery({
    queryKey: ["class-detail", classId],
    queryFn: () => api<ClassDetailWithMembers>(`/api/classes/${classId}`),
    enabled: !isNaN(classId),
  });

  const activeMembers: MemberOut[] = (detail.data?.members ?? []).filter(
    (m) => m.status === "active",
  );

  const [statuses, setStatuses] = useState<Record<number, Status>>({});

  function getStatus(userId: number): Status {
    return statuses[userId] ?? "present";
  }

  function cycle(userId: number) {
    const current = getStatus(userId);
    const next: Status =
      current === "present" ? "absent" : current === "absent" ? "late" : "present";
    setStatuses((s) => ({ ...s, [userId]: next }));
  }

  const save = useMutation({
    mutationFn: () => {
      const records = activeMembers.map((m) => ({
        user_id: m.id,
        status: getStatus(m.id),
      }));
      return api<{ saved: number }>(`/api/sessions/${sessionId}/attendance`, {
        method: "PUT",
        body: JSON.stringify({ records }),
      });
    },
    onSuccess: () => {
      navigate(-1);
    },
    onError: () => alert(es.asistencia.saveError),
  });

  function labelFor(s: Status): string {
    if (s === "present") return es.asistencia.statusPresent;
    if (s === "absent") return es.asistencia.statusAbsent;
    return es.asistencia.statusLate;
  }

  function colorFor(s: Status): string {
    if (s === "present") return "bg-green-100 text-green-800";
    if (s === "absent") return "bg-red-100 text-red-800";
    return "bg-yellow-100 text-yellow-800";
  }

  return (
    <div className="flex min-h-dvh flex-col">
      <header className="sticky top-0 z-10 flex items-center justify-between border-b bg-background px-4 py-3">
        <Button variant="ghost" size="sm" onClick={() => navigate(-1)}>
          <RiArrowLeftSLine className="size-4" /> {es.asistencia.back}
        </Button>
        <h1 className="text-xs font-semibold tracking-widest uppercase">
          {es.asistencia.title}
        </h1>
        <Button
          size="sm"
          onClick={() => save.mutate()}
          disabled={save.isPending || detail.isPending}
        >
          {save.isPending ? es.asistencia.saving : es.asistencia.saveButton}
        </Button>
      </header>

      <main className="flex-1 overflow-y-auto">
        {detail.isPending && (
          <p className="p-4 text-muted-foreground">{es.common.loading}</p>
        )}
        {activeMembers.length === 0 && !detail.isPending && (
          <p className="p-4 text-muted-foreground">
            {es.asistencia.emptyStudents}
          </p>
        )}
        <ul className="divide-y">
          {activeMembers.map((m) => {
            const status = getStatus(m.id);
            return (
              <li
                key={m.id}
                className="flex items-center justify-between px-4 py-4"
              >
                <div>
                  <p className="font-medium">{m.name}</p>
                  {m.username && (
                    <p className="text-xs text-muted-foreground">
                      @{m.username}
                    </p>
                  )}
                </div>
                {/* One row per student, tap to cycle P -> F -> T. Kept as a
                    paired row on purpose: stacking it would double the
                    scrolling for a full class. */}
                <button
                  onClick={() => cycle(m.id)}
                  className={`min-w-12 px-4 py-3 text-sm font-semibold tracking-widest uppercase ${colorFor(status)}`}
                >
                  {labelFor(status)}
                </button>
              </li>
            );
          })}
        </ul>
      </main>
    </div>
  );
}
