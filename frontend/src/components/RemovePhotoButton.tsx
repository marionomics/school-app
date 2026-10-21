import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useToast } from "@/components/Toaster";
import { es } from "@/strings/es";

/** The teacher removes a student's uploaded photo, after confirming. */
export default function RemovePhotoButton({
  userId,
  onRemoved,
}: {
  userId: number;
  onRemoved?: () => void;
}) {
  const [confirming, setConfirming] = useState(false);
  const qc = useQueryClient();
  const toast = useToast();

  const removePhoto = useMutation({
    mutationFn: (studentId: number) =>
      api<void>(`/api/users/${studentId}/avatar`, { method: "DELETE" }),
    onSuccess: () => {
      for (const queryKey of [["roster"], ["class-detail"], ["feed"], ["thread"], ["profile"], ["profile-posts"]])
        void qc.invalidateQueries({ queryKey });
      toast.show(es.perfil.photoRemoved);
      onRemoved?.();
    },
    onError: () => toast.show(es.perfil.error),
  });

  return (
    <>
      <Button
        variant="outline"
        className="mt-3 w-full"
        disabled={removePhoto.isPending}
        onClick={() => setConfirming(true)}
      >
        {es.perfil.teacherRemovePhoto}
      </Button>
      <Dialog open={confirming} onOpenChange={(o) => !o && setConfirming(false)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{es.perfil.teacherRemoveConfirmTitle}</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            {es.perfil.teacherRemoveConfirmBody}
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirming(false)}>
              {es.perfil.cancel}
            </Button>
            <Button
              variant="destructive"
              disabled={removePhoto.isPending}
              onClick={() => {
                setConfirming(false);
                removePhoto.mutate(userId);
              }}
            >
              {es.perfil.teacherRemovePhoto}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
