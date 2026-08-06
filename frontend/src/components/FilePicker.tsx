import { useRef } from "react";
import { RiAttachment2, RiCloseLine } from "@remixicon/react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { addFiles } from "@/lib/attachments";
import { useUploadsEnabled } from "@/lib/config";
import { es } from "@/strings/es";

type PickerProps = {
  files: File[];
  onChange: (files: File[]) => void;
  /** Icon-only, for the reply bar where there is no room for a label. */
  compact?: boolean;
};

export function FilePicker({ files, onChange, compact = false }: PickerProps) {
  const enabled = useUploadsEnabled();
  const input = useRef<HTMLInputElement>(null);

  // Spec §5.2: when uploads are off the affordance does not exist at all. A
  // disabled button inviting a student to attach work the server will refuse
  // is worse than no button.
  if (!enabled) return null;

  return (
    <>
      <input
        ref={input}
        type="file"
        multiple
        hidden
        onChange={(e) => {
          onChange(addFiles(files, e.target.files));
          // Reset so re-picking the same file still fires a change event.
          e.target.value = "";
        }}
      />
      <Button
        type="button"
        variant="outline"
        size={compact ? "icon-sm" : "sm"}
        onClick={() => input.current?.click()}
        aria-label={
          compact && files.length > 0
            ? es.attachments.chosen.replace("{n}", String(files.length))
            : es.attachments.attach
        }
      >
        <RiAttachment2 />
        {!compact && es.attachments.attach}
      </Button>
    </>
  );
}

export function FileChips({
  files,
  className,
  onRemove,
}: {
  files: File[];
  className?: string;
  onRemove?: (index: number) => void;
}) {
  if (files.length === 0) return null;
  return (
    <div className={cn("flex flex-wrap gap-2", className)}>
      {files.map((f, i) => (
        <span
          key={`${f.name}-${i}`}
          className="inline-flex items-center gap-1 border px-2 py-1 text-xs text-muted-foreground"
        >
          <RiAttachment2 className="size-3" /> {f.name}
          {onRemove && (
            <Button
              type="button"
              variant="ghost"
              size="icon-xs"
              onClick={() => onRemove(i)}
              aria-label={es.attachments.remove}
            >
              <RiCloseLine />
            </Button>
          )}
        </span>
      ))}
    </div>
  );
}
