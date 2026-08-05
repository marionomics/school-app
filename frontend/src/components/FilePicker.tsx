import { useRef } from "react";
import { RiAttachment2 } from "@remixicon/react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { capFiles } from "@/lib/attachments";
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
          onChange(capFiles(e.target.files));
          // Reset so re-picking the same file still fires a change event.
          e.target.value = "";
        }}
      />
      <Button
        type="button"
        variant="outline"
        size={compact ? "icon-sm" : "sm"}
        onClick={() => input.current?.click()}
        aria-label={es.attachments.attach}
      >
        <RiAttachment2 />
        {!compact && es.attachments.attach}
        {compact && files.length > 0 && (
          <span className="sr-only">
            {es.attachments.chosen.replace("{n}", String(files.length))}
          </span>
        )}
      </Button>
    </>
  );
}

export function FileChips({
  files,
  className,
}: {
  files: File[];
  className?: string;
}) {
  if (files.length === 0) return null;
  return (
    <div className={cn("flex flex-wrap gap-2", className)}>
      {files.map((f) => (
        <span
          key={f.name}
          className="inline-flex items-center gap-1 border px-2 py-1 text-xs text-muted-foreground"
        >
          <RiAttachment2 className="size-3" /> {f.name}
        </span>
      ))}
    </div>
  );
}
