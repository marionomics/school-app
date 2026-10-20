import { useState } from "react";
import { RiArrowLeftSLine, RiArrowRightSLine, RiAttachment2, RiCloseLine } from "@remixicon/react";
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
  const [failed, setFailed] = useState(false);
  if (failed) return <div role="img" aria-label={alt} className={`${className} bg-muted`} />;
  return (
    <img
      src={src}
      alt={alt}
      loading="lazy"
      decoding="async"
      className={className}
      onError={async () => {
        if (retried) {
          setFailed(true);
          return;
        }
        setRetried(true);
        try {
          const { url } = await api<{ url: string }>(`/api/attachments/${att.id}/url`);
          setSrc(url);
        } catch {
          setFailed(true);
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
  const current = open != null ? photos[open] : undefined;

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

      <Dialog open={current != null} onOpenChange={(o) => !o && setOpen(null)}>
        <DialogContent
          showCloseButton={false}
          className="top-0 left-0 h-dvh max-h-dvh w-screen max-w-none translate-x-0 translate-y-0 gap-0 rounded-none bg-black p-0 text-white ring-0 sm:max-w-none flex flex-col"
        >
          <DialogTitle className="sr-only">{alt}</DialogTitle>
          <div className="flex justify-end p-2">
            <Button variant="ghost" size="icon-sm" aria-label={es.attachments.closeViewer}
                    onClick={() => setOpen(null)}>
              <RiCloseLine />
            </Button>
          </div>
          {current && open != null && (
            <>
              <div className="flex min-h-0 flex-1 items-center justify-center">
                <Photo key={current.id} att={current} alt={alt}
                       className="max-h-full max-w-full object-contain" />
              </div>
              {photos.length > 1 && (
                <div className="flex justify-between p-2">
                  <Button variant="ghost" size="icon" aria-label={es.attachments.previous}
                          disabled={open === 0} onClick={() => setOpen(open - 1)}>
                    <RiArrowLeftSLine />
                  </Button>
                  <Button variant="ghost" size="icon" aria-label={es.attachments.next}
                          disabled={open === photos.length - 1} onClick={() => setOpen(open + 1)}>
                    <RiArrowRightSLine />
                  </Button>
                </div>
              )}
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
