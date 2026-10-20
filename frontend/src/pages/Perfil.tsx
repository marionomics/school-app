import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { squareAvatar } from "@/lib/images";
import Avatar from "@/components/Avatar";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/Toaster";
import { es } from "@/strings/es";
import type { User } from "@/lib/types";

export default function Perfil() {
  const { user, refresh } = useAuth();
  const toast = useToast();
  const input = useRef<HTMLInputElement>(null);
  const [preview, setPreview] = useState<{ file: File; url: string } | null>(null);
  const [bio, setBio] = useState(user?.bio ?? "");
  const [busy, setBusy] = useState(false);

  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview.url); }, [preview]);

  if (!user) return null;
  const hasOwnPhoto = user.has_own_avatar;

  async function savePhoto() {
    if (!preview) return;
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", preview.file);
      await api<User>("/api/users/me/avatar", { method: "PUT", body: fd });
      await refresh();
      setPreview(null);
      toast.show(es.perfil.saved);
    } catch {
      toast.show(es.perfil.error);   // the old photo is still the one shown
    } finally {
      setBusy(false);
    }
  }

  async function removePhoto() {
    setBusy(true);
    try {
      await api<User>("/api/users/me/avatar", { method: "DELETE" });
      await refresh();
    } catch {
      toast.show(es.perfil.error);
    } finally {
      setBusy(false);
    }
  }

  async function saveBio() {
    setBusy(true);
    try {
      await api<User>("/api/users/me", { method: "PATCH", body: JSON.stringify({ bio }) });
      await refresh();
      toast.show(es.perfil.saved);
    } catch {
      toast.show(es.perfil.error);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-6 p-4">
      <h1 className="text-xl font-bold">{es.perfil.title}</h1>

      <section className="flex flex-col gap-3">
        <Label htmlFor="photo">{es.perfil.photoLabel}</Label>
        {preview ? (
          <img src={preview.url} alt="" className="size-24 rounded-full object-cover" />
        ) : (
          <Avatar author={user} size={96} />
        )}
        <input
          id="photo"
          ref={input}
          type="file"
          accept="image/*"
          hidden
          onChange={async (e) => {
            const picked = e.target.files?.[0];
            e.target.value = "";
            if (!picked) return;
            const file = await squareAvatar(picked);
            // Not a JPEG means it couldn't be decoded here (HEIC on Android or
            // desktop): a preview would be a broken image and the save a 422.
            if (file.type !== "image/jpeg") {
              toast.show(es.perfil.photoUnreadable);
              return;
            }
            setPreview({ file, url: URL.createObjectURL(file) });
          }}
        />
        {preview ? (
          <>
            <Button onClick={savePhoto} disabled={busy}>{es.perfil.savePhoto}</Button>
            <Button variant="outline" onClick={() => setPreview(null)} disabled={busy}>
              {es.perfil.cancel}
            </Button>
          </>
        ) : (
          <>
            <Button variant="outline" onClick={() => input.current?.click()} disabled={busy}>
              {es.perfil.changePhoto}
            </Button>
            {hasOwnPhoto && (
              <Button variant="ghost" onClick={removePhoto} disabled={busy}>
                {es.perfil.removePhoto}
              </Button>
            )}
          </>
        )}
      </section>

      <section className="flex flex-col gap-3">
        <Label htmlFor="bio">{es.perfil.bioLabel}</Label>
        <Textarea id="bio" value={bio} maxLength={500} onChange={(e) => setBio(e.target.value)} />
        <Button onClick={saveBio} disabled={busy || bio === user.bio}>{es.perfil.saveBio}</Button>
      </section>
    </div>
  );
}
