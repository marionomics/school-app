# Entregas con archivos — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A student can attach a photo or a PDF to an entrega, and a teacher can attach the assignment sheet to a tarea.

**Architecture:** The backend has been complete since Phase 1 — `POST /api/posts` already accepts `files` on any post, including replies. All the frontend work is a missing control: lift the file-picker rules out of `Compose.tsx` into a pure module (`lib/attachments.ts`) plus a shared component (`components/FilePicker.tsx`), then use it in both composers. Backend work is tests only, no production code.

**Tech Stack:** React 19 + Vite + Tailwind, `@base-ui/react` (`base-sera` shadcn preset), `@remixicon/react`, vitest. FastAPI + pytest on the backend. Cloudflare R2 for storage.

**Spec:** `docs/superpowers/specs/2026-08-04-entregas-con-archivos-design.md` — read it first. Bug 6 in `planning/bugs.md`.

## Global Constraints

- **No schema change and no migration.** `Attachment` and every endpoint already exist. If you find yourself editing `models.py`, stop — you are solving the wrong problem.
- **Mobile first.** The reply bar is a fixed bottom bar on a phone. QA at 390 px wide before anything else.
- **Preset components only.** The attach control uses `Button` from `@/components/ui/button`. Never hand-roll `<button className="rounded-md border …">`; never edit `--radius` or strip `uppercase`.
- **Icons from `@remixicon/react`.** `RiAttachment2` is the attachment icon everywhere, already used by `PostCard`.
- **All user-facing copy lives in `frontend/src/strings/es.ts`** as a placeholder. Mario writes the final wording. Never inline a Spanish string in a component.
- **Modules under test import siblings relatively** (`./attachments`, not `@/lib/attachments`). Bug R5: vitest does not resolve the `@/` alias, and a test that dies at import is silently absent from the suite. Non-test-imported modules may keep using `@/`.
- **Limits, unchanged and identical everywhere:** 4 files per post, 10 MB per file, extensions `pdf doc docx xls xlsx ppt pptx txt csv zip rar 7z png jpg jpeg gif webp svg`.
- **The flag governs the affordance, not just the request** (spec §5.2): when `file_uploads_enabled` is false the picker is not rendered at all. No disabled button.
- Run `npm run lint && npm run typecheck && npm test` in `frontend/` before every frontend commit — CI's lint step fails before `npm test`, so a lint error hides test results.

## File Structure

| File | Responsibility |
|---|---|
| `frontend/src/lib/attachments.ts` | **Create.** Pure rules: the 4-file cap and "text or files" submit rule. No React, no imports. |
| `frontend/src/lib/attachments.test.ts` | **Create.** Unit tests for the above. |
| `frontend/src/lib/config.ts` | **Create.** `useUploadsEnabled()` — the one place `/api/config` is read for the flag. |
| `frontend/src/components/FilePicker.tsx` | **Create.** `FilePicker` (hidden input + attach button, renders nothing when uploads are off) and `FileChips` (the chosen filenames). |
| `frontend/src/strings/es.ts` | **Modify.** New `attachments` section; `compose.attach` moves into it. |
| `frontend/src/pages/Compose.tsx` | **Modify.** Blocker C — drop the `mode === "regular"` gate, use the shared picker. |
| `frontend/src/pages/Thread.tsx` | **Modify.** Blocker B — the reply form gains the picker and sends `files`. |
| `backend/tests/test_attachments_upload.py` | **Create.** The upload cases spec §6 lists, with R2 faked. |
| `planning/bugs.md`, `planning/changelog.md`, `planning/roadmap.md` | **Modify.** Close B and C, leave A visible. |

---

### Task 0: R2 credentials on Railway (Mario only — no code)

This is Blocker A. **It does not block Tasks 1–6** — they build and merge with the flag off, which simply keeps the picker hidden. Do not wait for it, but it must be done before anyone can hand in a file.

- [ ] **Step 1: Create the R2 bucket**

In the Cloudflare dashboard → **R2** → *Create bucket*. Name it `school-app` (any name works — whatever you pick is `R2_BUCKET_NAME`). Location: automatic. No public access — the app serves files through presigned URLs, the bucket stays private.

- [ ] **Step 2: Create an API token**

R2 → **Manage R2 API Tokens** → *Create API token*. Permissions: **Object Read & Write**, scoped to that one bucket. On save Cloudflare shows, once:

- **Access Key ID** → `R2_ACCESS_KEY_ID`
- **Secret Access Key** → `R2_SECRET_ACCESS_KEY`
- the **S3 endpoint**, shaped `https://<account-id>.r2.cloudflarestorage.com` → `R2_ENDPOINT` (no bucket name in it — `storage._client()` passes the bucket separately)

Copy all three now; the secret is not shown again.

- [ ] **Step 3: Set the four variables on the Railway service**

Railway → the `school-app` service → **Variables** → *Raw editor*:

```
R2_ACCESS_KEY_ID=…
R2_SECRET_ACCESS_KEY=…
R2_ENDPOINT=https://<account-id>.r2.cloudflarestorage.com
R2_BUCKET_NAME=school-app
```

The names are the uppercased pydantic field names in `backend/app/config.py` — they must match exactly. Railway redeploys on save.

- [ ] **Step 4: Verify the flag flipped**

```bash
curl -s https://school-app-production-e9f4.up.railway.app/api/config
```

Expected: `"file_uploads_enabled": true`. If it is still `false`, one of the four is empty or misspelled — `storage.is_r2_configured()` requires all four to be non-empty and reports nothing about which one is missing.

---

### Task 1: The pure attachment rules

**Files:**
- Create: `frontend/src/lib/attachments.ts`
- Test: `frontend/src/lib/attachments.test.ts`

**Interfaces:**
- Consumes: nothing.
- Produces: `MAX_FILES: number`, `capFiles(picked: FileList | File[] | null | undefined): File[]`, `canSubmit(text: string, files: File[]): boolean`. Tasks 2, 3 and 4 all import these.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/lib/attachments.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { canSubmit, capFiles, MAX_FILES } from "./attachments";

const file = (name: string) => new File(["x"], name, { type: "application/pdf" });

describe("capFiles", () => {
  it("returns an empty array when nothing was chosen", () => {
    expect(capFiles(null)).toEqual([]);
    expect(capFiles(undefined)).toEqual([]);
  });

  it("keeps every file up to the cap", () => {
    const picked = [file("a.pdf"), file("b.pdf")];
    expect(capFiles(picked).map((f) => f.name)).toEqual(["a.pdf", "b.pdf"]);
  });

  it("drops everything past the fourth", () => {
    const picked = ["a", "b", "c", "d", "e"].map((n) => file(`${n}.pdf`));
    expect(capFiles(picked)).toHaveLength(MAX_FILES);
    expect(capFiles(picked).map((f) => f.name)).toEqual([
      "a.pdf",
      "b.pdf",
      "c.pdf",
      "d.pdf",
    ]);
  });
});

describe("canSubmit", () => {
  it("is false with neither text nor files", () => {
    expect(canSubmit("", [])).toBe(false);
  });

  it("is false when the text is only whitespace", () => {
    expect(canSubmit("   \n ", [])).toBe(false);
  });

  it("is true with text alone", () => {
    expect(canSubmit("aquí está mi entrega", [])).toBe(true);
  });

  it("is true with a file and no text — a photo IS the entrega", () => {
    expect(canSubmit("", [file("foto.jpg")])).toBe(true);
  });

  it("is true with both", () => {
    expect(canSubmit("ahí va", [file("foto.jpg")])).toBe(true);
  });
});
```

- [ ] **Step 2: Run it and watch it fail**

```bash
cd frontend && npx vitest run src/lib/attachments.test.ts
```

Expected: FAIL — `Failed to resolve import "./attachments"`.

- [ ] **Step 3: Write the module**

Create `frontend/src/lib/attachments.ts`:

```ts
// The server enforces the same cap (MAX_FILES in backend/app/routers/posts.py);
// this exists so the UI never offers to send a fifth file it knows is refused.
export const MAX_FILES = 4;

/** The picker replaces the whole selection, so anything past the cap is dropped. */
export function capFiles(picked: FileList | File[] | null | undefined): File[] {
  return Array.from(picked ?? []).slice(0, MAX_FILES);
}

/**
 * A post is publishable with text, with files, or with both — never with
 * neither. Matches `create_post`, which accepts an empty body when files are
 * present: requiring a caption on a photo of handwritten work is busywork.
 */
export function canSubmit(text: string, files: File[]): boolean {
  return text.trim().length > 0 || files.length > 0;
}
```

- [ ] **Step 4: Run the test again**

```bash
cd frontend && npx vitest run src/lib/attachments.test.ts
```

Expected: PASS, 8 tests.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/attachments.ts frontend/src/lib/attachments.test.ts
git commit -m "feat(frontend): pure file-picker rules — 4-file cap and text-or-files submit"
```

---

### Task 2: The shared picker component

**Files:**
- Create: `frontend/src/lib/config.ts`
- Create: `frontend/src/components/FilePicker.tsx`
- Modify: `frontend/src/strings/es.ts`

**Interfaces:**
- Consumes: `capFiles` from Task 1.
- Produces: `useUploadsEnabled(): boolean`; `<FilePicker files={File[]} onChange={(f: File[]) => void} compact?={boolean} />`; `<FileChips files={File[]} className?={string} />`. Tasks 3 and 4 render both.

No test for this task — it is React rendering, and this repo's vitest setup has no DOM environment. The logic that *can* be unit-tested left for `lib/attachments.ts` in Task 1; what remains is verified by the manual pass in Task 6.

- [ ] **Step 1: Add the config hook**

Create `frontend/src/lib/config.ts`:

```ts
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export type AppConfig = { file_uploads_enabled: boolean };

/**
 * `/api/config` only changes when the service restarts with different R2
 * variables, so it never goes stale inside a session.
 */
export function useUploadsEnabled(): boolean {
  const q = useQuery({
    queryKey: ["config"],
    queryFn: () => api<AppConfig>("/api/config"),
    staleTime: Infinity,
  });
  return q.data?.file_uploads_enabled ?? false;
}
```

- [ ] **Step 2: Add the copy placeholders**

In `frontend/src/strings/es.ts`, add a new top-level section next to `post`:

```ts
  attachments: {
    attach: "Adjuntar",
    chosen: "{n} archivo(s)",
  },
```

Leave `compose.attach` where it is for now — `Compose.tsx` still references it, and removing it here would leave this commit failing typecheck. Task 3 deletes it once its last caller is gone.

- [ ] **Step 3: Write the component**

Create `frontend/src/components/FilePicker.tsx`:

```tsx
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
```

Note the hooks are all called before the `if (!enabled) return null` — bug R3 was a `return` above a hook, and React treats a changing hook order as fatal.

- [ ] **Step 4: Verify it compiles and lints**

```bash
cd frontend && npm run lint && npm run typecheck && npm test
```

Expected: all clean. Nothing renders `FilePicker` yet — that is Tasks 3 and 4 — but an unused export is not a lint error, so the tree stays green. The repo has one pre-existing lint *warning*; zero errors is the bar.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/config.ts frontend/src/components/FilePicker.tsx frontend/src/strings/es.ts
git commit -m "feat(frontend): shared FilePicker, hidden when uploads are disabled"
```

---

### Task 3: Blocker C — attachments in every composer mode

**Files:**
- Modify: `frontend/src/pages/Compose.tsx` (imports, the config query, the mode buttons, the publish button, the picker block)
- Modify: `frontend/src/strings/es.ts` (delete the now-unused `compose.attach`)

**Interfaces:**
- Consumes: `canSubmit` (Task 1), `FilePicker` / `FileChips` (Task 2).
- Produces: nothing.

Why: a teacher cannot attach the assignment sheet to a **tarea**, and a student cannot attach anything to a **participación**. Nothing in any spec asks for either restriction.

- [ ] **Step 1: Fix the imports**

`useRef` and `RiAttachment2` become unused. Replace lines 1–12 of `frontend/src/pages/Compose.tsx` with:

```tsx
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useTapWindow } from "@/hooks/useTapWindow";
import { useToast } from "@/components/Toaster";
import { FileChips, FilePicker } from "@/components/FilePicker";
import { canSubmit } from "@/lib/attachments";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { es } from "@/strings/es";
import type { MyClasses, Post } from "@/lib/types";
```

- [ ] **Step 2: Drop the local config query and the file input ref**

Delete the `fileInput` ref declaration:

```tsx
  const fileInput = useRef<HTMLInputElement>(null);
```

and the whole `config` query — `FilePicker` reads the flag itself now:

```tsx
  const config = useQuery({
    queryKey: ["config"],
    queryFn: () => api<{ file_uploads_enabled: boolean }>("/api/config"),
  });
```

- [ ] **Step 3: Stop clearing files when switching to participación**

In the student mode buttons, replace:

```tsx
              onClick={() => {
                setMode(m);
                if (m === "participacion") setFiles([]);
              }}
```

with:

```tsx
              onClick={() => setMode(m)}
```

- [ ] **Step 4: Use `canSubmit` on the publish button**

Replace:

```tsx
            disabled={(!content.trim() && files.length === 0) || needsClass || publish.isPending}
```

with:

```tsx
            disabled={!canSubmit(content, files) || needsClass || publish.isPending}
```

- [ ] **Step 5: Replace the gated picker block**

Replace the whole block currently at lines 205–221:

```tsx
      {config.data?.file_uploads_enabled && mode === "regular" && (
        <div>
          <input
            ref={fileInput}
            type="file"
            multiple
            hidden
            onChange={(e) => setFiles(Array.from(e.target.files ?? []).slice(0, 4))}
          />
          <button onClick={() => fileInput.current?.click()} className="rounded-md border px-3 py-1.5 text-sm">
            <RiAttachment2 className="size-4" /> {es.compose.attach}
          </button>
          {files.map((f) => (
            <span key={f.name} className="ml-2 text-xs text-muted-foreground">{f.name}</span>
          ))}
        </div>
      )}
```

with:

```tsx
      <div className="flex flex-col gap-2">
        <FilePicker files={files} onChange={setFiles} />
        <FileChips files={files} />
      </div>
```

The mode gate is gone: a tarea, an examen and a participación can all carry files now, and `FilePicker` itself renders nothing when uploads are disabled.

Its last caller gone, now delete the `attach: "Adjuntar",` line from the `compose` section of `frontend/src/strings/es.ts` — the string lives in `attachments` since Task 2. Confirm with `grep -rn "compose.attach" frontend/src` that nothing references it.

- [ ] **Step 6: Verify**

```bash
cd frontend && npm run lint && npm run typecheck && npm test
```

Expected: all clean. `api` and `useQuery` are still imported and still used (`mine`, `defaultClass`, `publish`) — if lint reports either as unused you deleted one query too many.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/Compose.tsx
git commit -m "fix(frontend): allow attachments on tareas, exámenes and participaciones"
```

---

### Task 4: Blocker B — the reply form can attach files

**Files:**
- Modify: `frontend/src/pages/Thread.tsx` (imports, state, `send` mutation, the reply form)

**Interfaces:**
- Consumes: `canSubmit` (Task 1), `FilePicker` / `FileChips` (Task 2).
- Produces: nothing.

Why: an entrega **is** a reply, so this is the actual reason handing in a photo is impossible today. The backend already accepts `files` on replies.

- [ ] **Step 1: Add the imports and the files state**

After the existing `PostCard` import in `frontend/src/pages/Thread.tsx`, add:

```tsx
import { FileChips, FilePicker } from "@/components/FilePicker";
import { canSubmit } from "@/lib/attachments";
```

and next to `const [reply, setReply] = useState("");` add:

```tsx
  const [files, setFiles] = useState<File[]>([]);
```

- [ ] **Step 2: Send the files and clear them on success**

In the `send` mutation, append the files to the `FormData` and reset them after a successful post:

```tsx
  const send = useMutation({
    mutationFn: () => {
      const fd = new FormData();
      fd.set("content", reply);
      fd.set("parent_id", String(replyTo ? replyTo.id : id));
      if (isEntrega) fd.set("is_entrega", "true");
      for (const f of files) fd.append("files", f);
      return api<Post>("/api/posts", { method: "POST", body: fd });
    },
    onSuccess: () => {
      setReply("");
      setFiles([]);
      setReplyTo(null);
      setIsEntrega(false);
      void qc.invalidateQueries({ queryKey: ["thread", id] });
      void qc.invalidateQueries({ queryKey: ["feed"] });
    },
    onError: () => toast.show(es.post.replyError),
  });
```

- [ ] **Step 3: Let a photo-only entrega through the submit guard**

Replace the form's `onSubmit`:

```tsx
        onSubmit={(e) => {
          e.preventDefault();
          if (reply.trim()) send.mutate();
        }}
```

with:

```tsx
        onSubmit={(e) => {
          e.preventDefault();
          if (canSubmit(reply, files)) send.mutate();
        }}
```

- [ ] **Step 4: Put the picker in the reply bar**

Replace the input row at the bottom of the form:

```tsx
        <div className="flex gap-2">
          <input
            className="flex-1 rounded-full border px-4 py-2"
            placeholder={es.post.replyPlaceholder}
            value={reply}
            onChange={(e) => setReply(e.target.value)}
          />
          <button disabled={!reply.trim() || send.isPending} className="rounded-full bg-primary px-4 py-2 text-primary-foreground disabled:opacity-50">
            {es.post.replySubmit}
          </button>
        </div>
```

with:

```tsx
        <FileChips files={files} className="mb-2" />
        <div className="flex items-center gap-2">
          <FilePicker files={files} onChange={setFiles} compact />
          <input
            className="min-w-0 flex-1 rounded-full border px-4 py-2"
            placeholder={es.post.replyPlaceholder}
            value={reply}
            onChange={(e) => setReply(e.target.value)}
          />
          <button
            disabled={!canSubmit(reply, files) || send.isPending}
            className="rounded-full bg-primary px-4 py-2 text-primary-foreground disabled:opacity-50"
          >
            {es.post.replySubmit}
          </button>
        </div>
```

`min-w-0` matters: without it the text input refuses to shrink below its intrinsic width and the attach button pushes the submit button off a 390 px screen.

- [ ] **Step 5: Verify**

```bash
cd frontend && npm run lint && npm run typecheck && npm test
```

Expected: all clean.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/Thread.tsx
git commit -m "feat(frontend): attach files to a reply — an entrega can be a photo"
```

---

### Task 5: Backend tests for uploads

**Files:**
- Create: `backend/tests/test_attachments_upload.py`

**Interfaces:**
- Consumes: the existing `client`, `db`, `auth_headers`, `enrolled`, `klass`, `student`, `teacher` fixtures from `backend/tests/conftest.py`.
- Produces: nothing.

No production code changes. `test_upload_rejected_when_r2_off` in `backend/tests/test_posts_create.py` already covers the disabled path; everything else in spec §6 needs R2 faked, because `create_post` refuses uploads before it ever validates a file.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_attachments_upload.py`:

```python
import pytest

from app import storage
from app.models import Attachment, Post


@pytest.fixture()
def r2_on(monkeypatch):
    """Pretend R2 is configured and swallow the upload — no network in tests."""
    uploaded = []
    monkeypatch.setattr(storage, "is_r2_configured", lambda: True)
    monkeypatch.setattr(
        storage,
        "upload_bytes",
        lambda data, key, content_type: uploaded.append((key, len(data))),
    )
    return uploaded


def a_file(name="nota.pdf", size=64, mime="application/pdf"):
    return ("files", (name, b"x" * size, mime))


@pytest.fixture()
def tarea(db, teacher, klass):
    t = Post(author_id=teacher.id, content="Lee el capítulo 3", type="tarea",
             class_id=klass.id)
    db.add(t)
    db.commit()
    return t


def test_reply_with_only_a_file_is_accepted(client, db, auth_headers, enrolled,
                                            klass, student, r2_on):
    root = Post(author_id=student.id, content="hilo", class_id=klass.id)
    db.add(root)
    db.commit()

    res = client.post(
        "/api/posts",
        data={"content": "", "parent_id": str(root.id)},
        files=[a_file("foto.jpg", mime="image/jpeg")],
        headers=auth_headers,
    )

    assert res.status_code == 201
    assert res.json()["attachments"][0]["file_name"] == "foto.jpg"
    assert db.query(Attachment).count() == 1
    assert len(r2_on) == 1  # the bytes actually went to storage


def test_entrega_can_be_a_photo_with_no_text(client, db, auth_headers, enrolled,
                                             tarea, r2_on):
    res = client.post(
        "/api/posts",
        data={"content": "", "parent_id": str(tarea.id), "is_entrega": "true"},
        files=[a_file("mi-tarea.jpg", mime="image/jpeg")],
        headers=auth_headers,
    )

    assert res.status_code == 201
    body = res.json()
    assert body["is_entrega"] is True
    assert len(body["attachments"]) == 1


def test_fifth_file_is_rejected(client, auth_headers, enrolled, r2_on):
    res = client.post(
        "/api/posts",
        data={"content": "cinco"},
        files=[a_file(f"{n}.pdf") for n in "abcde"],
        headers=auth_headers,
    )

    assert res.status_code == 422
    assert "4" in res.json()["detail"]


def test_oversized_file_is_rejected(client, auth_headers, enrolled, r2_on):
    res = client.post(
        "/api/posts",
        data={"content": "pesada"},
        files=[a_file("enorme.pdf", size=storage.MAX_FILE_SIZE + 1)],
        headers=auth_headers,
    )

    assert res.status_code == 422
    assert "grande" in res.json()["detail"].lower()


def test_disallowed_extension_is_rejected(client, db, auth_headers, enrolled, r2_on):
    res = client.post(
        "/api/posts",
        data={"content": "sospechoso"},
        files=[a_file("virus.exe", mime="application/octet-stream")],
        headers=auth_headers,
    )

    assert res.status_code == 422
    assert "permitido" in res.json()["detail"].lower()
    assert db.query(Attachment).count() == 0
```

- [ ] **Step 2: Run them**

```bash
cd backend && python -m pytest tests/test_attachments_upload.py -v
```

Expected: **all five PASS on the first run** — the backend has been complete since Phase 1, so these are characterization tests, not red-then-green. If any fails, that is a real backend bug the spec did not know about: stop and report it rather than editing `posts.py` to match the test.

- [ ] **Step 3: Run the whole backend suite**

```bash
cd backend && python -m pytest -q
```

Expected: green. The `r2_on` fixture uses `monkeypatch`, so the patch unwinds per test and `test_storage.py::test_not_configured_by_default` still sees R2 off.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_attachments_upload.py
git commit -m "test(backend): cover uploads on replies, the 4-file cap, size and extension limits"
```

---

### Task 6: Manual QA, docs and deploy

**Files:**
- Modify: `planning/bugs.md`, `planning/changelog.md`, `planning/roadmap.md`

- [ ] **Step 1: Verify the picker stays hidden with the flag off**

Locally R2 is unconfigured, so this is the default state:

```bash
cd backend && uvicorn app.main:app --reload   # terminal 1
cd frontend && npm run dev                    # terminal 2
```

At 390 px wide (device toolbar → iPhone 12 Pro), open a thread and the composer. Expected: **no attach button anywhere**, and the reply bar looks exactly as it did before this branch. Confirm `curl -s localhost:8000/api/config` reports `"file_uploads_enabled": false`.

- [ ] **Step 2: Verify the picker appears with the flag on**

Stop the backend and restart it with fake credentials — enough for `is_r2_configured()`, and uploads will fail at boto3, which is fine for checking the UI:

```bash
cd backend && R2_ACCESS_KEY_ID=x R2_SECRET_ACCESS_KEY=x \
  R2_ENDPOINT=https://example.invalid R2_BUCKET_NAME=test \
  uvicorn app.main:app --reload
```

Expected, still at 390 px: the attach button appears in the composer in **all four modes** and as an icon button in the reply bar; picking a file shows its name as a chip; the submit button enables with a file and no text; picking five files keeps four.

- [ ] **Step 3: Open the PR**

```bash
git push -u origin HEAD
gh pr create --title "Entregas con archivos: el alumno puede adjuntar su trabajo" \
  --body "Cierra los bloqueos B y C del bug 6. El bloqueo A (variables de R2 en Railway) es de Mario y no bloquea este merge: con el flag apagado el selector simplemente no se dibuja."
```

Wait for CI green (lint, typecheck, vitest, pytest against PostgreSQL) before merging.

- [ ] **Step 4: Merge, deploy and verify in production**

Merge the PR. Railway builds `main` automatically. Once it is up:

```bash
curl -s https://school-app-production-e9f4.up.railway.app/api/config
```

If Task 0 is done this reports `"file_uploads_enabled": true` and the pickers are live. If not, the app is unchanged for users — that is the intended behaviour, not a failed deploy.

- [ ] **Step 5: The real test, on a phone**

Only possible once Task 0 is done. On an actual phone, signed in as a student: open the tarea, tick **Es mi entrega**, tap the attach button, take a photo from the camera roll, send with no text. Then sign in as the teacher, open the thread and tap the attachment — it must open the presigned URL.

- [ ] **Step 6: Update the planning docs**

In `planning/bugs.md`, rewrite the state of row 6 to reflect that only A remains:

```
| 6 | **Parcial — falta configurar R2 en Railway** | **Un alumno no puede adjuntar archivos a su entrega.** (B) y (C) resueltos: `Thread.tsx` ya tiene selector de archivos en el formulario de respuesta y `Compose.tsx` ya no limita los adjuntos a `mode === "regular"` — una tarea, un examen y una participación pueden llevar archivos. Falta (A): `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_ENDPOINT` y `R2_BUCKET_NAME` en Railway; hasta entonces `/api/config` devuelve `file_uploads_enabled: false` y el selector no se dibuja. Plan: `docs/superpowers/plans/2026-08-04-entregas-con-archivos.md`. | 1 / 2a |
```

Move it to **Resueltos** only after Step 5 passes on a real phone.

Add this section at the top of `planning/changelog.md`, under the `# Changelog` heading:

```markdown
## 2026-08-04 (Entregas con archivos)
- **El alumno ya puede adjuntar su trabajo.** Una entrega *es* una respuesta, y el formulario de respuesta en `Thread.tsx` no tenía selector de archivos — ni uno. El backend aceptaba `files` en cualquier post desde la Fase 1 (validación, tope de 4, 10 MB, URLs prefirmadas): faltaba únicamente el control. Con foto y sin texto también se publica, porque la foto *es* la entrega y pedir un pie de foto es trabajo inventado.
- **Los adjuntos dejaron de ser cosa del modo `regular`.** `Compose.tsx` sólo dibujaba el botón en ese modo, así que el profesor no podía adjuntarle el PDF a una tarea ni el alumno nada a una participación. No era una decisión de ningún spec; era un descuido. Ahora la única condición es que las subidas estén habilitadas.
- **Un solo selector para los dos composers.** `FilePicker` no se dibuja cuando `file_uploads_enabled` es false: un botón deshabilitado que invita a adjuntar trabajo que el servidor va a rechazar es peor que no tener botón. Las reglas puras (tope de 4, "texto o archivos") viven en `lib/attachments.ts` con sus tests.
- **Falta el bloqueo que no es código.** Sin las cuatro variables de R2 en Railway, `/api/config` sigue devolviendo `file_uploads_enabled: false` y nada de esto se ve. Es una tarea de dashboard de Cloudflare que sólo Mario puede hacer.
- Tests: 234 backend (desde 229), 33 frontend (desde 25).
```

Recount the two test totals from your own run output — `python -m pytest -q` and `npm test` both print them — rather than trusting the numbers above.

In `planning/roadmap.md`, update the bug-6 line at the top to say that B and C shipped and only the R2 variables remain.

- [ ] **Step 7: Commit the docs**

```bash
git add planning/bugs.md planning/changelog.md planning/roadmap.md
git commit -m "docs: entregas con archivos — bloqueos B y C cerrados, falta R2 en Railway"
```

---

## Spec coverage

| Spec | Task |
|---|---|
| §2 Blocker A — R2 on Railway | Task 0, verified again in Task 6 Step 4 |
| §3 Blocker B — reply composer has no file input | Task 4 |
| §4 Blocker C — attachments gated to `regular` | Task 3 |
| §5.1 Same limits everywhere | Task 1 (`MAX_FILES`), unchanged backend |
| §5.2 Flag governs the affordance | Task 2 (`FilePicker` returns null), Task 6 Step 1 |
| §5.3 An entrega with only a file is valid | Task 1 (`canSubmit`), Task 4 Steps 3–4, Task 5 |
| §5.4 Out of scope | No progress bar, no drag-and-drop, no compression, no inline preview. Also **no per-file remove control** — re-tapping *Adjuntar* replaces the whole selection, which is how the composer already behaved. |
| §6 API tests | Task 5 (plus the existing `test_upload_rejected_when_r2_off`) |
| §6 Frontend tests | Task 1 — the rules are unit-tested; the render gating is checked manually in Task 6 Steps 1–2, since this repo has no DOM test environment |
| §6 Manual on a phone | Task 6 Step 5 |
| §7 Lift the picker instead of writing it twice | Task 2 |
