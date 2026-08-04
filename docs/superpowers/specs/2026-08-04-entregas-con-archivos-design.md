# Entregas con archivos: Design Spec

Written 2026-08-04. **Urgent — the first tarea is already assigned and students cannot attach anything to their entrega.**

Self-contained on purpose: this is meant to be picked up in a fresh session with no prior context.

## 1. State of play

The backend for file uploads has existed since Phase 1 and is complete. Nothing is missing there:

| Piece | Where | State |
|---|---|---|
| `Attachment` model + table | `backend/app/models.py` | done |
| Upload on post create (any post, including replies) | `backend/app/routers/posts.py` — `create_post` accepts `files: List[UploadFile]` | done |
| Validation — 10 MB cap, extension allowlist | `backend/app/storage.py` — `validate_file` | done |
| Max 4 files per post | `posts.py` — `MAX_FILES` | done |
| R2 upload | `storage.upload_bytes` | done |
| Presigned download URL | `GET /api/attachments/{id}/url` | done |
| Feature flag exposed to the client | `GET /api/config` → `file_uploads_enabled` | done |

Allowed extensions: `pdf, doc, docx, xls, xlsx, ppt, pptx, txt, csv, zip, rar, 7z, png, jpg, jpeg, gif, webp, svg`.

**Three things block a student from attaching work.** One is Mario's, two are code.

## 2. Blocker A — R2 is not configured in production (Mario)

`https://school-app-production-e9f4.up.railway.app/api/config` currently returns `"file_uploads_enabled": false`.

`storage.is_r2_configured()` requires all four of these to be non-empty. They are read by `backend/app/config.py` as pydantic settings, so the environment variable names are the uppercased field names:

- `R2_ACCESS_KEY_ID`
- `R2_SECRET_ACCESS_KEY`
- `R2_ENDPOINT`
- `R2_BUCKET_NAME`

**Until these are set on the Railway service, every upload is rejected with 400 "La subida de archivos no está habilitada" — no code change can work around it.** Creating the R2 bucket and its API token is a Cloudflare dashboard task nobody but Mario can do.

Verify with `curl -s https://school-app-production-e9f4.up.railway.app/api/config`; the flag flips to `true` on its own once the variables are present and the service restarts.

## 3. Blocker B — the reply composer has no file input

`frontend/src/pages/Thread.tsx` renders the reply form as a single text `<input>` plus a submit button. There is no file picker anywhere in it.

An entrega **is** a reply (`is_entrega` on a reply to a tarea), so this is the actual reason a student cannot hand in a photo of their work. The backend already accepts `files` on replies — this is purely a missing control.

The reply form must gain the same attachment affordance the main composer has: a picker, a list of chosen files, and the 4-file cap. It should appear only when `config.file_uploads_enabled` is true, matching how `Compose.tsx` already gates it.

## 4. Blocker C — attachments are gated to `mode === "regular"`

`frontend/src/pages/Compose.tsx` renders the attach button only when the composer is in `regular` mode. Consequences:

- a teacher cannot attach a PDF to a **tarea** — no assignment sheet, no reading
- a student cannot attach anything to a **participación**

Both look like oversights rather than decisions; nothing in any spec asks for them. The gate should become `config.file_uploads_enabled` alone, independent of mode.

## 5. Decisions

### 5.1 Same limits everywhere

4 files, 10 MB each, the existing extension allowlist. No per-type rules for entregas — a photo of handwritten work and a PDF are equally valid evidence.

### 5.2 The flag governs the affordance, not just the request

When `file_uploads_enabled` is false the picker is not rendered at all, anywhere. A disabled button inviting a student to attach work that will be refused is worse than no button.

### 5.3 An entrega with only a file is valid

`create_post` already accepts a post with no text when files are present (`if not content.strip() and not files`). A photo *is* the entrega; requiring a caption would be busywork. The reply form's submit must therefore enable on **either** text or files, not text alone — its current `disabled={!reply.trim()}` would block a photo-only entrega.

### 5.4 Out of scope

Progress indicators, drag-and-drop, client-side image compression, and previewing an attachment inline. Get the file to R2 first.

## 6. Testing

- **API:** a reply with a file and no text is accepted; a 5th file is rejected; an 11 MB file is rejected; a `.exe` is rejected; uploading with R2 off returns 400
- **Frontend:** the picker is absent when `file_uploads_enabled` is false; submit enables with files and no text
- **Manual, on a phone:** attach a photo from the camera roll to an entrega, then open it from the thread as the teacher

## 7. Notes for whoever picks this up

- Blocker A gates the other two from being *verifiable*, but B and C can be built and merged before the credentials exist — the flag simply keeps the UI hidden until then. Do not wait.
- `Compose.tsx` already has working file-picker code (`fileInput` ref, `files` state, the 4-file slice). Task: lift it into something both composers use rather than writing it twice.
- The composer sends `FormData` with repeated `files` fields; the reply form currently sends `FormData` too, so the shape already matches.
