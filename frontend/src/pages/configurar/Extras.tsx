import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useClassSettings } from "@/hooks/useClassSettings";
import SettingsPage from "@/components/SettingsPage";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useToast } from "@/components/Toaster";
import { formatPoints } from "@/lib/points";
import { es } from "@/strings/es";
import type { Incentive, MemberOut } from "@/lib/types";

export default function Extras() {
  const qc = useQueryClient();
  const toast = useToast();
  const { klass, isPending } = useClassSettings();
  const classId = klass?.id;
  const key = ["class-incentives", classId];

  const q = useQuery({
    queryKey: key,
    queryFn: () =>
      api<{ incentives: Incentive[] }>(`/api/classes/${classId}/incentives`),
    select: (d) => d.incentives,
    enabled: classId != null,
  });

  const members = useQuery({
    queryKey: ["class-members", classId],
    queryFn: () => api<{ members: MemberOut[] }>(`/api/classes/${classId}`),
    select: (d) => d.members.filter((m) => m.status === "active"),
    enabled: classId != null,
  });

  const [name, setName] = useState("");
  const [points, setPoints] = useState("");
  const [deleting, setDeleting] = useState<Incentive | null>(null);
  const [awarding, setAwarding] = useState<Incentive | null>(null);
  const [studentId, setStudentId] = useState<number | "">("");

  const create = useMutation({
    mutationFn: (body: { name: string; points: number }) =>
      api<Incentive>(`/api/classes/${classId}/incentives`, {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: key });
      setName("");
      setPoints("");
    },
    onError: () => toast.show(es.configurar.incentiveCreateError),
  });

  const del = useMutation({
    mutationFn: (id: number) =>
      api<void>(`/api/incentives/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: key });
      setDeleting(null);
    },
    onError: () => toast.show(es.configurar.saveError),
  });

  const award = useMutation({
    mutationFn: (body: { incentiveId: number; studentId: number }) =>
      api<unknown>(`/api/incentives/${body.incentiveId}/award`, {
        method: "POST",
        body: JSON.stringify({ student_id: body.studentId }),
      }),
    onSuccess: () => {
      toast.show(es.configurar.incentiveAwarded);
      void qc.invalidateQueries({ queryKey: ["grade"] });
      setAwarding(null);
      setStudentId("");
    },
    onError: () => toast.show(es.configurar.saveError),
  });

  if (isPending || classId == null)
    return (
      <SettingsPage title={es.configurar.groupExtras}>
        <p className="text-muted-foreground">{es.common.loading}</p>
      </SettingsPage>
    );

  const incentives = q.data ?? [];

  return (
    <SettingsPage title={es.configurar.groupExtras}>
      <Card className="p-4">
        <Label htmlFor="inc-name">{es.configurar.incentiveName}</Label>
        <Input
          id="inc-name"
          className="mt-2"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />

        <Label htmlFor="inc-points" className="mt-4 block">
          {es.configurar.incentivePoints}
        </Label>
        <Input
          id="inc-points"
          type="number"
          inputMode="numeric"
          min={0}
          className="mt-2"
          value={points}
          onChange={(e) => setPoints(e.target.value)}
        />
        {/* The units appear as you type. This is the field where confusing a
            décima with a point costs a student half a grade. */}
        {points !== "" && (
          <p className="mt-1 text-xs text-muted-foreground">
            {formatPoints(Number(points))}
          </p>
        )}

        <Button
          className="mt-4 w-full"
          disabled={!name.trim() || points === "" || create.isPending}
          onClick={() =>
            create.mutate({ name: name.trim(), points: Number(points) })
          }
        >
          {es.configurar.incentiveAdd}
        </Button>
      </Card>

      {incentives.length === 0 && (
        <p className="text-sm text-muted-foreground">
          {es.configurar.incentiveNone}
        </p>
      )}

      {/* A name and a number explain themselves — compact rows, not cards. */}
      {incentives.map((inc) => (
        <div
          key={inc.id}
          className="flex items-center justify-between gap-3 border-b py-3"
        >
          <span className="min-w-0">
            <span className="block truncate text-sm font-medium">
              {inc.name}
            </span>
            <span className="block text-xs text-muted-foreground">
              {formatPoints(Number(inc.points))}
            </span>
          </span>
          <span className="flex shrink-0 gap-1">
            <Button variant="ghost" size="sm" onClick={() => setAwarding(inc)}>
              {es.configurar.incentiveAward}
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setDeleting(inc)}>
              {es.configurar.incentiveDelete}
            </Button>
          </span>
        </div>
      ))}

      <Dialog open={deleting != null} onOpenChange={() => setDeleting(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{es.configurar.incentiveDeleteConfirm}</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            {es.configurar.incentiveDeleteBody}
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleting(null)}>
              {es.configurar.cancel}
            </Button>
            <Button
              variant="destructive"
              disabled={del.isPending}
              onClick={() => deleting && del.mutate(deleting.id)}
            >
              {es.configurar.incentiveDelete}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={awarding != null} onOpenChange={() => setAwarding(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{es.configurar.incentiveAwardTitle}</DialogTitle>
          </DialogHeader>
          <p className="text-sm">
            {awarding?.name}
            {awarding && (
              <span className="block text-xs text-muted-foreground">
                {formatPoints(Number(awarding.points))}
              </span>
            )}
          </p>
          <select
            className="mt-2 w-full border bg-transparent px-2 py-2 text-sm"
            value={studentId}
            onChange={(e) => setStudentId(Number(e.target.value))}
          >
            <option value="">{es.configurar.incentivePickStudent}</option>
            {(members.data ?? []).map((m) => (
              <option key={m.id} value={m.id}>
                {m.username ? `@${m.username}` : m.name}
              </option>
            ))}
          </select>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAwarding(null)}>
              {es.configurar.cancel}
            </Button>
            <Button
              disabled={studentId === "" || award.isPending}
              onClick={() =>
                awarding &&
                studentId !== "" &&
                award.mutate({
                  incentiveId: awarding.id,
                  studentId: Number(studentId),
                })
              }
            >
              {es.configurar.incentiveAward}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </SettingsPage>
  );
}
