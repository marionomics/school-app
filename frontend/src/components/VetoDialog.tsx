import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { es } from "@/strings/es";

/** The one veto confirmation, wherever vetoing starts — /revisar or the feed.
 *  Vetoing cancels the student's points, so it never fires on a single tap
 *  (R8: it once cancelled participaciones Mario meant to validate). */
export default function VetoDialog({
  open,
  onCancel,
  onConfirm,
}: {
  open: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onCancel()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{es.revisar.vetoConfirmTitle}</DialogTitle>
        </DialogHeader>
        <p className="text-sm text-muted-foreground">{es.revisar.vetoConfirmBody}</p>
        <DialogFooter>
          <Button variant="outline" onClick={onCancel}>
            {es.configurar.cancel}
          </Button>
          <Button variant="destructive" onClick={onConfirm}>
            {es.revisar.vetoConfirmYes}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
