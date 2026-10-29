import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { ApiError } from "@/lib/api";
import { setTeamMember } from "@/lib/review";
import { Button } from "@/components/ui/button";
import UserLink from "@/components/UserLink";
import { useToast } from "@/components/Toaster";
import { es } from "@/strings/es";
import type { TeamMember } from "@/lib/types";

/** The team inside the grading sheet. Removing a member is a flag the
 *  teacher can undo — never a different grade (one grade per entrega). */
export default function TeamEditor({
  postId,
  members,
  onChanged,
}: {
  postId: number;
  members: TeamMember[];
  onChanged: () => void;
}) {
  const toast = useToast();
  const [confirming, setConfirming] = useState<number | null>(null);
  const flip = useMutation({
    mutationFn: ({ userId, removed }: { userId: number; removed: boolean }) =>
      setTeamMember(postId, userId, removed),
    onSuccess: () => {
      setConfirming(null);
      onChanged();
    },
    onError: (e) => toast.show(e instanceof ApiError ? e.message : es.mentions.teamError),
  });
  if (members.length === 0) return null;
  return (
    <div className="mt-4 flex flex-col gap-2">
      <p className="text-xs text-muted-foreground">{es.mentions.team}</p>
      {members.map((m) => (
        <div key={m.user.id} className="flex flex-col gap-1">
          {/* A member plus the one thing you can do to them: the list-row
              exception to one control per line. */}
          <div className="flex items-center justify-between gap-3 text-sm">
            <span className={m.removed ? "text-muted-foreground line-through" : ""}>
              <UserLink user={m.user} plain />
            </span>
            {m.removed ? (
              <Button
                variant="outline"
                size="sm"
                disabled={flip.isPending}
                onClick={() => flip.mutate({ userId: m.user.id, removed: false })}
              >
                {es.mentions.restoreToTeam}
              </Button>
            ) : (
              <Button
                variant="outline"
                size="sm"
                disabled={flip.isPending}
                onClick={() => setConfirming(m.user.id)}
              >
                {es.mentions.removeFromTeam}
              </Button>
            )}
          </div>
          {confirming === m.user.id && (
            <div className="flex flex-col gap-2 border p-2 text-xs">
              <p>
                {es.mentions.removeConfirm.replace("{user}", m.user.username ?? m.user.name)}
              </p>
              <Button
                variant="destructive"
                size="sm"
                onClick={() => flip.mutate({ userId: m.user.id, removed: true })}
              >
                {es.mentions.confirm}
              </Button>
              <Button variant="ghost" size="sm" onClick={() => setConfirming(null)}>
                {es.mentions.cancel}
              </Button>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
