# Design Pass — Sistema visual y arquitectura de configuración: Design Spec

Approved 2026-08-01. Source of truth for the design-pass implementation plan. Branch: `design-pass`.

This pass exists because the app works and doesn't feel like one product. Phases 0–3 shipped functionality fast; the visual layer was never designed, only improvised per page. This spec fixes the cause, not the symptoms.

**Nothing here changes what the app computes.** The grade engine and the ledger are untouched. Two deliberate behaviour changes reach the backend — the feed stops hiding vetoed posts (§2.9) and the class-settings schema gains `attendance_required_pct` (§3) — and nothing else. No migration.

## 1. Why this is needed

The design system was **configured and then never used**. `frontend/components.json` sets shadcn style `base-sera`, base color zinc, icon library `remixicon`; `index.css` imports `shadcn/tailwind.css` with the full token set and the Geist variable font; `@remixicon/react`, `@base-ui/react` and the `shadcn` CLI are all already dependencies.

But `frontend/src/components/ui/` contains exactly one file, `button.tsx`. No `input`, `select`, `card`, `dialog` or `slider` was ever added. So every form control in the app is a hand-rolled `<input className="rounded-md border px-2 py-1">`, and every icon is an emoji — not because the tools were missing, but because nobody reached for them.

`Configurar.tsx` shows the consequence most clearly: a single `field()` helper renders five settings into a two-column grid, giving a percentage weight, a point value and a mathematical exponent the identical control with no indication that they are different kinds of thing. That page is not badly styled. It is unstructured.

## 2. Decisions

### 2.1 Configuration is an architecture, not a page

`/configurar` becomes an **index of groups**. Each row shows an icon, the group name, and a one-line summary of its current state; tapping opens that group's own page. Nothing is editable on the index.

The purpose is to not confront the teacher with every decision in the app the moment they open settings. A group page shows only its own controls.

### 2.2 One control per line

In any form or settings surface, one thing per line. No two controls side by side, ever.

**Consulted exception:** list screens where each row is "who" plus "what you're setting" — the examen roster (student → score) and pasar lista (student → P/F/T) — keep name and control on one aligned row. Stacking them would double the scrolling for forty students. This exception covers list rows only and does not extend to forms.

### 2.2b The preset is adopted untouched

Components come from `npx shadcn add` and are used **as they arrive**. No token overrides, no editing `--radius`, no stripping `uppercase` from the button variants, no bespoke wrappers that re-style a primitive.

`base-sera` is angular, uppercase-labelled and typographically technical. That is accepted deliberately, including on the student-facing feed. The alternative considered and rejected was softening the preset toward a rounder look: it would have matched the mockups drawn during brainstorming, but every component added later would arrive in preset style and need the same manual treatment, which is how a codebase ends up a patchwork of configurations — the exact failure this pass exists to end.

Consistency is the goal. Where a preset component is a poor fit for a surface, the fix is to choose a different preset component, never to restyle one.

### 2.3 The card must earn its space

A setting gets a **card** — its own bordered block, value shown large, consequence written underneath — only when its consequence is not self-evident. Everything else is a **compact row** under a small uppercase section header.

Applied, per setting:

| Setting | Treatment | Why |
|---|---|---|
| `like_value` | card, slider | the number's effect on a grade is not guessable |
| `like_exponent` | card, three radio options | nobody thinks in exponents; each option must state its outcome |
| `tareas_weight`, `examenes_weight` | card each, typed | the one place typing is right, and each needs its own explanation |
| `attendance_required_pct` | card, slider | decides who exempts |
| falta cost (−10, fixed) | row, read-only | a stated fact, not a choice |
| retardo behaviour | row, read-only | states that a retardo does not subtract today |
| incentive list items | rows | each is a name and a number |

There is deliberately no switch in that table. Making "un retardo cuenta como falta" configurable would need a new column and a grade-engine branch — a feature, not a design change. The row states the current behaviour and nothing more.

### 2.4 Never make the user type what they can choose

Sliders, switches and radio choices by default. The keyboard appears only for the two rubro weights and for naming things (incentive names, class name).

`tap_value` leaves the UI entirely. It stays at `1.0` in `points_config` and is not tunable — one tap is one point, which is the rule the whole participación mechanic rests on.

`like_cap` and `daily_post_limit` stay unexposed. The concave curve is deliberately the anti-cramming mechanism; a cap would undo it (`planning/future.md` question 1, closed 2026-07-30).

### 2.5 Every number states its unit

The décima trap is the most likely source of a real grading mistake, and it lives in the interface, not the engine. Any points value is rendered in the 100-scale with its equivalents spelled out:

- `1.0` → "un punto de 100 · una décima de 10"
- `5` → "5 puntos · 5 décimas · medio punto de 10"
- `−10` → "diez puntos de 100 · un punto entero de 10"

A single helper produces this string; no surface writes its own.

### 2.6 The `like_exponent` is presented as behaviour

Three named options, each stating its actual outcome, computed and not hardcoded:

| Option | Value | Shown as |
|---|---|---|
| Fuerte | 0.5 | "100 likes = 10 puntos" |
| Suave | 0.75 | "100 likes = 32 puntos" |
| Lineal | 1.0 | "100 likes = 100 puntos" |

Fuerte is the default and stays recommended. The stored column keeps accepting any value in `[0.1, 2.0]`; the UI offers these three.

### 2.7 Flat icons, with two survivors

All UI iconography becomes `@remixicon/react`, the library `components.json` already names and `package.json` already carries. **No new icon dependency** — an earlier draft of this spec called for `lucide-react`, which would have fought the preset. Emojis leave the interface.

**Kept:** 👻 ghost and 🥷 polizón as enrollment-status markers. The v2 spec names those two specifically, they carry meaning rather than decoration, and the playfulness is intended. Everything else — 📌 ✅ 🗣️ 📝 ⚖ ⚡ — becomes an icon.

### 2.8 The feed does not move under your thumb

The server keeps bumping `last_activity_at` on likes and replies. The **client** stops re-sorting while you read: order changes only on an explicit refresh.

Cause, precisely: `frontend/src/lib/likes.ts:56` invalidates the whole `["feed"]` query in `onSettled`, forcing a refetch that returns the just-bumped post at the top. The `onMutate` optimistic patch above it already applies the correct like state in place. Removing the invalidation is the fix.

`mergePages` already dedupes by id, so a bumped post cannot appear twice. The residual behaviour — a post bumped above your scroll position while you read won't be re-fetched lower down — is accepted; it appears at the top on the next refresh.

### 2.9 A vetoed post stays visible

The feed currently filters `Post.status == "active"` (`backend/app/routers/posts.py:128`), so a vetoed participación disappears entirely. From the student's side that is a post silently deleted with no explanation, which is the opposite of what 2b-1 §2.6 intended when it kept vetoed posts in the thread with their reason.

Vetoed posts stay in the feed, marked as not counting, with the reason visible to their author only. Deleted posts stay hidden. The existing privacy rule is unchanged: `veto_reason` reaches the author and the teacher, nobody else.

### 2.10 Revisar shows what is pending

The participaciones tab defaults to unhandled items. Vetoing removes the row from the list rather than flipping its button in place, with a "Vistas" filter to go back and un-veto. This matches the queue semantics already chosen in 2b-1 §2.5: the list is what needs you, not everything that ever happened.

## 3. The settings architecture

```
/configurar                        index, read-only
  ├── /configurar/pesos            tareas_weight · examenes_weight
  ├── /configurar/foro             like_value · like_exponent
  ├── /configurar/extras           incentives: list, create, delete, award
  ├── /configurar/asistencia       attendance_required_pct · reglas (read-only)
  ├── /configurar/salvando         explanation + activation (disabled, §5)
  └── /configurar/clase            name, dates, schedule
```

Each index row renders: remixicon glyph, group name, current-state summary, chevron.

**Pesos** — the two weights, each its own card, each typed. Below them a read-only line stating that the remainder of the grade comes from participaciones, likes and puntos extra, which are uncapped. **Never** warn that the weights don't total 100; the gap is the design (`CLAUDE.md`).

**Foro** — `like_value` slider, `like_exponent` as §2.6.

**Extras** — the incentive list as rows (name, points with units per §2.5), plus create and award. The create form states the unit beside the number field as the user types. Deletion keeps its existing soft-delete semantics: an incentive that has been awarded is marked `deleted_at` and its ledger rows survive.

**Asistencia** — `attendance_required_pct` slider. The column exists on `Class` and has never been reachable. Exposing it needs one small backend change: adding the field to `ClassSettingsUpdate` and `ClassSettingsOut` in `backend/app/schemas.py`, which today carry only the weights and the three point values. No migration — the column is already there with a default of 80.

Below it, read-only rows: falta cost −10, and a statement of current retardo behaviour.

**Clase** — name, start and end dates, schedule. Currently set at creation and editable nowhere.

## 4. Scope of change per surface

**Rebuilt against the new primitives:** `Configurar.tsx` (split into an index and six group pages), `Revisar.tsx`, `ClassPanel.tsx`, `PasarLista.tsx`.

**Re-skinned, structure unchanged:** `Home.tsx`, `Thread.tsx`, `Compose.tsx`, `Classes.tsx`, `PostCard.tsx`, `GradeChip.tsx`, `Shell.tsx`, `Onboarding.tsx`, `Login.tsx`.

**Behaviour changes:** `likes.ts` (§2.8), `posts.py` feed filter (§2.9), `Revisar.tsx` participaciones tab (§2.10).

`Configurar.tsx` is 341 lines doing settings, incentive CRUD, awarding and two modals. Splitting it by group page is part of this work, not incidental refactoring.

## 5. Salvando el semestre

The index gets its row and the page gets built: what the protocol is, what it would do, and a disabled activation control marked as coming.

The mechanic itself — multipliers, whether they apply retroactively or only forward, how randomness works — is **not** in this pass. It touches the grade engine and needs its own spec and tests. `planning/roadmap.md` has it under "Medio semestre".

## 6. Testing

This pass is mostly visual, and visual correctness is not unit-testable. What is:

- **Unit:** the units helper from §2.5 (1.0, 5, −10, 0.5, and a value with decimals), and the `like_exponent` preview calculation for all three options — the numbers shown to the teacher must come from the same maths as the engine, never from hardcoded strings
- **Unit:** `mergePages` still dedupes after the feed change
- **API:** the feed includes vetoed posts and excludes deleted ones; `veto_reason` still reaches only author and teacher; `PATCH /api/classes/{id}/settings` accepts and persists `attendance_required_pct` and still rejects unknown fields with 422
- **Manual, per surface, at 390 px before desktop:** every rebuilt page, since the point of this work is how it looks and feels

Existing backend tests must stay green — 194 at the time of writing. The count should rise only from the two backend changes named above; anything else moving is a red flag.

## 7. Rollout

Order, each step deployable on its own:

1. Preset primitives added via `npx shadcn add`; units helper written and tested. Nothing visible changes.
2. Settings architecture: index plus the six group pages.
3. Revisar and the class panel, with the §2.10 queue fix.
4. Student surfaces: feed, thread, composer, with §2.8 and §2.9.

Nothing goes to Railway until Mario has seen it locally on a phone. Production stays on `main` — students are using it mid-semester, and this branch does not deploy on merge until he says so.

## 8. Notes

- Bug 2 in `planning/bugs.md` (deleting your latest entrega loses the tarea) is untouched by this pass and stays open.
- Editing a post — as opposed to deleting and reposting — remains unbuilt. `planning/changelog.md` 2026-07-31 records it as pending and not urgent; it interacts with the "no evidence, no points" rule and needs its own decision.
