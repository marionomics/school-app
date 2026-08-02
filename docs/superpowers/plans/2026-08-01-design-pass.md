# Design Pass Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the app look and behave like one product — real preset components everywhere, settings organised as an index of group pages, and four behaviours that currently annoy the teacher fixed.

**Architecture:** The shadcn preset `base-sera` is already configured in `frontend/components.json` but only `button.tsx` was ever added. Every task pulls the primitives it needs with `npx shadcn add` and uses them **exactly as they arrive** — no token edits, no restyling wrappers. `Configurar.tsx` splits from one 341-line dumping ground into an index plus six group pages. Two small backend changes ride along.

**Tech Stack:** React 19 + Vite 8 + Tailwind 4, shadcn preset `base-sera` on `@base-ui/react`, `@remixicon/react` for icons, TanStack Query, vitest; FastAPI + pytest on the backend.

## Global Constraints

- Source of truth: `docs/superpowers/specs/2026-08-01-design-pass-design.md`. Where this plan and the spec disagree, the spec wins.
- **Use the preset untouched.** No edits to `--radius`, no stripping `uppercase` or `tracking-widest` from any variant, no wrapper that re-styles a primitive. If a component looks wrong for a surface, pick a different preset component (spec §2.2b).
- **No new dependencies.** Icons come from `@remixicon/react`, already in `package.json`. Never add `lucide-react`.
- One control per line in every form. The only exception is list rows pairing a person with a control — the examen roster and pasar lista (spec §2.2).
- Every points value renders through the units helper from Task 2. No surface writes its own unit string.
- All user-facing copy is a placeholder in `frontend/src/strings/es.ts`. Never inline a Spanish string in a component.
- Never warn that the rubro weights don't total 100. The gap is the design (`CLAUDE.md`).
- `tap_value`, `like_cap` and `daily_post_limit` are not exposed in any UI.
- Backend tests run with `../venv/bin/python -m pytest` from `backend/`. The suite is at 194 and must stay green; it should only grow from Tasks 3 and 12.
- Frontend checks: `npx vitest run && npx tsc --noEmit && npm run lint` from `frontend/`. Note vitest may fail locally on Node 16 — CI runs Node 22 (`planning/changelog.md`, 2b-1 entry). If it fails locally with a Vite/Node error, run `tsc` and `lint` and let CI cover vitest.
- Nothing deploys. This branch stays local until Mario has seen it on a phone (spec §7).

---

### Task 1: Add the preset primitives

**Files:**
- Create: `frontend/src/components/ui/*.tsx` (generated)
- Modify: none

**Interfaces:**
- Consumes: `frontend/components.json` (style `base-sera`, iconLibrary `remixicon`).
- Produces: importable primitives `@/components/ui/{input,label,select,slider,switch,radio-group,card,dialog,tabs,badge,separator}`.

- [ ] **Step 1: Add the components**

Run from `frontend/`:

```bash
npx shadcn@latest add input label select slider switch radio-group card dialog tabs badge separator
```

Accept every default. Do not answer yes to any prompt offering to overwrite `button.tsx`.

- [ ] **Step 2: Confirm what landed**

Run: `ls frontend/src/components/ui/`
Expected: `button.tsx` plus the eleven new files. If any failed to generate, add it individually — do not hand-write a substitute.

- [ ] **Step 3: Verify the build still compiles**

Run: `cd frontend && npx tsc --noEmit && npm run lint`
Expected: both clean. Nothing imports the new files yet, so nothing should change visually.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ui frontend/package.json frontend/package-lock.json
git commit -m "chore(frontend): add the base-sera primitives that were never installed"
```

---

### Task 2: The units helper

**Files:**
- Create: `frontend/src/lib/points.ts`, `frontend/src/lib/points.test.ts`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `formatPoints(points: number): string` — e.g. `1` → `"1 punto · 1 décima"`, `5` → `"5 puntos · 5 décimas · medio punto de 10"`, `-10` → `"10 puntos · un punto entero de 10"`.
  - `likeCurvePreview(exponent: number, n?: number): number` — points earned from `n` likes (default 100) at `like_value` 1.0, rounded to the nearest whole number.

**Why this exists:** the décima trap is the likeliest source of a real grading mistake, and it lives in the interface. One helper, used everywhere (spec §2.5).

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/lib/points.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { formatPoints, likeCurvePreview } from "./points";

describe("formatPoints", () => {
  it("states one point as one décima", () => {
    expect(formatPoints(1)).toBe("1 punto · 1 décima");
  });

  it("spells out a half point on the 10-scale", () => {
    expect(formatPoints(5)).toBe("5 puntos · 5 décimas · medio punto de 10");
  });

  it("describes a falta as a whole point on the 10-scale", () => {
    expect(formatPoints(-10)).toBe("10 puntos · un punto entero de 10");
  });

  it("handles a fractional value", () => {
    expect(formatPoints(0.5)).toBe("0.5 puntos · media décima");
  });

  it("handles zero", () => {
    expect(formatPoints(0)).toBe("0 puntos");
  });
});

describe("likeCurvePreview", () => {
  it("matches the engine's concave curve at the three offered exponents", () => {
    expect(likeCurvePreview(0.5)).toBe(10);    // sqrt(100)
    expect(likeCurvePreview(0.75)).toBe(32);   // 100^0.75 = 31.6
    expect(likeCurvePreview(1.0)).toBe(100);
  });

  it("accepts a different like count", () => {
    expect(likeCurvePreview(0.5, 25)).toBe(5);
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && npx vitest run src/lib/points.test.ts`
Expected: FAIL — cannot resolve `./points`.

- [ ] **Step 3: Implement**

Create `frontend/src/lib/points.ts`:

```ts
/** Points are always on the 0–100 scale. One point on that scale is one
 *  décima, which is 0.1 on the 10-scale students actually talk about.
 *  Every surface that shows a points value goes through here — getting this
 *  wrong by a factor of ten is the single most expensive UI mistake
 *  available in this app. */
export function formatPoints(points: number): string {
  const n = Math.abs(points);
  if (n === 0) return "0 puntos";

  const unit = n === 1 ? "1 punto · 1 décima" : `${n} puntos · ${n} décimas`;
  if (n === 1) return unit;
  if (n === 0.5) return "0.5 puntos · media décima";
  if (n === 5) return "5 puntos · 5 décimas · medio punto de 10";
  if (n === 10) return "10 puntos · un punto entero de 10";
  if (n % 10 === 0) return `${n} puntos · ${n / 10} puntos enteros de 10`;
  return unit;
}

/** Mirrors like_points() in backend/app/services/grades.py: the nth like is
 *  worth n^exponent − (n−1)^exponent, so the total is n^exponent. Shown to
 *  the teacher so an exponent is chosen by its consequence, not its value. */
export function likeCurvePreview(exponent: number, n = 100): number {
  return Math.round(Math.pow(n, exponent));
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd frontend && npx vitest run src/lib/points.test.ts`
Expected: PASS, 7 tests.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/points.ts frontend/src/lib/points.test.ts
git commit -m "feat(frontend): points formatting helper with décima equivalents"
```

---

### Task 3: Expose `attendance_required_pct`

**Files:**
- Modify: `backend/app/schemas.py` (`ClassSettingsUpdate`, `ClassSettingsOut`)
- Test: `backend/tests/test_class_settings.py`

**Interfaces:**
- Consumes: `Class.attendance_required_pct`, which already exists with default 80.
- Produces: `PATCH /api/classes/{id}/settings` accepting `attendance_required_pct: int` in `[0, 100]`; `GET` returning it.

**No migration** — the column is already on the table.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_class_settings.py`:

```python
def test_settings_expose_attendance_minimum(client, teacher_headers, klass):
    r = client.get(f"/api/classes/{klass.id}/settings", headers=teacher_headers)
    assert r.status_code == 200
    assert r.json()["attendance_required_pct"] == 80


def test_teacher_can_change_the_attendance_minimum(client, teacher_headers, klass):
    r = client.patch(f"/api/classes/{klass.id}/settings",
                     json={"attendance_required_pct": 70}, headers=teacher_headers)
    assert r.status_code == 200
    assert r.json()["attendance_required_pct"] == 70


def test_attendance_minimum_above_100_is_rejected(client, teacher_headers, klass):
    r = client.patch(f"/api/classes/{klass.id}/settings",
                     json={"attendance_required_pct": 140}, headers=teacher_headers)
    assert r.status_code == 422
```

If `backend/tests/test_class_settings.py` does not exist under that name, find the file containing the existing settings tests (`grep -rl "settings" backend/tests`) and append there instead.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && ../venv/bin/python -m pytest tests/ -k attendance_minimum -v`
Expected: FAIL — `KeyError: 'attendance_required_pct'`, and 422 on the PATCH because `extra='forbid'` rejects the unknown field.

- [ ] **Step 3: Implement**

In `backend/app/schemas.py`, add to `ClassSettingsUpdate`:

```python
    attendance_required_pct: Optional[int] = Field(default=None, ge=0, le=100)
```

And to `ClassSettingsOut`:

```python
    attendance_required_pct: int
```

The PATCH handler applies fields generically via `model_dump(exclude_unset=True)`; confirm that by reading it before assuming — if it assigns field by field, add the new one there too.

- [ ] **Step 4: Run the full backend suite**

Run: `cd backend && ../venv/bin/python -m pytest -q`
Expected: PASS, 197 (194 + 3).

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas.py backend/tests
git commit -m "feat(backend): expose attendance_required_pct in class settings"
```

---

### Task 4: Vetoed posts stay in the feed

**Files:**
- Modify: `backend/app/routers/posts.py:128` (`get_feed`)
- Test: `backend/tests/test_veto.py`

**Interfaces:**
- Consumes: `Post.status`, `Post.veto_reason`, the existing privacy rule in `serialize_post`.
- Produces: the feed returns posts with `status in ("active", "vetoed")` and excludes `deleted`.

**Why:** a vetoed post currently vanishes from the feed, so from the student's side their post was silently deleted with no reason given — the opposite of what 2b-1 §2.6 intended when it kept vetoed posts visible in the thread (spec §2.9).

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_veto.py`:

```python
def _feed_ids(client, headers):
    return [p["id"] for p in client.get("/api/feed", headers=headers).json()["items"]]


def test_a_vetoed_post_stays_in_the_feed(client, db, teacher_headers, auth_headers, student2_headers, enrolled):
    pid = _participacion(client, auth_headers).json()["id"]
    client.post(f"/api/posts/{pid}/veto", json={"reason": "no fue en clase"},
                headers=teacher_headers)
    assert pid in _feed_ids(client, auth_headers)        # its author sees it
    assert pid in _feed_ids(client, student2_headers)    # so does everyone else


def test_a_deleted_post_stays_out_of_the_feed(client, db, auth_headers, enrolled):
    pid = _participacion(client, auth_headers).json()["id"]
    client.delete(f"/api/posts/{pid}", headers=auth_headers)
    assert pid not in _feed_ids(client, auth_headers)


def test_the_veto_reason_in_the_feed_is_still_private(client, db, teacher_headers, auth_headers, student2_headers, enrolled):
    pid = _participacion(client, auth_headers).json()["id"]
    client.post(f"/api/posts/{pid}/veto", json={"reason": "no fue en clase"},
                headers=teacher_headers)

    def reason_for(headers):
        items = client.get("/api/feed", headers=headers).json()["items"]
        return next(p for p in items if p["id"] == pid)["veto_reason"]

    assert reason_for(auth_headers) == "no fue en clase"
    assert reason_for(student2_headers) is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && ../venv/bin/python -m pytest tests/test_veto.py -k feed -v`
Expected: FAIL — the vetoed post id is absent from the feed.

- [ ] **Step 3: Implement**

In `backend/app/routers/posts.py`, `get_feed`, change the filter:

```python
        .filter(Post.parent_id.is_(None), Post.status.in_(("active", "vetoed")))
```

Leave `serialize_post` alone — it already blanks content for non-active posts and already withholds `veto_reason` from anyone but the author and the teacher.

- [ ] **Step 4: Run the full backend suite**

Run: `cd backend && ../venv/bin/python -m pytest -q`
Expected: PASS, 200 (197 + 3).

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/posts.py backend/tests/test_veto.py
git commit -m "feat(backend): vetoed posts stay visible in the feed"
```

---

### Task 5: The feed stops re-sorting under your thumb

**Files:**
- Modify: `frontend/src/lib/likes.ts:55-58`
- Test: `frontend/src/lib/feed.test.ts`

**Interfaces:**
- Consumes: `mergePages` from `frontend/src/lib/feed.ts`.
- Produces: no new exports. The like mutation no longer invalidates `["feed"]`.

**Why:** `onSettled` invalidates the whole feed query, forcing a refetch — and the server has just bumped `last_activity_at`, so the liked post returns at the top and the list jumps. The `onMutate` optimistic patch already applies the correct state in place (spec §2.8).

- [ ] **Step 1: Write the failing test**

Append to `frontend/src/lib/feed.test.ts`:

```ts
import { mergePages } from "./feed";

describe("feed order stability", () => {
  it("keeps the order of the first page when a later page repeats a post", () => {
    // The server bumped post 2 to the top of page 2 after we loaded page 1.
    // mergePages must keep our original position and not duplicate it.
    const page1 = { items: [post(1), post(2), post(3)], next_cursor: "c" };
    const page2 = { items: [post(2), post(4)], next_cursor: null };
    const merged = mergePages([page1, page2]);
    expect(merged.map((p) => p.id)).toEqual([1, 2, 3, 4]);
  });
});
```

- [ ] **Step 2: Run the test to verify it passes already**

Run: `cd frontend && npx vitest run src/lib/feed.test.ts`
Expected: PASS. This one is a **characterisation test** — it pins behaviour that already works so the next step can't quietly break it. That is why it does not fail first.

- [ ] **Step 3: Remove the invalidation**

In `frontend/src/lib/likes.ts`, replace the `onSettled` block:

```ts
    onSettled: () => {
      // Deliberately NOT invalidating ["feed"]: the server bumps
      // last_activity_at on a like, so a refetch would re-sort the list and
      // yank the post to the top while the user is reading. onMutate above
      // already applied the correct like state in place. The feed re-sorts
      // only on an explicit refresh.
      void qc.invalidateQueries({ queryKey: ["thread"] });
    },
```

- [ ] **Step 4: Verify**

Run: `cd frontend && npx vitest run && npx tsc --noEmit && npm run lint`
Expected: all pass.

- [ ] **Step 5: Check it by hand**

Start both servers, open the feed as a student, and like a post that is not at the top. Confirm the heart fills, the count rises, and **the post does not move**. Reload and confirm it is now at the top — the bump still happened server-side.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/likes.ts frontend/src/lib/feed.test.ts
git commit -m "fix(frontend): liking no longer re-sorts the feed under you"
```

---

### Task 6: Settings index

**Files:**
- Create: `frontend/src/pages/configurar/Index.tsx`, `frontend/src/components/SettingsRow.tsx`
- Modify: `frontend/src/App.tsx`, `frontend/src/strings/es.ts`

**Interfaces:**
- Consumes: `GET /api/classes/mine`, `GET /api/classes/{id}/settings`, primitives from Task 1.
- Produces: route `/configurar` rendering the index; `<SettingsRow icon={ReactNode} name={string} summary={string} to={string} />` reused by every group page's parent list.

- [ ] **Step 1: Add the strings**

Replace the whole `configurar` block in `frontend/src/strings/es.ts` with:

```ts
  configurar: {
    title: "Configuración",
    empty: "Sin clases asignadas.",
    save: "Guardar",
    saved: "Guardado",
    saveError: "No se pudo guardar",
    back: "Atrás",
    groupPesos: "Pesos de la calificación",
    groupForo: "Puntos del foro",
    groupExtras: "Puntos extra",
    groupAsistencia: "Asistencia",
    groupSalvando: "Salvando el semestre",
    groupClase: "Editar clase",
    summaryPesos: "Tareas {t} · Exámenes {e}",
    summaryForo: "Like {v} · curva {c}",
    summaryExtras: "{n} tipos configurados",
    summaryAsistencia: "Mínimo {p}% · falta −10",
    summarySalvando: "Inactivo",
    curvaFuerte: "Fuerte",
    curvaSuave: "Suave",
    curvaLineal: "Lineal",
    curvaPreview: "100 likes = {n} puntos",
    curvaHelp: "Cada like nuevo vale menos que el anterior.",
    pesosTareas: "Peso de tareas",
    pesosExamenes: "Peso de exámenes",
    pesosRest: "El resto de la calificación sale de participaciones, likes y puntos extra, que no tienen tope.",
    likeValue: "Puntos base por like",
    curvaLabel: "Curva de likes",
    asistenciaMin: "Asistencia mínima",
    asistenciaMinHelp: "Debajo de esto, el alumno no exenta",
    faltaCost: "Costo de una falta",
    retardoRule: "Retardo",
    retardoRuleValue: "No resta puntos",
    salvandoTitle: "Salvando el semestre",
    salvandoBody: "Un periodo en el que todo lo que se gana en el foro cuenta doble. Sirve para reactivar la clase cuando el semestre se está apagando.",
    salvandoSoon: "Próximamente",
    incentivesTitle: "Puntos extra",
    incentiveName: "Nombre",
    incentivePoints: "Puntos",
    incentiveAdd: "Agregar",
    incentiveNone: "Aún no hay puntos extra configurados.",
    incentiveDelete: "Eliminar",
    incentiveDeleteConfirm: "¿Eliminar este tipo de punto extra?",
    incentiveDeleteBody: "Si ya lo otorgaste, quedará oculto pero los puntos que diste se conservan.",
    incentiveAward: "Otorgar",
    incentiveAwardTitle: "Otorgar puntos extra",
    incentivePickStudent: "Selecciona un alumno",
    incentiveAwarded: "Puntos otorgados",
    cancel: "Cancelar",
    claseName: "Nombre de la clase",
    claseStart: "Inicio",
    claseEnd: "Fin",
  },
```

- [ ] **Step 2: Build the row component**

Create `frontend/src/components/SettingsRow.tsx`:

```tsx
import { Link } from "react-router-dom";
import { RiArrowRightSLine } from "@remixicon/react";

export default function SettingsRow({
  icon, name, summary, to,
}: { icon: React.ReactNode; name: string; summary: string; to: string }) {
  return (
    <Link to={to} className="flex items-center gap-3 border-b px-1 py-3 last:border-b-0">
      <span className="flex size-8 shrink-0 items-center justify-center bg-muted text-muted-foreground">
        {icon}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-sm font-semibold">{name}</span>
        <span className="block truncate text-xs text-muted-foreground">{summary}</span>
      </span>
      <RiArrowRightSLine className="size-4 text-muted-foreground" />
    </Link>
  );
}
```

- [ ] **Step 3: Build the index**

Create `frontend/src/pages/configurar/Index.tsx`:

```tsx
import { useQuery } from "@tanstack/react-query";
import {
  RiScales3Line, RiHeartLine, RiSparkling2Line, RiCheckboxCircleLine,
  RiFlashlightLine, RiEditLine,
} from "@remixicon/react";
import { api } from "@/lib/api";
import SettingsRow from "@/components/SettingsRow";
import { es } from "@/strings/es";
import type { ClassSettings, MyClasses } from "@/lib/types";

export default function ConfigurarIndex() {
  const mine = useQuery({
    queryKey: ["classes-mine"],
    queryFn: () => api<MyClasses>("/api/classes/mine"),
  });
  const klass = mine.data?.teaching?.[0];

  const settings = useQuery({
    queryKey: ["settings", klass?.id],
    queryFn: () => api<ClassSettings>(`/api/classes/${klass!.id}/settings`),
    enabled: klass != null,
  });

  if (mine.isPending) return <p className="p-4 text-muted-foreground">{es.common.loading}</p>;
  if (klass == null) return <p className="p-4 text-muted-foreground">{es.configurar.empty}</p>;

  const s = settings.data;
  const curva = s == null ? "—"
    : Number(s.like_exponent) >= 1 ? es.configurar.curvaLineal
    : Number(s.like_exponent) >= 0.75 ? es.configurar.curvaSuave
    : es.configurar.curvaFuerte;

  return (
    <main className="mx-auto max-w-md p-4">
      <h1 className="mb-3 text-sm font-semibold tracking-widest uppercase">
        {es.configurar.title}
      </h1>
      <SettingsRow
        icon={<RiScales3Line className="size-4" />}
        name={es.configurar.groupPesos}
        summary={s ? es.configurar.summaryPesos
          .replace("{t}", String(s.tareas_weight))
          .replace("{e}", String(s.examenes_weight)) : "—"}
        to="/configurar/pesos"
      />
      <SettingsRow
        icon={<RiHeartLine className="size-4" />}
        name={es.configurar.groupForo}
        summary={s ? es.configurar.summaryForo
          .replace("{v}", String(s.like_value))
          .replace("{c}", curva.toLowerCase()) : "—"}
        to="/configurar/foro"
      />
      <SettingsRow
        icon={<RiSparkling2Line className="size-4" />}
        name={es.configurar.groupExtras}
        summary=""
        to="/configurar/extras"
      />
      <SettingsRow
        icon={<RiCheckboxCircleLine className="size-4" />}
        name={es.configurar.groupAsistencia}
        summary={s ? es.configurar.summaryAsistencia
          .replace("{p}", String(s.attendance_required_pct)) : "—"}
        to="/configurar/asistencia"
      />
      <SettingsRow
        icon={<RiFlashlightLine className="size-4" />}
        name={es.configurar.groupSalvando}
        summary={es.configurar.summarySalvando}
        to="/configurar/salvando"
      />
      <SettingsRow
        icon={<RiEditLine className="size-4" />}
        name={es.configurar.groupClase}
        summary={klass.name}
        to="/configurar/clase"
      />
    </main>
  );
}
```

Extend `ClassSettings` in `frontend/src/lib/types.ts` with `attendance_required_pct: number` (Task 3 added it to the API). If the interface has a different name, find it with `grep -n "like_exponent" frontend/src/lib/types.ts` and extend that one.

- [ ] **Step 4: Route it**

In `frontend/src/App.tsx`, change the `/configurar` import and route to the new index, keeping the existing `RequireAuth` + `Shell` wrapper shape used by `/revisar`:

```tsx
import ConfigurarIndex from "@/pages/configurar/Index";
```

```tsx
            <Route
              path="/configurar"
              element={<RequireAuth><Shell><ConfigurarIndex /></Shell></RequireAuth>}
            />
```

Leave the old `Configurar.tsx` file in place for now — Tasks 7–11 replace its contents group by group, and deleting it early would break the build.

- [ ] **Step 5: Verify**

Run: `cd frontend && npx tsc --noEmit && npm run lint`
Expected: clean. The six rows render; five of them lead nowhere until the next tasks.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/configurar frontend/src/components/SettingsRow.tsx frontend/src/App.tsx frontend/src/strings/es.ts frontend/src/lib/types.ts
git commit -m "feat(frontend): settings index of groups"
```

---

### Task 7: Pesos page

**Files:**
- Create: `frontend/src/pages/configurar/Pesos.tsx`, `frontend/src/components/SettingsPage.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: `PATCH /api/classes/{id}/settings`, `Card`, `Input`, `Label`, `Button`.
- Produces: `<SettingsPage title={string} children>` — a titled sub-page with a back link, reused by Tasks 8–11.

- [ ] **Step 1: Build the shared sub-page shell**

Create `frontend/src/components/SettingsPage.tsx`:

```tsx
import { Link } from "react-router-dom";
import { RiArrowLeftSLine } from "@remixicon/react";
import { es } from "@/strings/es";

export default function SettingsPage({
  title, children,
}: { title: string; children: React.ReactNode }) {
  return (
    <main className="mx-auto max-w-md p-4">
      <Link to="/configurar"
            className="mb-3 inline-flex items-center gap-1 text-xs text-muted-foreground">
        <RiArrowLeftSLine className="size-4" /> {es.configurar.back}
      </Link>
      <h1 className="mb-4 text-sm font-semibold tracking-widest uppercase">{title}</h1>
      <div className="flex flex-col gap-3">{children}</div>
    </main>
  );
}
```

- [ ] **Step 2: Build the page**

Create `frontend/src/pages/configurar/Pesos.tsx`:

```tsx
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import SettingsPage from "@/components/SettingsPage";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/components/Toaster";
import { es } from "@/strings/es";
import type { ClassSettings, MyClasses } from "@/lib/types";

export default function Pesos() {
  const qc = useQueryClient();
  const toast = useToast();
  const mine = useQuery({ queryKey: ["classes-mine"],
                          queryFn: () => api<MyClasses>("/api/classes/mine") });
  const klass = mine.data?.teaching?.[0];
  const q = useQuery({
    queryKey: ["settings", klass?.id],
    queryFn: () => api<ClassSettings>(`/api/classes/${klass!.id}/settings`),
    enabled: klass != null,
  });

  const [tareas, setTareas] = useState<string | null>(null);
  const [examenes, setExamenes] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: (body: Record<string, number>) =>
      api<ClassSettings>(`/api/classes/${klass!.id}/settings`, {
        method: "PATCH", body: JSON.stringify(body),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["settings"] });
      void qc.invalidateQueries({ queryKey: ["grade"] });
      toast.show(es.configurar.saved);
    },
    onError: () => toast.show(es.configurar.saveError),
  });

  if (q.isPending || klass == null)
    return <SettingsPage title={es.configurar.groupPesos}>
             <p className="text-muted-foreground">{es.common.loading}</p>
           </SettingsPage>;

  const t = tareas ?? String(q.data.tareas_weight);
  const e = examenes ?? String(q.data.examenes_weight);

  return (
    <SettingsPage title={es.configurar.groupPesos}>
      <Card className="p-4">
        <Label htmlFor="w-tareas">{es.configurar.pesosTareas}</Label>
        <Input id="w-tareas" type="number" inputMode="numeric" min={0} max={100}
               className="mt-2" value={t} onChange={(ev) => setTareas(ev.target.value)} />
      </Card>
      <Card className="p-4">
        <Label htmlFor="w-examenes">{es.configurar.pesosExamenes}</Label>
        <Input id="w-examenes" type="number" inputMode="numeric" min={0} max={100}
               className="mt-2" value={e} onChange={(ev) => setExamenes(ev.target.value)} />
      </Card>
      {/* Deliberately NOT a warning: the weights are not supposed to reach 100.
          The gap is filled by uncapped participaciones and extras. */}
      <p className="text-xs text-muted-foreground">{es.configurar.pesosRest}</p>
      <Button
        disabled={save.isPending}
        onClick={() => save.mutate({ tareas_weight: Number(t), examenes_weight: Number(e) })}
      >
        {es.configurar.save}
      </Button>
    </SettingsPage>
  );
}
```

`es.configurar.save` was added to the strings block in Task 6.

- [ ] **Step 3: Route it**

In `frontend/src/App.tsx`, add alongside `/configurar`:

```tsx
            <Route
              path="/configurar/pesos"
              element={<RequireAuth><Shell><Pesos /></Shell></RequireAuth>}
            />
```

- [ ] **Step 4: Verify**

Run: `cd frontend && npx tsc --noEmit && npm run lint`
Expected: clean.

- [ ] **Step 5: Check it by hand**

At a 390 px viewport: two cards, one field each, one per line. Change a weight, save, reload, confirm it persisted. Confirm there is no warning anywhere about the weights not summing to 100.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/configurar/Pesos.tsx frontend/src/components/SettingsPage.tsx frontend/src/App.tsx frontend/src/strings/es.ts
git commit -m "feat(frontend): pesos settings page"
```

---

### Task 8: Foro page — slider and curve presets

**Files:**
- Create: `frontend/src/pages/configurar/Foro.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: `likeCurvePreview` and `formatPoints` from Task 2, `SettingsPage` from Task 7, `Slider` and `RadioGroup` from Task 1.
- Produces: route `/configurar/foro`.

- [ ] **Step 1: Build the page**

Create `frontend/src/pages/configurar/Foro.tsx`:

```tsx
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import SettingsPage from "@/components/SettingsPage";
import { Card } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { useToast } from "@/components/Toaster";
import { formatPoints, likeCurvePreview } from "@/lib/points";
import { es } from "@/strings/es";
import type { ClassSettings, MyClasses } from "@/lib/types";

const CURVES = [
  { value: "0.5", label: es.configurar.curvaFuerte },
  { value: "0.75", label: es.configurar.curvaSuave },
  { value: "1", label: es.configurar.curvaLineal },
];

export default function Foro() {
  const qc = useQueryClient();
  const toast = useToast();
  const mine = useQuery({ queryKey: ["classes-mine"],
                          queryFn: () => api<MyClasses>("/api/classes/mine") });
  const klass = mine.data?.teaching?.[0];
  const q = useQuery({
    queryKey: ["settings", klass?.id],
    queryFn: () => api<ClassSettings>(`/api/classes/${klass!.id}/settings`),
    enabled: klass != null,
  });

  const [draft, setDraft] = useState<number | null>(null);

  const save = useMutation({
    mutationFn: (body: Record<string, number>) =>
      api<ClassSettings>(`/api/classes/${klass!.id}/settings`, {
        method: "PATCH", body: JSON.stringify(body),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["settings"] });
      void qc.invalidateQueries({ queryKey: ["grade"] });
      toast.show(es.configurar.saved);
    },
    onError: () => toast.show(es.configurar.saveError),
  });

  if (q.isPending || klass == null)
    return <SettingsPage title={es.configurar.groupForo}>
             <p className="text-muted-foreground">{es.common.loading}</p>
           </SettingsPage>;

  const likeValue = draft ?? Number(q.data.like_value);
  const exponent = String(Number(q.data.like_exponent));

  return (
    <SettingsPage title={es.configurar.groupForo}>
      <Card className="p-4">
        <Label>{es.configurar.likeValue}</Label>
        <p className="mt-1 text-3xl font-semibold tabular-nums">{likeValue.toFixed(1)}</p>
        <p className="text-xs text-muted-foreground">{formatPoints(likeValue)}</p>
        <Slider
          className="mt-4"
          min={0.5} max={5} step={0.5}
          value={[likeValue]}
          onValueChange={(v: number[]) => setDraft(v[0])}
          onValueCommit={(v: number[]) => save.mutate({ like_value: v[0] })}
        />
      </Card>

      <Card className="p-4">
        <Label>{es.configurar.curvaLabel}</Label>
        <RadioGroup
          className="mt-3"
          value={exponent}
          onValueChange={(v: string) => save.mutate({ like_exponent: Number(v) })}
        >
          {CURVES.map((c) => (
            <div key={c.value} className="flex items-start gap-3 border-t py-3 first:border-t-0">
              <RadioGroupItem value={c.value} id={`curve-${c.value}`} className="mt-1" />
              <Label htmlFor={`curve-${c.value}`} className="flex flex-col items-start gap-0.5">
                <span className="text-sm font-medium">{c.label}</span>
                {/* Computed from the same maths as the engine — never a hardcoded string. */}
                <span className="text-xs text-muted-foreground">
                  {es.configurar.curvaPreview
                    .replace("{n}", String(likeCurvePreview(Number(c.value))))}
                </span>
              </Label>
            </div>
          ))}
        </RadioGroup>
        <p className="mt-2 text-xs text-muted-foreground">{es.configurar.curvaHelp}</p>
      </Card>
    </SettingsPage>
  );
}
```

If the generated `slider.tsx` or `radio-group.tsx` exports different prop names (`onValueCommit` in particular varies), read the generated file and adapt the call site — **do not** edit the primitive.

- [ ] **Step 2: Route it**

```tsx
            <Route
              path="/configurar/foro"
              element={<RequireAuth><Shell><Foro /></Shell></RequireAuth>}
            />
```

- [ ] **Step 3: Verify**

Run: `cd frontend && npx tsc --noEmit && npm run lint && npx vitest run`
Expected: all clean.

- [ ] **Step 4: Check it by hand**

Confirm the slider never opens the keyboard, that the three curve options read 10 / 32 / 100, that picking one saves immediately, and that a student's grade chip reflects a changed like value after refresh.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/configurar/Foro.tsx frontend/src/App.tsx
git commit -m "feat(frontend): foro settings with slider and curve presets"
```

---

### Task 9: Extras page — incentives

**Files:**
- Create: `frontend/src/pages/configurar/Extras.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: the existing incentive endpoints already built in 2b-2 (`GET`/`POST`/`DELETE /api/classes/{id}/incentives`, award endpoint), `formatPoints` from Task 2, `Dialog` from Task 1.
- Produces: route `/configurar/extras`.

- [ ] **Step 1: Read the existing implementation first**

Run: `grep -n "incentive" frontend/src/pages/Configurar.tsx`

The 2b-2 code already has working create, delete-with-confirmation and award-with-student-picker logic against the real endpoints. **Port that logic**; this task replaces its presentation, not its behaviour. Copy the exact endpoint paths and payload shapes from there rather than guessing them.

- [ ] **Step 2: Build the page**

Create `frontend/src/pages/configurar/Extras.tsx`. The create form is a `Card`, one control per line, with the units shown live as the teacher types — this is the field where the décima confusion actually costs a grade:

```tsx
      <Card className="p-4">
        <Label htmlFor="inc-name">{es.configurar.incentiveName}</Label>
        <Input id="inc-name" className="mt-2" value={name}
               onChange={(e) => setName(e.target.value)} />

        <Label htmlFor="inc-points" className="mt-4 block">
          {es.configurar.incentivePoints}
        </Label>
        <Input id="inc-points" type="number" inputMode="numeric" min={0} className="mt-2"
               value={points} onChange={(e) => setPoints(e.target.value)} />
        {points !== "" && (
          <p className="mt-1 text-xs text-muted-foreground">
            {formatPoints(Number(points))}
          </p>
        )}

        <Button className="mt-4 w-full" disabled={!name.trim() || points === ""}
                onClick={() => create.mutate({ name: name.trim(), points: Number(points) })}>
          {es.configurar.incentiveAdd}
        </Button>
      </Card>
```

Each incentive is a **compact row**, not a card — a name and a number explain themselves (spec §2.3):

```tsx
      {incentives.length === 0 && (
        <p className="text-sm text-muted-foreground">{es.configurar.incentiveNone}</p>
      )}
      {incentives.map((inc) => (
        <div key={inc.id} className="flex items-center justify-between gap-3 border-b py-3">
          <span className="min-w-0">
            <span className="block truncate text-sm font-medium">{inc.name}</span>
            <span className="block text-xs text-muted-foreground">
              {formatPoints(Number(inc.points))}
            </span>
          </span>
          <span className="flex shrink-0 gap-1">
            <Button variant="ghost" size="sm" onClick={() => setAwarding(inc)}>
              {es.configurar.incentiveAward}
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setDeleting(inc)}>
              {es.configurar.incentiveDelete}
            </Button>
          </span>
        </div>
      ))}
```

Delete uses `Dialog` titled `incentiveDeleteConfirm` with `incentiveDeleteBody`, and award uses `Dialog` with a `Select` of active students.

**Port the mutations from the existing page rather than rewriting them** — `Configurar.tsx` already has working create, soft-delete and award calls against the real endpoints. Copy the exact paths, payload shapes and query keys from there so the cache stays coherent and the soft-delete semantics survive.

- [ ] **Step 3: Route it**

```tsx
            <Route
              path="/configurar/extras"
              element={<RequireAuth><Shell><Extras /></Shell></RequireAuth>}
            />
```

- [ ] **Step 4: Verify**

Run: `cd frontend && npx tsc --noEmit && npm run lint`
Expected: clean.

- [ ] **Step 5: Check it by hand**

Create an incentive worth 5 points and confirm the form says "5 puntos · 5 décimas · medio punto de 10" **as you type**. Award it to a student and confirm their grade chip rises by 5. Delete an awarded incentive and confirm the student keeps the points.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/configurar/Extras.tsx frontend/src/App.tsx
git commit -m "feat(frontend): puntos extra page with explicit units"
```

---

### Task 10: Asistencia page

**Files:**
- Create: `frontend/src/pages/configurar/Asistencia.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: `attendance_required_pct` from Task 3, `formatPoints` from Task 2, `Slider` from Task 1.
- Produces: route `/configurar/asistencia`.

- [ ] **Step 1: Build the page**

Create `frontend/src/pages/configurar/Asistencia.tsx`. One card and two read-only rows, following the pattern established in Task 8 for loading the class and settings and for the save mutation:

```tsx
      <Card className="p-4">
        <Label>{es.configurar.asistenciaMin}</Label>
        <p className="mt-1 text-3xl font-semibold tabular-nums">{pct}%</p>
        <p className="text-xs text-muted-foreground">{es.configurar.asistenciaMinHelp}</p>
        <Slider
          className="mt-4"
          min={0} max={100} step={5}
          value={[pct]}
          onValueChange={(v: number[]) => setDraft(v[0])}
          onValueCommit={(v: number[]) => save.mutate({ attendance_required_pct: v[0] })}
        />
      </Card>

      <div>
        <p className="mb-1 text-[10px] font-semibold tracking-widest uppercase text-muted-foreground">
          {es.configurar.rulesHeader}
        </p>
        <div className="flex items-center justify-between border-b py-3">
          <span className="text-sm font-medium">{es.configurar.faltaCost}</span>
          <span className="text-sm tabular-nums">−10</span>
        </div>
        <p className="pb-3 text-xs text-muted-foreground">{formatPoints(-10)}</p>
        <div className="flex items-center justify-between py-3">
          <span className="text-sm font-medium">{es.configurar.retardoRule}</span>
          <span className="text-sm text-muted-foreground">{es.configurar.retardoRuleValue}</span>
        </div>
      </div>
```

Add `rulesHeader: "Reglas"` to the `configurar` strings.

**There is deliberately no switch here.** Making "un retardo cuenta como falta" configurable would need a new column and a grade-engine branch — a feature, not a design change (spec §2.3). The row states current behaviour only.

- [ ] **Step 2: Route it**

```tsx
            <Route
              path="/configurar/asistencia"
              element={<RequireAuth><Shell><Asistencia /></Shell></RequireAuth>}
            />
```

- [ ] **Step 3: Verify**

Run: `cd frontend && npx tsc --noEmit && npm run lint`
Expected: clean.

- [ ] **Step 4: Check it by hand**

Move the slider, confirm it saves on release and survives a reload. Confirm the falta row reads "10 puntos · un punto entero de 10".

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/configurar/Asistencia.tsx frontend/src/App.tsx frontend/src/strings/es.ts
git commit -m "feat(frontend): asistencia settings page"
```

---

### Task 11: Salvando and Clase pages, then delete the old file

**Files:**
- Create: `frontend/src/pages/configurar/Salvando.tsx`, `frontend/src/pages/configurar/Clase.tsx`
- Delete: `frontend/src/pages/Configurar.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: `PATCH /api/classes/{id}/settings` for the class fields it supports; `SettingsPage` from Task 7.
- Produces: routes `/configurar/salvando` and `/configurar/clase`.

- [ ] **Step 1: Build the Salvando slot**

Create `frontend/src/pages/configurar/Salvando.tsx` — explanation plus a disabled control:

```tsx
export default function Salvando() {
  return (
    <SettingsPage title={es.configurar.salvandoTitle}>
      <Card className="p-4">
        <p className="text-sm">{es.configurar.salvandoBody}</p>
        <Button disabled className="mt-4 w-full">{es.configurar.salvandoSoon}</Button>
      </Card>
    </SettingsPage>
  );
}
```

The mechanic — multipliers, retroactive or forward, randomness — is **not** in this pass. It touches the grade engine and needs its own spec (spec §5).

- [ ] **Step 2: Build the Clase page**

Create `frontend/src/pages/configurar/Clase.tsx` with the class name, start date and end date, one `Card` per field, following Task 7's save pattern.

Before writing the mutation, check which of these the API actually accepts: run `grep -n "class ClassSettingsUpdate" -A 12 backend/app/schemas.py`. `ClassSettingsUpdate` carries weights and point values only. If name and dates are not accepted, render them **read-only** with a note, and record the gap in `planning/future.md` as "editar nombre y fechas de la clase" rather than inventing an endpoint — adding one is backend scope this pass does not have.

- [ ] **Step 3: Route both and drop the old page**

Add both routes following the established shape, then:

```bash
git rm frontend/src/pages/Configurar.tsx
```

Confirm nothing still imports it: `grep -rn "pages/Configurar" frontend/src`

- [ ] **Step 4: Verify**

Run: `cd frontend && npx tsc --noEmit && npm run lint && npx vitest run`
Expected: all clean, no dangling imports.

- [ ] **Step 5: Check it by hand**

Walk the whole index: six rows, each opening its own page, each page one control per line, back link everywhere. Confirm no page opens the keyboard except Pesos, Extras' name and points fields, and Clase.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat(frontend): salvando slot and clase page, retire the old Configurar"
```

---

### Task 12: Revisar shows only what's pending

**Files:**
- Modify: `frontend/src/pages/Revisar.tsx`
- Test: manual

**Interfaces:**
- Consumes: `GET /api/review/participaciones`, `setVeto` from `frontend/src/lib/review.ts`.
- Produces: no new exports.

- [ ] **Step 1: Filter the list and add the toggle**

In the participaciones tab, hold a filter state:

```tsx
  const [showHandled, setShowHandled] = useState(false);
```

Render a `Tabs` or two `Button variant="ghost" size="sm"` controls for pending vs `Vistas`, and filter the rendered rows:

```tsx
  const rows = q.data.items.filter((i) => (showHandled ? i.vetoed : !i.vetoed));
```

The optimistic veto mutation already patches the row's `vetoed` flag, so a vetoed row leaves the pending list on its own with no extra work — that is the behaviour the spec asks for (§2.10). Keep the existing rollback on error.

- [ ] **Step 2: Re-skin the tabs and rows**

Replace the hand-rolled tab buttons with the `Tabs` primitive and the veto button with `Button variant="destructive" size="sm"`. Replace any emoji with a remixicon glyph.

- [ ] **Step 3: Verify**

Run: `cd frontend && npx tsc --noEmit && npm run lint && npx vitest run`
Expected: clean.

- [ ] **Step 4: Check it by hand**

Veto a participación and confirm the row leaves the list immediately; switch to Vistas and confirm it is there; un-veto and confirm it returns to pending. Kill the backend and veto again to confirm the row visibly comes back with a toast.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Revisar.tsx
git commit -m "feat(frontend): Revisar participaciones shows only what's pending"
```

---

### Task 13: Re-skin the teacher surfaces

**Files:**
- Modify: `frontend/src/pages/Revisar.tsx`, `frontend/src/pages/ClassPanel.tsx`, `frontend/src/pages/PasarLista.tsx`, `frontend/src/components/ReviewSheet.tsx`, `frontend/src/components/ExamenRoster.tsx`

**Interfaces:**
- Consumes: primitives from Task 1.
- Produces: no new exports.

- [ ] **Step 1: Replace controls, one file at a time**

For each file: every raw `<input>` becomes `Input`, every `<select>` becomes `Select`, every hand-rolled bordered `<div>` that wraps a settings-like block becomes `Card`, every modal becomes `Dialog`, every emoji becomes a remixicon glyph. Every `<button className="rounded-full …">` becomes `Button` with the appropriate variant.

**Preserve the list-row exception:** the examen roster and pasar lista keep the student name and their control on one aligned row (spec §2.2). Do not stack them.

- [ ] **Step 2: Verify after each file**

Run: `cd frontend && npx tsc --noEmit && npm run lint`
Expected: clean after each. Commit per file rather than in one lump, so a regression is bisectable.

- [ ] **Step 3: Check it by hand**

At 390 px: grade an entrega from Revisar, enter a roster of exam scores, take attendance end to end. Nothing may require horizontal scrolling.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/Revisar.tsx frontend/src/pages/ClassPanel.tsx frontend/src/pages/PasarLista.tsx frontend/src/components
git commit -m "refactor(frontend): teacher surfaces on the preset primitives"
```

---

### Task 14: Re-skin the student surfaces

**Files:**
- Modify: `frontend/src/pages/Home.tsx`, `frontend/src/pages/Thread.tsx`, `frontend/src/pages/Compose.tsx`, `frontend/src/pages/Classes.tsx`, `frontend/src/components/PostCard.tsx`, `frontend/src/components/GradeChip.tsx`, `frontend/src/components/Shell.tsx`

**Interfaces:**
- Consumes: primitives from Task 1, `formatPoints` from Task 2.
- Produces: no new exports.

- [ ] **Step 1: Post badges become icons**

In `PostCard.tsx`, replace the emoji badges with `Badge` plus a remixicon glyph: 📌 tarea → `RiPushpinLine`, ✅ entrega → `RiCheckLine`, 📝 examen → `RiFileTextLine`, 🗣️ participación → `RiChat3Line`.

**Keep 👻 and 🥷** wherever enrollment status is shown — those two survive deliberately (spec §2.7).

- [ ] **Step 2: A vetoed post reads clearly**

Task 4 made vetoed posts appear in the feed. Render them with a muted treatment and a `Badge variant="destructive"` reading `es.post.vetoedNotice`, with `veto_reason` beneath it when present. The server only sends the reason to its author, so no role check belongs here.

- [ ] **Step 3: Grade breakdown uses the units helper**

In `GradeChip.tsx`, every points figure goes through `formatPoints`. The faltas line must read as a whole point on the 10-scale, not as a bare −10.

- [ ] **Step 4: The composer and the rest**

`Compose.tsx`: mode selector becomes `Tabs`, the class picker becomes `Select`, the due-date field keeps `type="datetime-local"` inside `Input`, the textarea keeps its shape. `Shell.tsx`: nav emojis become remixicon glyphs.

- [ ] **Step 5: Verify**

Run: `cd frontend && npx tsc --noEmit && npm run lint && npx vitest run && npm run build`
Expected: all clean.

- [ ] **Step 6: Check it by hand**

At 390 px, as a student: read the feed, like something and confirm it does not jump, open a thread, submit an entrega, read the grade breakdown. As the teacher: confirm a vetoed post is visible with its marker and that a classmate cannot see its reason.

- [ ] **Step 7: Commit**

```bash
git add frontend/src
git commit -m "refactor(frontend): student surfaces on the preset primitives"
```

---

### Task 15: Close out

**Files:**
- Modify: `planning/changelog.md`, `CLAUDE.md`, `planning/future.md`

- [ ] **Step 1: Run everything**

```bash
cd backend && ../venv/bin/python -m pytest -q
cd ../frontend && npx vitest run && npx tsc --noEmit && npm run lint && npm run build
```

Expected: backend 200, frontend green. Record the real numbers.

- [ ] **Step 2: Grep for leftovers**

```bash
grep -rn "rounded-md border px-2 py-1" frontend/src   # hand-rolled inputs
grep -rn "📌\|✅\|🗣️\|📝\|⚖\|⚡" frontend/src         # emojis that should be icons
grep -rn "lucide" frontend/                            # must return nothing
```

Expected: the first two return nothing outside 👻/🥷 usages; the third returns nothing at all. Fix anything that turns up before finishing.

- [ ] **Step 3: Update CLAUDE.md**

The Tech Stack line says "React + Vite + shadcn (preset `b3SkwD0Ou`)". Correct it to name the real configuration: shadcn style `base-sera`, base color zinc, icons from `@remixicon/react`, primitives used untouched. Add a line to Development Rules: **use the preset components as they arrive; never restyle a primitive.**

- [ ] **Step 4: Write the changelog entry**

Add a dated Spanish entry at the top of `planning/changelog.md`: what changed visually, the settings architecture, the four behaviour fixes, and the two findings worth remembering — that the design system was configured but never used, and that the like-invalidation was what made the feed jump. Record any gap parked in `future.md` from Task 11.

- [ ] **Step 5: Commit**

```bash
git add planning/ CLAUDE.md
git commit -m "docs: close out the design pass"
```

---

## Notes for the reviewer

- The rule that matters most: **primitives are used as they arrive**. A task that edits `--radius`, strips `uppercase`, or wraps a primitive to restyle it has missed the point of the whole pass (spec §2.2b).
- Tasks 3 and 4 are the only backend changes. If the test count moves for any other reason, something unintended happened.
- Task 5 is a deletion, not an addition. Resist the urge to add a refetch somewhere else to compensate.
- Nothing here deploys. `main` stays as it is while students are using it mid-semester.
