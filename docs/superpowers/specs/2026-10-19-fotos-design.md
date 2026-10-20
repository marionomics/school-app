# Bloque 3a — Photos: inline images and profile photo

**Status:** design approved by Mario on 2026-10-19, section by section; written spec approved 2026-10-20. Roadmap Bloque 3 ("Fotos primero").

## Goal

Sometimes a student says something better with a photo. Today an attached image shows as a link you have to open; it should show in the post, like on a social network. Success: a student posts a photo from their phone and everyone sees it in the feed right away, on any phone, without burning through their mobile data. And everyone can set their own profile photo.

## Decisions (Mario)

1. **Shrink once, keep no original** (option B). So handwriting stays legible when grading, the size is generous: **2048 px on the long side**, JPEG quality 0.85 (≈ 400–700 KB). Never enlarge.
2. **Shrink on the phone, before upload** (option A). Less data uploaded, and the iPhone converts its HEIC to JPEG on the way — the HEIC that Android can't display disappears at the source.
3. **The teacher can remove any student's profile photo** (option A): an exception, not an approval queue. The student goes back to their Google photo and can upload another.
4. **Photos already uploaded also show inline**, with nothing migrated on R2 (there are few, even though they are full-size originals).
5. **The bio already exists** (edited on `/onboarding`); showing it to others is the profile page `/u/:username`, a separate spec right after this one.

## 1. Upload

### `frontend/src/lib/images.ts` (relative imports — it has a test file)
- `fitWithin(w, h, max): { width, height }` — scales down proportionally if the long side exceeds `max`; otherwise returns the input. Pure.
- `centerSquare(w, h): { sx, sy, size }` — the centred square crop. Pure.
- `shouldShrink(file): boolean` — `true` for `image/jpeg`, `image/png`, `image/webp`, `image/heic`, `image/heif` (or a `.heic/.heif` extension with an empty `type`); `false` for GIF (it would lose its animation), SVG, and anything that isn't an image. Pure.
- `shrinkImage(file, max = 2048): Promise<File>` — if `shouldShrink`, decodes with `createImageBitmap(file, { imageOrientation: "from-image" })`, fills the canvas white (a transparent PNG would otherwise turn black in JPEG), draws at `fitWithin(...)` and encodes `image/jpeg` at 0.85, named `<base>.jpg`. Returns the **original** if: it doesn't apply, the browser can't decode it (HEIC on desktop Chrome), any step fails, or the result is larger than the original **and the original is JPEG, PNG or WebP** — a HEIC is always delivered converted, even if the JPEG is larger, because HEIC doesn't display on Android.
- `squareAvatar(file, size = 512): Promise<File>` — the same, cropping with `centerSquare` and scaling to `size`×`size`.

**Side effects:** re-encoding drops all metadata — including the photo's **GPS location** (a photo taken at home no longer tells classmates where the student lives) — and applies orientation (sideways photos come out upright).

### Where it runs
Every file picker — composer, reply form, entregas — goes through a helper `prepareFiles(files: File[]): Promise<File[]>` (in `images.ts`) before `addFiles`. While it works, the picker shows "Preparando foto…" and the publish button waits. A failure silently falls back to the original.

### Backend
No change to post uploads: same 10 MB cap, same extensions, same `create_post`. The server never trusts the client to have shrunk anything. No migration for post photos (dimensions aren't stored; section 2's layout doesn't need them).

## 2. How photos look

### Backend
- `AttachmentOut` gains `url: Optional[str]`: an R2 signed link **valid for one hour** (`storage.generate_presigned_url`, local signing with no network call) for displayable attachments — `mime_type` in `image/jpeg`, `image/png`, `image/webp`, `image/gif`. HEIC, SVG and non-images: `url = None` (they stay chips). R2 not configured: `url = None`.
- One helper `attachment_out(att) -> AttachmentOut` in one place; used by `serialize_post` and the exam roster.
- Deleted post: still no attachments. Vetoed: keeps its photos, like its text.
- The `/revisar → Exámenes` roster (`submission.attachments`) includes the same `url`.

### Frontend: `components/PostPhotos.tsx`
Used by `PostCard` and `ExamenRoster`.
- **1 photo:** full width, fixed **4:5** box, whole photo visible (`object-contain`) on a light grey background. Fixed so the feed doesn't jump while loading; uncropped so a page of homework is never cut.
- **2–4 photos:** a 2-column grid of cropped square tiles (`object-cover`).
- **Tap** opens the whole photo full screen in the preset `Dialog`, with previous/next when there are several. Closing returns to the same spot in the feed.
- Grey placeholder while loading; `loading="lazy"` and `decoding="async"`.
- **Expired link** (tab open longer than an hour): on `onError`, once, it asks `/api/attachments/{id}/url` and retries with the new one.
- `alt` from the strings module: "Foto de @{user}" (placeholder). No per-photo captions.
- Which layout N photos get is a pure function (`photoLayout(n)`) in `src/lib`.
- Non-image attachments stay as chips below the photos.

## 3. Profile photo

### Backend
- **Migration:** `users.avatar_key` (`String(500)`, nullable). `users.avatar_url` (Google's, set when the account is created) stays as the fallback.
- **One helper `avatar_for(user) -> Optional[str]`**: a one-hour signed link to `avatar_key` if set and R2 is configured; otherwise `avatar_url`. Every schema that exposes a user's `avatar_url` (`AuthorOut`, `UserOut`, roster rows in `classes.py` and `grades.py`) gets it from this helper — the frontend keeps the same field.
- `PUT /api/users/me/avatar` (multipart, one `file`): only `image/jpeg`, `image/png`, `image/webp`; at most 10 MB; otherwise 422. No R2: 400. Uploads to `avatars/{user_id}_{timestamp}.jpg`, sets `avatar_key`, returns `UserOut`.
- `DELETE /api/users/me/avatar`: `avatar_key = NULL`; returns `UserOut`.
- `DELETE /api/users/{user_id}/avatar`: teacher only, and only if that user has an enrollment in a class the teacher teaches; otherwise 403. Same effect.
- Replaced photos are not deleted from R2 (they're small).

### Frontend
- On `/onboarding` (where username and bio are already edited; the bottom-nav "perfil" icon leads there): the current photo with **Cambiar foto** and, if they uploaded their own, **Quitar foto**. Picking a photo crops it to the centre square and shrinks it to 512 px (`squareAvatar`), shows a preview and saves with **Guardar**. Optimistic with visible rollback.
- The teacher's **Quitar foto** lives for now in the student sheet of the class panel (the one that lists their faltas); it moves to the profile page once `/u/:username` exists.
- `Avatar`: if the image fails (expired link), it falls back to the initial instead of a broken image.

## 4. Tests

**Backend** (first; R2 replaced by a stub that records uploads and returns predictable signed links — tests never talk to Cloudflare):
- An image attachment carries `url`; a PDF doesn't; HEIC and SVG don't.
- Deleted post: no attachments; vetoed: keeps them with `url`.
- The exam roster carries `url` in `submission.attachments`.
- Uploading a photo sets `avatar_key`, and that user's `avatar_url` is the signed link in `/me`, in the feed (`author`) and in the class roster.
- Removing the photo goes back to Google's.
- PDF or a file over 10 MB → 422.
- A student can't remove another student's photo (403); the teacher can, only for students in their class (anyone else → 403).
- Migration: adding the column keeps existing users' Google `avatar_url`.

**Frontend:** `fitWithin` (only shrinks, keeps proportions, portrait and landscape), `centerSquare`, `shouldShrink` (GIF, SVG, non-image → false; HEIC with no `type` → true), `photoLayout(n)`. Types, lint, build. Phone QA after deploy: an iPhone HEIC photo visible on Android, a handwritten page legible when tapped, a profile photo change visible everywhere.

## Commit order (each deployable)

1. Backend: `url` on image attachments (`attachment_out`) + roster.
2. Frontend: `PostPhotos` + full-screen viewer — already-uploaded photos show inline from here on.
3. Frontend: `images.ts` shrinking on every file picker.
4. Backend: `avatar_key` + migration + `avatar_for` + the three endpoints.
5. Frontend: change/remove photo on `/onboarding`, the teacher's button in the panel, the `Avatar` fallback.

## Out of scope

- The profile page `/u/:username` (visible bio, aura received, posts) — next spec.
- A draggable crop editor; per-photo captions; shrinking already-uploaded photos on R2; deleting replaced profile photos from R2.
