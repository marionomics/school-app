import { useState } from "react";
import { RiArrowLeftSLine, RiArrowRightSLine, RiAttachment2 } from "@remixicon/react";
import { api } from "@/lib/api";
import { photoLayout, splitAttachments } from "@/lib/photos";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { es } from "@/strings/es";
import type { Attachment, Author } from "@/lib/types";

/** A photo whose signed link expired (tab open over an hour) asks for a
 *  fresh one once, then gives up quietly. */
function Photo({ att, alt, className }: { att: Attachment; alt: string; className: string }) {
  const [src, setSrc] = useState(att.url ?? "");
  const [retried, setRetried] = useState(false);
  return (
    <img
      src={src}
      alt={alt}
      loading="lazy"
      decoding="async"
      className={className}
      onError={async () => {
        if (retried) return;
        setRetried(true);
        try {
          const { url } = await api<{ url: string }>(`/api/attachments/${att.id}/url`);
          setSrc(url);
        } catch {
          /* leave the grey box */
        }
      }}
    />
  );
}

export default function PostPhotos({
  attachments,
  author,
  onOpenFile,
}: {
  attachments: Attachment[];
  author: Author;
  onOpenFile?: (id: number) => void;
}) {
  const { photos, files } = splitAttachments(attachments);
  const [open, setOpen] = useState<number | null>(null);
  const alt = es.attachments.photoAlt.replace("{user}", author.username ?? author.name);
  const layout = photoLayout(photos.length);

  return (
    <div className="mt-2 flex flex-col gap-2">
      {layout === "single" && (
        <button type="button" onClick={() => setOpen(0)} className="block w-full">
          <div className="aspect-[4/5] w-full bg-muted">
            <Photo att={photos[0]} alt={alt} className="size-full object-contain" />
          </div>
        </button>
      )}
      {layout === "grid" && (
        <div className="grid grid-cols-2 gap-1">
          {photos.map((p, i) => (
            <button key={p.id} type="button" onClick={() => setOpen(i)} className="block">
              <div className="aspect-square bg-muted">
                <Photo att={p} alt={alt} className="size-full object-cover" />
              </div>
            </button>
          ))}
        </div>
      )}
      {files.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {files.map((a) =>
            onOpenFile ? (
              <button
                key={a.id}
                onClick={() => onOpenFile(a.id)}
                className="inline-flex max-w-full items-center gap-1 border px-2 py-1 text-xs"
              >
                <RiAttachment2 className="size-3 shrink-0" />
                <span className="truncate">{a.file_name}</span>
              </button>
            ) : (
              <span key={a.id} className="inline-flex items-center gap-1 border px-2 py-1 text-xs">
                <RiAttachment2 className="size-3" /> {a.file_name}
              </span>
            ),
          )}
        </div>
      )}

      <Dialog open={open != null} onOpenChange={(o) => !o && setOpen(null)}>
        <DialogContent>
          <DialogTitle className="sr-only">{alt}</DialogTitle>
          {open != null && (
            <Photo att={photos[open]} alt={alt} className="max-h-[80dvh] w-full object-contain" />
          )}
          {photos.length > 1 && open != null && (
            <div className="flex justify-between">
              <Button variant="ghost" size="icon-sm" aria-label={es.attachments.previous}
                      disabled={open === 0} onClick={() => setOpen(open - 1)}>
                <RiArrowLeftSLine />
              </Button>
              <Button variant="ghost" size="icon-sm" aria-label={es.attachments.next}
                      disabled={open === photos.length - 1} onClick={() => setOpen(open + 1)}>
                <RiArrowRightSLine />
              </Button>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
