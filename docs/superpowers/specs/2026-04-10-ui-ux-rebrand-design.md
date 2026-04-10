# UI/UX Rebrand & Consolidation Design Spec

**Date:** 2026-04-10  
**Scope:** Full frontend rebrand (both portals), teacher nav consolidation, student UX reorder, bug reporting, technical debt  
**Approach:** Layered — 4 sequential phases, each independently shippable

---

## 1. Brand System

### Colors
Replace all existing orange/rust palette with the Marionomics brand system:

| Token | Value | Replaces | Usage |
|---|---|---|---|
| `dark` | `#2b2b2b` | `#1F2020` | Teacher bg, dark sections, primary buttons on light bg |
| `cream` | `#f0ede6` | `#F2F0E4` | Student bg (near-identical, keep) |
| `lime` | `#c8f135` | `#EA8251` (orange) | Primary accent, badges, CTAs, active tab indicator |
| `surface` | `#1e1e1e` | — | Teacher nav/header bg |
| `lime-dim` | `rgba(200,241,53,0.12)` | `rgba(234,130,81,0.1)` | Hover states, avatar bg, subtle highlights |
| `danger` | `#ff6060` | existing red | Absent, errors (teacher dark bg context) |
| `danger-light` | `#e53935` | existing red | Absent, errors (student light bg context) |
| `warning` | `#f5a623` | existing amber | Late, pending |
| `white` | `#ffffff` | — | Student cards, nav bg |

Remove entirely: `#EA8251`, `#9C4927`, `text-violet-*`, `bg-violet-*`, any `#667eea`/`#764ba2`.

### Typography
- Replace `Inter` with `Graphik` across all pages
- Font files live in `/Users/marionomics/Dropbox/BrandKit/Tipografias/` — copy to `static/fonts/`
- Weights: Regular (400), Medium (500), Semibold (600)
- Declare via `@font-face` in a shared `static/css/brand.css`
- Fallback: `system-ui, -apple-system, sans-serif`

### Shared CSS file
Create `static/css/brand.css` with:
- `@font-face` declarations for Graphik
- CSS custom properties (`:root { --dark: #2b2b2b; --cream: #f0ede6; --lime: #c8f135; ... }`)
- Shared utility classes replacing the per-page Tailwind config blocks and opacity variant classes
- Imported in every HTML page's `<head>`

### Logo Mark
All pages get the Marionomics logo mark in the nav: lime circle (`#c8f135`) with dark "M↗" symbol (26×26px, border-radius 50%). Replaces the current text-only "Portal" label.

### Icons
No emoji anywhere in structural UI. All existing emoji icons (⭐ ✨ ⚠️ ✅ in student class cards, teacher stat cards) replaced with inline Heroicons-style SVGs (`fill="none" stroke="currentColor"`).

---

## 2. Teacher Panel

### Navigation: 5 tabs (was 7)

| New Tab | Replaces | Contents |
|---|---|---|
| **Hoy** | Vista General (partially) | Daily stats + pending participation + forum feed + quick shortcuts |
| **Alumnos** | Lista de Alumnos + Asistencia | Student roster with mode toggle (see below) |
| **Evaluaciones** | Exámenes + Retos | All grading: in-person exams, online exams, retos/submissions, grade categories |
| **Historial** | Asistencia (historical) + Justificaciones | Attendance calendar by date + justification review |
| **Foro** | (was buried in navigation) | Full forum with teacher moderation tools |

Justifications badge moves to the **Historial** tab.

### "Hoy" Tab
Three-column layout (desktop) / stacked cards (mobile):
1. **Asistencia de hoy** — count of present/absent + mini student list with status dots + "Tomar Asistencia" button (navigates to Alumnos → Attendance mode)
2. **Participación en vivo** — pending count, recent submissions, "Aprobar Todo" + "Revisar" buttons
3. **Foro — actividad reciente** — last 3 posts with author avatar, title, like count, points earned, "Ir al Foro" button

### "Alumnos" Tab — Merged Roster + Attendance
Single tab with a **Lista / Asistencia toggle** at the top:

**Lista mode (default):**
- Student rows: name (clickable) · final grade (color-coded) · chevron
- Clicking a student name opens an inline detail drawer: final grade, participation pts, absence count, attendance %, retos submitted count
- No "Ver Detalle" / "Acciones" column anywhere — name is the tap target
- Search/filter bar preserved

**Asistencia mode:**
- Same student list, same order
- Each row: student name + P / A / T tap buttons (one tap to mark)
- Date picker at top (defaults to today) — purpose is **recording** attendance for a specific day
- Running tally: `38 ✓ · 2 ✗ · 2 ?`
- "Guardar Asistencia" button at bottom
- Mobile-optimized: large tap targets, no table columns

### "Evaluaciones" Tab
Merges the former Exámenes and Retos tabs:
- Section headers: "Exámenes Presenciales" · "Exámenes Online" · "Retos" · "Categorías"
- All existing create/grade/auto-grade flows preserved, just under one tab
- The keyboard-first exam grading modal is unchanged

### "Historial" Tab
- Top: date picker → **review** attendance for any past date (read-only; to correct a past record, switch to Alumnos → Asistencia mode and pick that date)
- Below: Justificaciones list (moved from standalone tab), with status filter
- Justification badge count shown on this tab's label
- Distinction from Alumnos > Asistencia mode: Historial = browse/audit; Alumnos = record/edit

### "Foro" Tab
- Full forum view with teacher moderation (pin, lock, delete)
- Identical to current `forum.html` content but embedded in the class dashboard

### Dark Mode Styling
- Background: `#2b2b2b`
- Nav/header surface: `#1e1e1e`
- Cards: `rgba(255,255,255,0.04)` bg, `rgba(255,255,255,0.07)` border
- Active tab indicator: `#c8f135` border-bottom + `#c8f135` text
- Inactive tabs: `rgba(255,255,255,0.3)` text
- Section micro-labels: `font-size: 9px; letter-spacing: 3px; text-transform: uppercase; color: rgba(255,255,255,0.3)`
- Primary CTA buttons: `background: #c8f135; color: #2b2b2b; font-weight: 800`
- Ghost buttons: `border: 1px solid rgba(255,255,255,0.15); color: rgba(255,255,255,0.5)`

### Teacher Preview Mode
Preserved exactly as-is. "Vista de Estudiante" button remains in the teacher admin panel.

---

## 3. Student Portal

### Section Order (one page, no tabs — preserved)
New order, conditional rendering:

1. **Dashboard** — class cards (unchanged structure, rebranded colors)
2. **Trabajo Pendiente** — shown ONLY when student has unsubmitted assignments with upcoming/past due dates; hidden when nothing is pending
3. **Participación en vivo** — participation button block (design preserved exactly, gradient updated to lime)
4. **Foro** — forum feed (unchanged position relative to participation)

"Mis Retos" section removed from the main page entirely. Completed/past submissions are accessible via "Ver desglose completo" on the class card.

### Conditional Pending Work Section
- Shown when: `assignments` with `submission === null` and `due_date !== null`
- Dark band (`#2b2b2b` bg) with left lime border (`border-left: 3px solid #c8f135`)
- Lists pending items: assignment title · due date (red if overdue or due today, muted if future)
- Each item has a direct "Entregar →" action link
- Section disappears completely once all assignments are submitted or have no due date

### Class Cards
- Grade badge: lime background (`#c8f135`) + dark text when grade ≥ 70, unchanged colors for warning/risk states
- Stats grid: 3 columns — Participación / Pts. Extra / Faltas
- "Ver desglose completo →" link at bottom (opens existing grade modal — unchanged)
- Emoji icons (⭐ ✨ ⚠️ ✅) replaced with SVG Heroicons

### Participation Button
- Animation and ×1/×2/×3 tap logic: **unchanged**
- Gradient updated: `linear-gradient(135deg, #c8f135 0%, #a8d020 100%)` replaces orange gradient
- Text color: `#2b2b2b` (dark on lime)

### Bug Report FAB (student only)
- Fixed position: bottom-right, `position: fixed; bottom: 20px; right: 16px; z-index: 40`
- Subtle styling: `background: rgba(43,43,43,0.06); border: 1px solid rgba(43,43,43,0.12); color: rgba(43,43,43,0.35)`
- Label: "⚡ Reportar bug" (emoji acceptable in user-facing utility element)
- On click: opens `mailto:` using `TEACHER_EMAIL` env var (served via `/api/config`); subject "Bug en Portal del Estudiante"; body auto-prefilled with `window.location.href`
- `window.location.href` auto-appended to email body so you know which page the report came from
- **Not shown on teacher panel**

### Light Mode Styling
- Background: `#f0ede6` (cream)
- Cards: `#ffffff` bg, `#e8e4da` border
- Primary accent: `#c8f135` (lime) replaces `#EA8251` (orange)
- Text: `#2b2b2b`
- Muted text: `#888` / `#aaa`
- Focus rings: manual CSS class `.focus-lime` (`outline: 2px solid #c8f135; outline-offset: 2px`) in `brand.css` — Tailwind CDN doesn't support arbitrary color values in `focus:ring-*`

---

## 4. Technical Debt

### API Caching Layer
Add a simple in-memory cache in both `home.js` and `class-dashboard.js`:
```js
const _cache = {};
async function cachedCall(key, fn, ttlMs = 30000) {
  if (_cache[key] && Date.now() - _cache[key].ts < ttlMs) return _cache[key].data;
  const data = await fn();
  _cache[key] = { data, ts: Date.now() };
  return data;
}
```
- Grade calculation results cached 30s — avoids re-fetch every time grade modal opens
- Dashboard data cached on tab switch
- Cache invalidated on any write action (save attendance, approve participation, etc.)

### JS File Splitting
Both monolithic files split into logical modules using ES module `<script type="module">`:

`home.js` (1662 lines) → split into:
- `home-auth.js` — login, logout, session
- `home-dashboard.js` — class cards, grade modal, join modal
- `home-participation.js` — participation form and tap logic
- `home-forum.js` — forum feed, likes, replies, casino toasts
- `home-assignments.js` — pending work section
- `home-main.js` — boot, imports, shared state

`class-dashboard.js` (1898 lines) → split into:
- `dashboard-core.js` — init, tab switching, shared state
- `dashboard-alumnos.js` — roster + attendance mode
- `dashboard-evaluaciones.js` — exams, retos, grading modal
- `dashboard-hoy.js` — today tab, participation approval
- `dashboard-historial.js` — historical attendance, justifications
- `dashboard-forum.js` — embedded forum tab

### Color/Style Violations Fixed
- Remove all `text-violet-500`, `bg-violet-500` → replace with `text-[#f5a623]` (warning amber)
- Remove all `#667eea`, `#764ba2` occurrences
- Remove emoji from structural UI elements (class cards, stat cards)
- Consolidate per-page Tailwind config blocks into `brand.css`

### Sequential API Call Fixes
- `loadStudentDashboard`: already uses `Promise.all` for grade + assignment fetches — preserve
- `openGradeModal`: currently re-fetches grade calc on every open → use cache
- `loadRoster`: re-fetches on every tab visit → use cache with manual refresh option

---

## 5. Implementation Plan (4 Phases)

### Phase 1 — Brand Tokens (visual win, low risk)
1. Copy Graphik font files to `static/fonts/`
2. Create `static/css/brand.css` with `@font-face`, CSS vars, shared utility classes
3. Update all HTML pages: add `brand.css` link, replace Tailwind config blocks, swap Inter → Graphik, swap all color references orange→lime, violet→amber
4. Replace emoji icons with SVG Heroicons in student class cards
5. Update participation button gradient to lime

**Deliverable:** Both portals look Marionomics-branded. All existing functionality unchanged.

### Phase 2 — Teacher Nav Restructure
1. Merge "Asistencia" tab into "Alumnos" with Lista/Asistencia toggle
2. Merge "Exámenes" + "Retos" into "Evaluaciones" tab
3. Merge "Justificaciones" into new "Historial" tab (with historical attendance)
4. Rename "Vista General" → "Hoy", restructure into 3-column daily view
5. Add "Foro" as 5th tab (embed forum content from `forum.html`)
6. Make student names clickable everywhere → inline detail drawer
7. Apply dark mode styling to teacher panel

**Deliverable:** Teacher dashboard has 5 clean tabs, no redundant lists, mobile-optimized attendance flow.

### Phase 3 — Student UX Reorder + Technical Debt
1. Student portal: implement conditional "Trabajo Pendiente" section
2. Remove "Mis Retos" section from main page; ensure completed work is in desglose completo
3. Reorder sections: Dashboard → Pending → Participación → Foro
4. Add bug report FAB to student portal (mailto, auto-appends page URL)
5. Add API caching layer to both `home.js` and `class-dashboard.js`
6. Split `home.js` into modules
7. Split `class-dashboard.js` into modules
8. Fix remaining color violations

**Deliverable:** Student portal flow matches real usage priority. Both frontends performant and maintainable.

### Phase 4 — Polish & Validation
1. Test all flows on mobile (Chrome DevTools mobile simulation + real device)
2. Test teacher preview mode end-to-end
3. Verify forum points/casino toasts still work
4. Verify online exam flow unchanged
5. Verify all API endpoints still called correctly after JS split
6. Add `.superpowers/` to `.gitignore`

**Deliverable:** Production-ready. Ship to Railway.

---

## 6. Out of Scope (noted for future)

- Automated attendance (QR/geolocation) — separate session
- Social/algorithmic forum graph (engagement visualization) — separate session
- Graphik font license verification for web use — confirm before Phase 1 ships
- Multi-teacher support — not needed yet, single teacher assumption holds

---

## Decisions Made

| Decision | Choice | Reason |
|---|---|---|
| Teacher panel color mode | Dark (`#2b2b2b`) | Marionomics native aesthetic, professional feel |
| Student portal color mode | Light (cream) | Warm, approachable; consistent with existing |
| Primary accent | Lime `#c8f135` | Marionomics brand; replaces off-brand orange |
| Font | Graphik | Marionomics brand; replaces Inter |
| Tab count (teacher) | 5 | Consolidates 7 without losing any functionality |
| Bug report | Student FAB → mailto | Simple, no backend needed, teacher doesn't need it |
| Tech debt timing | Phase 3 (same release) | Already touching files; no reason to defer |
| "Mis Retos" | Remove from main view | Surfaces only when pending; completed = desglose |
