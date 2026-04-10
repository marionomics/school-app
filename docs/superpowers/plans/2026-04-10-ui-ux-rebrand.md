# UI/UX Rebrand & Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebrand both portals to the Marionomics brand system, consolidate the teacher dashboard from 7 tabs to 5, improve student UX flow, add bug reporting FAB, and address JS technical debt.

**Architecture:** Frontend-only changes (no backend schema changes except adding `teacher_email` to `/api/config`). Brand tokens live in a shared `static/css/brand.css`. JS modules split using ES `<script type="module">`. Teacher dashboard rebuilt around 5 tabs with dark mode.

**Tech Stack:** Vanilla JS (ES modules), Tailwind CSS CDN, FastAPI (Python), SQLAlchemy, Railway

**Spec reference:** `docs/superpowers/specs/2026-04-10-ui-ux-rebrand-design.md`

---

## File Map

### Created
- `static/css/brand.css` — CSS custom properties, @font-face Graphik, shared utilities
- `static/fonts/Graphik-Regular.otf` — copied from BrandKit
- `static/fonts/Graphik-Medium.otf` — copied from BrandKit
- `static/fonts/Graphik-Semibold.otf` — copied from BrandKit
- `static/js/home-auth.js` — login, logout, session (split from home.js)
- `static/js/home-dashboard.js` — class cards, grade modal, join modal
- `static/js/home-participation.js` — participation form and tap logic
- `static/js/home-forum.js` — forum feed, likes, replies, casino toasts
- `static/js/home-assignments.js` — pending work section
- `static/js/home-main.js` — boot, imports, shared state
- `static/js/dashboard-core.js` — init, tab switching, shared state
- `static/js/dashboard-alumnos.js` — roster + attendance mode toggle
- `static/js/dashboard-evaluaciones.js` — exams, retos, grading modal
- `static/js/dashboard-hoy.js` — today tab, participation approval
- `static/js/dashboard-historial.js` — historical attendance, justifications
- `static/js/dashboard-forum.js` — embedded forum tab

### Modified
- `static/index.html` — add brand.css, Graphik, reorder sections, bug FAB, replace emoji with SVGs
- `static/admin.html` — add brand.css, Graphik
- `static/class-dashboard.html` — rebuild to 5 tabs, dark mode, add brand.css
- `static/js/home.js` — replaced by home-* modules (kept as shim if needed)
- `static/js/class-dashboard.js` — replaced by dashboard-* modules
- `static/forum.html` — add brand.css, Graphik
- `static/js/forum.js` — update colors
- `app/main.py` — add `teacher_email` to `/api/config`

---

## Phase 1 — Brand Tokens

### Task 1: Font Files + brand.css

**Files:**
- Create: `static/fonts/Graphik-Regular.otf`
- Create: `static/fonts/Graphik-Medium.otf`
- Create: `static/fonts/Graphik-Semibold.otf`
- Create: `static/css/brand.css`

- [ ] **Step 1: Copy Graphik font files**

```bash
mkdir -p static/fonts
cp /Users/marionomics/Dropbox/BrandKit/Tipografias/Graphik-Regular.otf static/fonts/
cp /Users/marionomics/Dropbox/BrandKit/Tipografias/Graphik-Medium.otf static/fonts/
cp /Users/marionomics/Dropbox/BrandKit/Tipografias/Graphik-Semibold.otf static/fonts/
```

- [ ] **Step 2: Create `static/css/brand.css`**

```css
/* ===== Marionomics Brand System ===== */

@font-face {
  font-family: 'Graphik';
  src: url('/static/fonts/Graphik-Regular.otf') format('opentype');
  font-weight: 400;
  font-style: normal;
  font-display: swap;
}
@font-face {
  font-family: 'Graphik';
  src: url('/static/fonts/Graphik-Medium.otf') format('opentype');
  font-weight: 500;
  font-style: normal;
  font-display: swap;
}
@font-face {
  font-family: 'Graphik';
  src: url('/static/fonts/Graphik-Semibold.otf') format('opentype');
  font-weight: 600;
  font-style: normal;
  font-display: swap;
}

/* ===== CSS Custom Properties ===== */
:root {
  --dark: #2b2b2b;
  --cream: #f0ede6;
  --lime: #c8f135;
  --surface: #1e1e1e;
  --lime-dim: rgba(200, 241, 53, 0.12);
  --danger: #ff6060;
  --danger-light: #e53935;
  --warning: #f5a623;
  --white: #ffffff;
  --font-brand: 'Graphik', system-ui, -apple-system, sans-serif;
}

/* ===== Global Font ===== */
body {
  font-family: var(--font-brand);
}

/* ===== Focus Ring ===== */
.focus-lime:focus {
  outline: 2px solid var(--lime);
  outline-offset: 2px;
}

/* ===== Brand Mark (logo circle) ===== */
.brand-mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  background: var(--lime);
  border-radius: 50%;
  color: var(--dark);
  font-weight: 800;
  font-size: 12px;
  flex-shrink: 0;
}

/* ===== Micro Label ===== */
.micro-label {
  font-size: 9px;
  letter-spacing: 3px;
  text-transform: uppercase;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.3);
}

/* ===== Teacher Dark Mode Base ===== */
.teacher-panel {
  background: var(--dark);
  color: var(--white);
  min-height: 100vh;
}
.teacher-surface {
  background: var(--surface);
}
.teacher-card {
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.07);
  border-radius: 12px;
}

/* ===== Teacher Tab Nav ===== */
.teacher-tab {
  padding: 14px 16px;
  font-size: 13px;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.45);
  border-bottom: 2px solid transparent;
  cursor: pointer;
  white-space: nowrap;
  transition: color 0.15s;
  background: none;
  border-top: none;
  border-left: none;
  border-right: none;
}
.teacher-tab:hover {
  color: rgba(255, 255, 255, 0.7);
}
.teacher-tab.active {
  color: var(--lime);
  border-bottom-color: var(--lime);
}

/* ===== Teacher CTA Buttons ===== */
.btn-lime {
  background: var(--lime);
  color: var(--dark);
  font-weight: 800;
  border: none;
  border-radius: 8px;
  padding: 10px 18px;
  cursor: pointer;
  font-family: var(--font-brand);
  transition: opacity 0.15s;
}
.btn-lime:hover { opacity: 0.9; }

.btn-ghost {
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.15);
  color: rgba(255, 255, 255, 0.5);
  border-radius: 8px;
  padding: 10px 18px;
  cursor: pointer;
  font-family: var(--font-brand);
  transition: border-color 0.15s, color 0.15s;
}
.btn-ghost:hover {
  border-color: rgba(255, 255, 255, 0.3);
  color: rgba(255, 255, 255, 0.7);
}

/* ===== Student Light Mode ===== */
.student-portal {
  background: var(--cream);
  color: var(--dark);
  min-height: 100vh;
}

/* ===== Lime Badge ===== */
.badge-lime {
  background: var(--lime);
  color: var(--dark);
  font-weight: 700;
  border-radius: 9999px;
  padding: 2px 10px;
  font-size: 13px;
}

/* ===== Pending Work Band ===== */
.pending-band {
  background: var(--dark);
  border-left: 3px solid var(--lime);
  border-radius: 8px;
  padding: 16px;
  color: var(--white);
}

/* ===== Bug Report FAB ===== */
.bug-fab {
  position: fixed;
  bottom: 20px;
  right: 16px;
  z-index: 40;
  background: rgba(43, 43, 43, 0.06);
  border: 1px solid rgba(43, 43, 43, 0.12);
  color: rgba(43, 43, 43, 0.35);
  border-radius: 20px;
  padding: 7px 14px;
  font-size: 12px;
  cursor: pointer;
  font-family: var(--font-brand);
  transition: background 0.15s, color 0.15s;
}
.bug-fab:hover {
  background: rgba(43, 43, 43, 0.1);
  color: rgba(43, 43, 43, 0.6);
}

/* ===== Participation Gradient (lime override) ===== */
.participation-gradient {
  background: linear-gradient(135deg, #c8f135 0%, #a8d020 100%);
  color: var(--dark);
}
```

- [ ] **Step 3: Start the dev server and verify font loads**

```bash
uvicorn app.main:app --reload &
sleep 2
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/static/css/brand.css
```
Expected: `200`

- [ ] **Step 4: Commit**

```bash
git add static/fonts/ static/css/brand.css
git commit -m "feat: add Graphik fonts and brand.css token system"
```

---

### Task 2: Expose `teacher_email` in `/api/config`

**Files:**
- Modify: `app/main.py` (the `/api/config` route)

- [ ] **Step 1: Read current `/api/config` in `app/main.py`**

Find the `@app.get("/api/config")` route and note its current response dict.

- [ ] **Step 2: Add `teacher_email` to the response**

In `app/main.py`, find the config endpoint and add:

```python
@app.get("/api/config")
async def get_config():
    return {
        "google_client_id": os.getenv("GOOGLE_CLIENT_ID", ""),
        "file_uploads_enabled": is_r2_configured(),
        "teacher_email": os.getenv("TEACHER_EMAIL", ""),
    }
```

- [ ] **Step 3: Verify endpoint**

```bash
curl -s http://localhost:8000/api/config | python3 -m json.tool
```
Expected: JSON with `teacher_email` key present.

- [ ] **Step 4: Commit**

```bash
git add app/main.py
git commit -m "feat: expose teacher_email in /api/config for bug report FAB"
```

---

### Task 3: Student Portal Rebrand (`index.html`)

**Files:**
- Modify: `static/index.html`

- [ ] **Step 1: Read `static/index.html` head section (first 60 lines)**

Note the current `<head>` structure: Google Fonts link, Tailwind CDN script with config block, style block with opacity variants.

- [ ] **Step 2: Replace head — swap Inter for Graphik, add brand.css, update Tailwind config**

Replace the `<head>` section:
- Remove: `<link href="https://fonts.googleapis.com/css2?family=Inter:wght@...">` 
- Add: `<link rel="stylesheet" href="/static/css/brand.css">`
- Update Tailwind config colors:
  ```html
  <script>
    tailwind.config = {
      theme: {
        extend: {
          colors: {
            primary: '#c8f135',
            secondary: '#a8d020',
            dark: '#2b2b2b',
            cream: '#f0ede6',
            surface: '#1e1e1e',
            warning: '#f5a623',
            danger: '#e53935',
          }
        }
      }
    }
  </script>
  ```
- Remove: all `bg-primary-5`, `bg-primary-10`, `hover:bg-primary-5:hover` style block entries and replace with CSS vars from `brand.css`

- [ ] **Step 3: Update body class and text colors**

- `<body>` should have class `student-portal` (from brand.css) instead of `bg-cream`
- Replace `text-primary` (orange) with `text-[#c8f135]` where lime is appropriate
- Replace `bg-primary` (orange) buttons with `btn-lime` class
- Replace `text-violet-500` (pending participation) with `style="color:var(--warning)"` or `text-[#f5a623]`

- [ ] **Step 4: Replace emoji icons in class cards with SVG Heroicons**

Find all emoji in structural UI (⭐ ✨ ⚠️ ✅) and replace with inline SVGs:

Star icon (replaces ⭐):
```html
<svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
  <path stroke-linecap="round" stroke-linejoin="round" d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z"/>
</svg>
```

Sparkle/check icon (replaces ✨ ✅):
```html
<svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
  <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/>
</svg>
```

Warning icon (replaces ⚠️):
```html
<svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
  <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
</svg>
```

- [ ] **Step 5: Update participation button gradient**

Find the participation button element and replace orange gradient with:
```html
class="participation-gradient ..."
```
(The `participation-gradient` class is defined in brand.css as `linear-gradient(135deg, #c8f135 0%, #a8d020 100%)`)

- [ ] **Step 6: Add Bug Report FAB before closing `</body>`**

```html
<button class="bug-fab" id="bugFab" onclick="reportBug()">⚡ Reportar bug</button>

<script>
  async function reportBug() {
    let teacherEmail = '';
    try {
      const cfg = await fetch('/api/config').then(r => r.json());
      teacherEmail = cfg.teacher_email || '';
    } catch(e) {}
    const subject = encodeURIComponent('Bug en Portal del Estudiante');
    const body = encodeURIComponent('Página: ' + window.location.href + '\n\nDescripción del bug:\n');
    window.location.href = 'mailto:' + teacherEmail + '?subject=' + subject + '&body=' + body;
  }
</script>
```

Note: Only shown for students — the bug FAB is hidden for teacher accounts. Add `id="bugFab"` and after auth resolves, hide it if `currentUser.role === 'teacher'`: `document.getElementById('bugFab').style.display = 'none'`.

- [ ] **Step 7: Open browser and verify student portal**

```bash
open http://localhost:8000
```

Check:
- Graphik font loads (inspect → Computed → font-family)
- Lime (#c8f135) replaces orange
- No emoji in class cards
- Participation button has lime gradient
- Bug FAB visible in bottom-right
- Grade breakdown modal opens correctly

- [ ] **Step 8: Commit**

```bash
git add static/index.html
git commit -m "feat: rebrand student portal — Graphik, lime palette, SVG icons, bug FAB"
```

---

### Task 4: Reorder Student Portal Sections + Conditional Pending Work

**Files:**
- Modify: `static/index.html`
- Modify: `static/js/home.js` (pending work rendering logic)

- [ ] **Step 1: Read the current section order in `index.html`**

Note the order of: class cards section, participation section, assignments section, forum section.

- [ ] **Step 2: Reorder HTML sections**

New order (move DOM elements):
1. Class cards (`#dashboard-section` or equivalent)
2. Pending work band (`#pending-work-section`) — add `hidden` by default
3. Participation section (`#participation-section`)
4. Forum section (`#forum-section`)

Remove the "Mis Retos" section from the main page entirely if it exists as a separate section.

- [ ] **Step 3: Read `home.js` — find where assignments are rendered**

Search for the function that renders assignments/retos (likely `renderAssignments` or similar). Note which assignments it includes.

- [ ] **Step 4: Update assignment rendering to show only pending work**

Replace the current assignment rendering logic with a function that:
1. Filters assignments to only those where `submission === null` AND `due_date !== null`
2. Shows the `#pending-work-section` only if filtered list is non-empty
3. Hides it completely when nothing is pending

```javascript
function renderPendingWork(assignments) {
  const pending = assignments.filter(a => !a.submission && a.due_date);
  const section = document.getElementById('pending-work-section');
  if (!section) return;
  if (pending.length === 0) {
    section.style.display = 'none';
    return;
  }
  section.style.display = 'block';
  const now = new Date();
  const list = pending.map(a => {
    const due = new Date(a.due_date);
    const isOverdue = due < now;
    const isToday = due.toDateString() === now.toDateString();
    const urgentColor = (isOverdue || isToday) ? 'color:#ff6060' : 'color:rgba(255,255,255,0.5)';
    const dueStr = due.toLocaleDateString('es-MX', { month: 'short', day: 'numeric' });
    return `<div style="display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.07)">
      <span style="font-weight:500">${a.title}</span>
      <div style="display:flex;align-items:center;gap:12px">
        <span style="${urgentColor};font-size:13px">Vence ${dueStr}</span>
        <a href="#assignments" style="color:var(--lime);font-size:13px;font-weight:600;text-decoration:none">Entregar →</a>
      </div>
    </div>`;
  }).join('');
  section.querySelector('.pending-list').innerHTML = list;
}
```

- [ ] **Step 5: Add `pending-work-section` HTML in `index.html`**

Add this HTML after the class cards section (hidden by default):

```html
<section id="pending-work-section" class="pending-band" style="display:none;margin:16px 0">
  <div style="display:flex;align-items:center;gap:8px;margin-bottom:12px">
    <svg width="16" height="16" fill="none" stroke="#c8f135" stroke-width="2" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/>
    </svg>
    <span style="font-size:11px;letter-spacing:3px;text-transform:uppercase;font-weight:600;color:rgba(255,255,255,0.4)">Trabajo Pendiente</span>
  </div>
  <div class="pending-list"></div>
</section>
```

- [ ] **Step 6: Wire `renderPendingWork` into the data load flow**

Find where assignments are loaded (e.g., `loadAssignments()` or inside `loadDashboard()`). After fetching, call `renderPendingWork(assignments)`.

- [ ] **Step 7: Verify in browser**

```bash
open http://localhost:8000
```

Check:
- If no pending assignments: pending band is invisible
- If there are pending assignments: dark band with lime left border appears
- Section order: cards → pending → participation → forum

- [ ] **Step 8: Commit**

```bash
git add static/index.html static/js/home.js
git commit -m "feat: reorder student sections, add conditional pending work band"
```

---

### Task 5: Rebrand Teacher Panels (`admin.html`, `forum.html`)

**Files:**
- Modify: `static/admin.html`
- Modify: `static/forum.html`
- Modify: `static/js/forum.js`

- [ ] **Step 1: Read `static/admin.html` head section**

Note current Google Fonts / Tailwind config.

- [ ] **Step 2: Update `admin.html` head**

- Remove Google Fonts Inter link
- Add `<link rel="stylesheet" href="/static/css/brand.css">`
- Update Tailwind config to use Marionomics palette (same as Task 3 Step 2)

- [ ] **Step 3: Update `forum.html` head similarly**

Same changes: remove Inter, add brand.css, update Tailwind config.

- [ ] **Step 4: Update `forum.js` color references**

Find any hardcoded orange `#EA8251`, `#9C4927`, or `text-violet-*` classes. Replace:
- `#EA8251` → `var(--lime)` or `#c8f135`
- `#9C4927` → `var(--dark)` or `#2b2b2b`
- `text-violet-500` → inline style `color: var(--warning)`
- `bg-violet-500` → inline style `background: var(--warning)`

- [ ] **Step 5: Verify forum page**

```bash
open http://localhost:8000/forum.html
```

Check: Graphik font, no orange, lime accents where appropriate.

- [ ] **Step 6: Commit**

```bash
git add static/admin.html static/forum.html static/js/forum.js
git commit -m "feat: rebrand admin and forum pages — Graphik, lime palette"
```

---

## Phase 2 — Teacher Dashboard 5-Tab Restructure

### Task 6: Build New `class-dashboard.html` Structure (5 tabs, dark mode)

**Files:**
- Modify: `static/class-dashboard.html` (full restructure)

This is the largest structural change. Read the current file fully first.

- [ ] **Step 1: Read full `static/class-dashboard.html`**

Note all modal IDs, form IDs, and any inline script blocks. These must be preserved.

- [ ] **Step 2: Update `<head>` — dark background, brand.css**

```html
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Panel del Profesor</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {
      theme: {
        extend: {
          colors: {
            dark: '#2b2b2b',
            surface: '#1e1e1e',
            lime: '#c8f135',
            warning: '#f5a623',
            danger: '#ff6060',
          }
        }
      }
    }
  </script>
  <link rel="stylesheet" href="/static/css/brand.css">
  <style>
    body { background: #2b2b2b; color: #fff; }
  </style>
</head>
```

- [ ] **Step 3: Replace nav/header with dark surface + logo mark + 5 tabs**

```html
<header style="background:var(--surface);border-bottom:1px solid rgba(255,255,255,0.07);position:sticky;top:0;z-index:30">
  <div style="max-width:1200px;margin:0 auto;padding:0 16px">
    <!-- Top bar: logo + class name + exit button -->
    <div style="display:flex;align-items:center;justify-content:space-between;padding:12px 0">
      <div style="display:flex;align-items:center;gap:10px">
        <div class="brand-mark">M↗</div>
        <div>
          <div class="micro-label">Panel del Profesor</div>
          <div id="classNameHeader" style="font-weight:600;font-size:16px;color:#fff;margin-top:2px"></div>
        </div>
      </div>
      <div style="display:flex;gap:8px">
        <button onclick="openStudentPreview()" class="btn-ghost" style="font-size:13px;padding:7px 14px">Vista de Estudiante</button>
        <a href="/admin" class="btn-ghost" style="font-size:13px;padding:7px 14px;text-decoration:none">← Clases</a>
      </div>
    </div>
    <!-- 5 Tab nav -->
    <nav style="display:flex;gap:0;overflow-x:auto;-webkit-overflow-scrolling:touch" id="tabNav">
      <button class="teacher-tab active" data-tab="hoy" onclick="showTab('hoy')">Hoy</button>
      <button class="teacher-tab" data-tab="alumnos" onclick="showTab('alumnos')">Alumnos</button>
      <button class="teacher-tab" data-tab="evaluaciones" onclick="showTab('evaluaciones')">Evaluaciones</button>
      <button class="teacher-tab" data-tab="historial" onclick="showTab('historial')">Historial <span id="historialBadge" style="display:none;background:var(--danger);color:#fff;border-radius:9999px;padding:1px 7px;font-size:11px;margin-left:4px"></span></button>
      <button class="teacher-tab" data-tab="foro" onclick="showTab('foro')">Foro</button>
    </nav>
  </div>
</header>
```

- [ ] **Step 4: Create 5 tab content panels**

Wrap existing tab content in new panel divs with `id="tab-{name}"`. Each has `display:none` initially except `tab-hoy` which is `display:block`.

```html
<main style="max-width:1200px;margin:0 auto;padding:16px">

  <!-- HOY TAB -->
  <div id="tab-hoy" class="tab-panel">
    <!-- 3-column grid: attendance summary | participation | forum activity -->
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px;margin-top:8px">
      
      <!-- Today Attendance Card -->
      <div class="teacher-card" style="padding:20px">
        <div class="micro-label" style="margin-bottom:12px">Asistencia de hoy</div>
        <div id="hoy-attendance-summary"></div>
        <button onclick="showTab('alumnos');setAlumnosMode('asistencia')" class="btn-lime" style="width:100%;margin-top:14px;font-size:13px">Tomar Asistencia</button>
      </div>

      <!-- Live Participation Card -->
      <div class="teacher-card" style="padding:20px">
        <div class="micro-label" style="margin-bottom:12px">Participación en vivo</div>
        <div id="hoy-participation-summary"></div>
        <div style="display:flex;gap:8px;margin-top:14px">
          <button onclick="bulkApproveParticipation()" class="btn-lime" style="flex:1;font-size:13px">Aprobar Todo</button>
          <button onclick="showTab('evaluaciones')" class="btn-ghost" style="flex:1;font-size:13px">Revisar</button>
        </div>
      </div>

      <!-- Forum Activity Card -->
      <div class="teacher-card" style="padding:20px">
        <div class="micro-label" style="margin-bottom:12px">Foro — actividad reciente</div>
        <div id="hoy-forum-activity"></div>
        <button onclick="showTab('foro')" class="btn-ghost" style="width:100%;margin-top:14px;font-size:13px">Ir al Foro</button>
      </div>

    </div>
  </div>

  <!-- ALUMNOS TAB -->
  <div id="tab-alumnos" class="tab-panel" style="display:none">
    <!-- Mode toggle -->
    <div style="display:flex;align-items:center;gap:0;margin:16px 0;background:rgba(255,255,255,0.06);border-radius:8px;padding:4px;width:fit-content">
      <button id="modeToggleLista" onclick="setAlumnosMode('lista')" style="padding:8px 20px;border-radius:6px;font-size:13px;font-weight:600;border:none;background:var(--lime);color:var(--dark);cursor:pointer;transition:all 0.15s">Lista</button>
      <button id="modeToggleAsistencia" onclick="setAlumnosMode('asistencia')" style="padding:8px 20px;border-radius:6px;font-size:13px;font-weight:600;border:none;background:transparent;color:rgba(255,255,255,0.5);cursor:pointer;transition:all 0.15s">Asistencia</button>
    </div>
    
    <!-- Lista mode -->
    <div id="alumnos-lista-panel">
      <div style="margin-bottom:12px">
        <input id="rosterSearch" type="text" placeholder="Buscar alumno..." oninput="filterRoster(this.value)"
          style="background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.12);color:#fff;border-radius:8px;padding:10px 14px;width:100%;font-family:var(--font-brand);font-size:14px">
      </div>
      <div id="rosterList"></div>
    </div>

    <!-- Asistencia mode -->
    <div id="alumnos-asistencia-panel" style="display:none">
      <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px;flex-wrap:wrap">
        <input type="date" id="attendanceDate" onchange="loadAttendanceForDate(this.value)"
          style="background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.12);color:#fff;border-radius:8px;padding:10px 14px;font-family:var(--font-brand)">
        <div id="attendanceTally" style="font-size:13px;color:rgba(255,255,255,0.5)"></div>
      </div>
      <div id="attendanceList"></div>
      <button onclick="saveAttendance()" class="btn-lime" style="margin-top:16px;width:100%">Guardar Asistencia</button>
    </div>
  </div>

  <!-- EVALUACIONES TAB -->
  <div id="tab-evaluaciones" class="tab-panel" style="display:none">
    <div id="evaluaciones-content"></div>
  </div>

  <!-- HISTORIAL TAB -->
  <div id="tab-historial" class="tab-panel" style="display:none">
    <div style="margin-bottom:20px">
      <div class="micro-label" style="margin-bottom:8px">Revisar asistencia por fecha</div>
      <input type="date" id="historialDate" onchange="loadHistorialAttendance(this.value)"
        style="background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.12);color:#fff;border-radius:8px;padding:10px 14px;font-family:var(--font-brand)">
    </div>
    <div id="historial-attendance-view" style="margin-bottom:32px"></div>
    
    <div class="micro-label" style="margin-bottom:12px">Justificaciones</div>
    <div style="display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap">
      <button onclick="loadJustificaciones('pending')" class="btn-ghost" style="font-size:12px;padding:6px 12px">Pendientes</button>
      <button onclick="loadJustificaciones('approved')" class="btn-ghost" style="font-size:12px;padding:6px 12px">Aprobadas</button>
      <button onclick="loadJustificaciones('rejected')" class="btn-ghost" style="font-size:12px;padding:6px 12px">Rechazadas</button>
    </div>
    <div id="justificaciones-list"></div>
  </div>

  <!-- FORO TAB -->
  <div id="tab-foro" class="tab-panel" style="display:none">
    <div id="forum-embedded-content"></div>
  </div>

</main>
```

- [ ] **Step 5: Add inline `showTab` and `setAlumnosMode` functions**

At the bottom of `class-dashboard.html`, before `</body>`:

```html
<script>
function showTab(tabName) {
  document.querySelectorAll('.tab-panel').forEach(p => p.style.display = 'none');
  document.querySelectorAll('.teacher-tab').forEach(t => t.classList.remove('active'));
  const panel = document.getElementById('tab-' + tabName);
  if (panel) panel.style.display = 'block';
  const btn = document.querySelector('[data-tab="' + tabName + '"]');
  if (btn) btn.classList.add('active');
  // Lazy-load tab content
  if (tabName === 'alumnos') loadRoster();
  if (tabName === 'evaluaciones') loadEvaluaciones();
  if (tabName === 'historial') initHistorial();
  if (tabName === 'foro') loadForumEmbedded();
}

function setAlumnosMode(mode) {
  const listaPanel = document.getElementById('alumnos-lista-panel');
  const asistPanel = document.getElementById('alumnos-asistencia-panel');
  const btnLista = document.getElementById('modeToggleLista');
  const btnAsist = document.getElementById('modeToggleAsistencia');
  if (mode === 'lista') {
    listaPanel.style.display = 'block';
    asistPanel.style.display = 'none';
    btnLista.style.background = 'var(--lime)';
    btnLista.style.color = 'var(--dark)';
    btnAsist.style.background = 'transparent';
    btnAsist.style.color = 'rgba(255,255,255,0.5)';
  } else {
    listaPanel.style.display = 'none';
    asistPanel.style.display = 'block';
    btnAsist.style.background = 'var(--lime)';
    btnAsist.style.color = 'var(--dark)';
    btnLista.style.background = 'transparent';
    btnLista.style.color = 'rgba(255,255,255,0.5)';
    // Default attendance date to today
    const dateInput = document.getElementById('attendanceDate');
    if (!dateInput.value) {
      dateInput.value = new Date().toISOString().split('T')[0];
      loadAttendanceForDate(dateInput.value);
    }
  }
}
</script>
```

- [ ] **Step 6: Preserve all existing modals**

The following modal HTML must be kept intact (they may already be in `class-dashboard.html`):
- Exam grading modal (`#examGradingModal` or equivalent)
- Submission review modal
- Grade creation modal
- Student detail drawer (new — see Task 7)

Search for modal divs and verify they are still present after restructuring.

- [ ] **Step 7: Verify in browser**

```bash
open http://localhost:8000/admin
```

Click a class → verify:
- Dark background
- 5 tabs in sticky header
- Logo mark visible
- Tab switching works
- "Vista de Estudiante" button still present

- [ ] **Step 8: Commit**

```bash
git add static/class-dashboard.html
git commit -m "feat: restructure teacher dashboard to 5-tab dark mode layout"
```

---

### Task 7: Student Detail Drawer in Alumnos Tab

**Files:**
- Modify: `static/class-dashboard.html` (add drawer HTML)
- Modify: `static/js/class-dashboard.js` (add `openStudentDrawer` function)

- [ ] **Step 1: Add drawer HTML to `class-dashboard.html`**

Before `</body>`:

```html
<!-- Student detail drawer (slides in from right) -->
<div id="studentDrawer" style="position:fixed;top:0;right:-400px;width:360px;height:100vh;background:var(--surface);border-left:1px solid rgba(255,255,255,0.1);z-index:50;padding:24px;overflow-y:auto;transition:right 0.25s ease;box-shadow:-8px 0 32px rgba(0,0,0,0.4)">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:24px">
    <h3 id="drawerStudentName" style="font-size:18px;font-weight:600;color:#fff"></h3>
    <button onclick="closeStudentDrawer()" style="background:transparent;border:none;color:rgba(255,255,255,0.4);font-size:20px;cursor:pointer;line-height:1">✕</button>
  </div>
  <div id="drawerContent">
    <div class="micro-label" style="margin-bottom:4px">Calificación final</div>
    <div id="drawerGrade" style="font-size:32px;font-weight:700;color:var(--lime);margin-bottom:20px"></div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
      <div class="teacher-card" style="padding:14px">
        <div class="micro-label" style="margin-bottom:4px">Participación</div>
        <div id="drawerParticipation" style="font-size:20px;font-weight:600;color:#fff"></div>
      </div>
      <div class="teacher-card" style="padding:14px">
        <div class="micro-label" style="margin-bottom:4px">Faltas</div>
        <div id="drawerAbsences" style="font-size:20px;font-weight:600;color:var(--danger)"></div>
      </div>
      <div class="teacher-card" style="padding:14px">
        <div class="micro-label" style="margin-bottom:4px">Asistencia</div>
        <div id="drawerAttendancePct" style="font-size:20px;font-weight:600;color:#fff"></div>
      </div>
      <div class="teacher-card" style="padding:14px">
        <div class="micro-label" style="margin-bottom:4px">Retos entregados</div>
        <div id="drawerRetos" style="font-size:20px;font-weight:600;color:#fff"></div>
      </div>
    </div>
  </div>
</div>
<div id="drawerOverlay" onclick="closeStudentDrawer()" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,0.5);z-index:49"></div>
```

- [ ] **Step 2: Add `openStudentDrawer` and `closeStudentDrawer` to `class-dashboard.js`**

```javascript
async function openStudentDrawer(studentId, studentName) {
  document.getElementById('drawerStudentName').textContent = studentName;
  document.getElementById('drawerContent').style.opacity = '0.5';
  document.getElementById('studentDrawer').style.right = '0';
  document.getElementById('drawerOverlay').style.display = 'block';

  try {
    const [gradeData, attendanceData, submissionsData] = await Promise.all([
      apiCall(`/api/students/me/grade-calculation/${classId}`, 'GET', null, { 'X-Impersonate': studentId }),
      apiCall(`/api/students/me/attendance?class_id=${classId}`, 'GET', null, { 'X-Impersonate': studentId }),
      apiCall(`/api/admin/assignments?class_id=${classId}`),
    ]);

    const grade = gradeData.final_grade ?? 0;
    const absences = gradeData.absence_count ?? 0;
    const partPts = gradeData.participation_points ?? 0;

    const totalClasses = attendanceData.length;
    const present = attendanceData.filter(a => a.status === 'present' || a.status === 'excused').length;
    const attendancePct = totalClasses > 0 ? Math.round((present / totalClasses) * 100) : 0;

    // Count submissions for this student — use the admin assignments list
    // submissionsData is assignment list; we don't have per-student submission count here
    // so we show a placeholder or fetch separately
    const retosCount = '—';

    document.getElementById('drawerGrade').textContent = grade.toFixed(1);
    document.getElementById('drawerParticipation').textContent = partPts.toFixed(1) + ' pts';
    document.getElementById('drawerAbsences').textContent = absences;
    document.getElementById('drawerAttendancePct').textContent = attendancePct + '%';
    document.getElementById('drawerRetos').textContent = retosCount;
    document.getElementById('drawerContent').style.opacity = '1';
  } catch(e) {
    document.getElementById('drawerContent').textContent = 'Error cargando datos';
  }
}

function closeStudentDrawer() {
  document.getElementById('studentDrawer').style.right = '-400px';
  document.getElementById('drawerOverlay').style.display = 'none';
}
```

- [ ] **Step 3: Update roster rendering to use clickable names**

In `class-dashboard.js`, find the function that renders roster rows. Replace "Ver Detalle" buttons with clickable student names:

```javascript
// Before (remove "Ver Detalle" button):
// <button onclick="viewStudent(${s.id})">Ver Detalle</button>

// After (clickable name):
// <span onclick="openStudentDrawer(${s.id}, '${s.name}')" style="cursor:pointer;color:var(--lime);font-weight:500">${s.name}</span>
```

- [ ] **Step 4: Verify drawer in browser**

Open class dashboard → Alumnos tab → click a student name → drawer should slide in from right with grade, participation, absences, attendance %.

- [ ] **Step 5: Commit**

```bash
git add static/class-dashboard.html static/js/class-dashboard.js
git commit -m "feat: add student detail drawer on name click in Alumnos tab"
```

---

### Task 8: Wire Dashboard JS to New 5-Tab Structure

**Files:**
- Modify: `static/js/class-dashboard.js`

The existing JS functions (loadRoster, loadAttendance, etc.) need to be wired to the new tab IDs and function names introduced in Task 6.

- [ ] **Step 1: Read `class-dashboard.js` — find `showTab` function**

Note the current tab IDs (e.g., `overview`, `roster`, `attendance`, `grades`, `participation`, `retos`, `justificaciones`).

- [ ] **Step 2: Update or remove old `showTab` function**

The new `showTab` function is now inline in `class-dashboard.html` (Task 6 Step 5). Remove or replace the old `showTab` in `class-dashboard.js` to avoid conflict. The JS file's `showTab` can be removed — the HTML inline version handles tab switching.

- [ ] **Step 3: Create `loadEvaluaciones()` that merges exams + retos**

```javascript
async function loadEvaluaciones() {
  const container = document.getElementById('evaluaciones-content');
  if (!container) return;
  
  // Load both exams and retos
  const assignments = await apiCall(`/api/admin/assignments?class_id=${classId}`);
  const exams = assignments.filter(a => a.exam_type === 'exam');
  const onlineExams = assignments.filter(a => a.exam_type === 'online');
  const retos = assignments.filter(a => a.exam_type === 'homework');
  
  container.innerHTML = `
    <div style="margin-bottom:24px">
      <div class="micro-label" style="margin-bottom:12px">Exámenes Presenciales</div>
      <div id="eval-exams-list"></div>
      <button onclick="openNewExamModal()" class="btn-lime" style="margin-top:12px;font-size:13px">+ Nuevo Examen</button>
    </div>
    <div style="margin-bottom:24px">
      <div class="micro-label" style="margin-bottom:12px">Exámenes Online</div>
      <div id="eval-online-list"></div>
    </div>
    <div style="margin-bottom:24px">
      <div class="micro-label" style="margin-bottom:12px">Retos</div>
      <div id="eval-retos-list"></div>
      <button onclick="openNewRetoModal()" class="btn-ghost" style="margin-top:12px;font-size:13px">+ Nuevo Reto</button>
    </div>
    <details style="margin-top:16px">
      <summary class="micro-label" style="cursor:pointer;list-style:none">Categorías de Calificación ▸</summary>
      <div id="eval-categories" style="margin-top:12px"></div>
    </details>
  `;
  
  // Render each section using existing render functions
  renderExamList(exams, 'eval-exams-list');
  renderExamList(onlineExams, 'eval-online-list');
  renderRetosList(retos, 'eval-retos-list');
  loadCategories('eval-categories');
}
```

Note: `renderExamList`, `renderRetosList`, `loadCategories` are existing functions in `class-dashboard.js` — wire them to the new container IDs.

- [ ] **Step 4: Create `initHistorial()` and `loadHistorialAttendance()`**

```javascript
function initHistorial() {
  const dateInput = document.getElementById('historialDate');
  if (!dateInput.value) {
    dateInput.value = new Date().toISOString().split('T')[0];
    loadHistorialAttendance(dateInput.value);
  }
  loadJustificaciones('pending');
}

async function loadHistorialAttendance(date) {
  const container = document.getElementById('historial-attendance-view');
  if (!container || !date) return;
  container.innerHTML = '<div style="color:rgba(255,255,255,0.4);font-size:13px">Cargando...</div>';
  
  try {
    const [students, records] = await Promise.all([
      apiCall(`/api/admin/roster/${classId}`),
      apiCall(`/api/admin/attendance?class_id=${classId}&date=${date}`)
    ]);
    
    const recordMap = {};
    records.forEach(r => { recordMap[r.student_id] = r.status; });
    
    if (students.length === 0) {
      container.innerHTML = '<div style="color:rgba(255,255,255,0.4);font-size:13px">No hay alumnos.</div>';
      return;
    }
    
    const rows = students.map(s => {
      const status = recordMap[s.id] || 'sin registro';
      const statusColor = status === 'present' ? '#c8f135' : status === 'absent' ? '#ff6060' : status === 'late' ? '#f5a623' : 'rgba(255,255,255,0.3)';
      const statusLabel = { present: 'Presente', absent: 'Ausente', late: 'Tarde', excused: 'Justificada' }[status] || status;
      return `<div style="display:flex;justify-content:space-between;align-items:center;padding:10px 0;border-bottom:1px solid rgba(255,255,255,0.06)">
        <span style="font-size:14px">${s.name}</span>
        <span style="font-size:12px;font-weight:600;color:${statusColor}">${statusLabel}</span>
      </div>`;
    }).join('');
    
    container.innerHTML = `<div style="font-size:12px;color:rgba(255,255,255,0.3);margin-bottom:8px">Solo lectura. Para corregir: Alumnos → Asistencia.</div>${rows}`;
  } catch(e) {
    container.innerHTML = '<div style="color:#ff6060;font-size:13px">Error cargando asistencia.</div>';
  }
}
```

- [ ] **Step 5: Create `loadForumEmbedded()` that fetches and renders forum posts**

```javascript
async function loadForumEmbedded() {
  const container = document.getElementById('forum-embedded-content');
  if (!container) return;
  
  // Reuse existing forum rendering logic — call the same function used in forum.js
  // The forum tab renders the same content as the standalone forum page
  container.innerHTML = '<div id="forum-posts-wrapper"></div>';
  
  // Load posts using existing forum post loader
  if (typeof loadForumPosts === 'function') {
    loadForumPosts('forum-posts-wrapper');
  } else {
    // Fallback: show link to standalone forum
    container.innerHTML = '<a href="/forum.html" class="btn-ghost" style="display:inline-block;margin-top:16px">Abrir Foro →</a>';
  }
}
```

- [ ] **Step 6: Update `loadDashboard()` to populate "Hoy" tab data**

After the main dashboard API call, populate the "Hoy" tab cards:

```javascript
// After existing loadDashboard() fetches data:
function renderHoyTab(dashData) {
  // Attendance summary
  const todayPresent = dashData.today_present ?? 0;
  const todayAbsent = dashData.today_absent ?? 0;
  const total = dashData.total_students ?? 0;
  document.getElementById('hoy-attendance-summary').innerHTML = `
    <div style="font-size:28px;font-weight:700;color:var(--lime)">${todayPresent}</div>
    <div style="font-size:13px;color:rgba(255,255,255,0.4)">${todayAbsent} ausentes · ${total - todayPresent - todayAbsent} sin registrar</div>
  `;
  
  // Participation summary
  const pendingCount = dashData.pending_participation_count ?? 0;
  document.getElementById('hoy-participation-summary').innerHTML = `
    <div style="font-size:28px;font-weight:700;color:${pendingCount > 0 ? 'var(--warning)' : 'rgba(255,255,255,0.3)'}">${pendingCount}</div>
    <div style="font-size:13px;color:rgba(255,255,255,0.4)">participaciones pendientes</div>
  `;
  
  // Forum activity — last 3 posts
  const posts = dashData.recent_forum_posts ?? [];
  if (posts.length === 0) {
    document.getElementById('hoy-forum-activity').innerHTML = '<div style="font-size:13px;color:rgba(255,255,255,0.3)">Sin actividad reciente.</div>';
  } else {
    document.getElementById('hoy-forum-activity').innerHTML = posts.slice(0,3).map(p => `
      <div style="padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.06)">
        <div style="font-size:13px;font-weight:500;color:#fff">${p.title}</div>
        <div style="font-size:11px;color:rgba(255,255,255,0.35);margin-top:2px">${p.author_name} · ${p.like_count} ♥</div>
      </div>
    `).join('');
  }
}
```

Note: `today_present`, `today_absent`, `recent_forum_posts` may not be in the current dashboard API response. Check `/api/admin/classes/{id}/dashboard` — if missing, add them to the backend in a follow-up or fall back gracefully with `?? 0`.

- [ ] **Step 7: Verify all tabs in browser**

Check each tab:
- Hoy: 3 cards visible, data loads
- Alumnos: Lista/Asistencia toggle works; Lista shows student names as links; Asistencia shows P/A/T buttons
- Evaluaciones: exams + retos sections visible; "Nuevo Examen" and "Nuevo Reto" buttons work
- Historial: date picker shows read-only attendance; justifications list loads
- Foro: forum posts render (or fallback link)

- [ ] **Step 8: Commit**

```bash
git add static/js/class-dashboard.js
git commit -m "feat: wire 5-tab JS — Hoy, Alumnos toggle, Evaluaciones, Historial, Foro"
```

---

## Phase 3 — API Caching + JS Module Split

### Task 9: Add API Caching Layer to `home.js`

**Files:**
- Modify: `static/js/home.js`

- [ ] **Step 1: Add cache module at top of `home.js`**

Insert at the very top of `home.js`, before any other code:

```javascript
// ===== In-memory API cache (30s TTL) =====
const _cache = {};
async function cachedCall(key, fn, ttlMs = 30000) {
  if (_cache[key] && Date.now() - _cache[key].ts < ttlMs) return _cache[key].data;
  const data = await fn();
  _cache[key] = { data, ts: Date.now() };
  return data;
}
function invalidateCache(keyPrefix) {
  Object.keys(_cache).forEach(k => { if (k.startsWith(keyPrefix)) delete _cache[k]; });
}
```

- [ ] **Step 2: Wrap `openGradeModal` to use cache**

Find `openGradeModal(classId)` or equivalent. Wrap the grade-calc fetch:

```javascript
// Before:
// const data = await apiCall(`/api/students/me/grade-calculation/${classId}`);

// After:
const data = await cachedCall(`grade-calc-${classId}`, () =>
  apiCall(`/api/students/me/grade-calculation/${classId}`)
);
```

- [ ] **Step 3: Invalidate cache on participation submit**

Find the participation submit handler. After a successful submit, add:

```javascript
invalidateCache('grade-calc-');
```

- [ ] **Step 4: Commit**

```bash
git add static/js/home.js
git commit -m "perf: add 30s in-memory cache to home.js grade modal fetches"
```

---

### Task 10: Add API Caching Layer to `class-dashboard.js`

**Files:**
- Modify: `static/js/class-dashboard.js`

- [ ] **Step 1: Add the same cache module at top of `class-dashboard.js`**

```javascript
// ===== In-memory API cache (30s TTL) =====
const _cache = {};
async function cachedCall(key, fn, ttlMs = 30000) {
  if (_cache[key] && Date.now() - _cache[key].ts < ttlMs) return _cache[key].data;
  const data = await fn();
  _cache[key] = { data, ts: Date.now() };
  return data;
}
function invalidateCache(keyPrefix) {
  Object.keys(_cache).forEach(k => { if (k.startsWith(keyPrefix)) delete _cache[k]; });
}
```

- [ ] **Step 2: Cache `loadRoster()` result**

Find `loadRoster()`. Wrap the API call:

```javascript
const students = await cachedCall(`roster-${classId}`, () =>
  apiCall(`/api/admin/roster/${classId}`)
);
```

- [ ] **Step 3: Invalidate roster cache after writing attendance**

Find `saveAttendance()`. After successful save:

```javascript
invalidateCache(`roster-${classId}`);
invalidateCache(`dashboard-${classId}`);
```

- [ ] **Step 4: Cache dashboard data**

In `loadDashboard()`:

```javascript
const data = await cachedCall(`dashboard-${classId}`, () =>
  apiCall(`/api/admin/classes/${classId}/dashboard`)
);
```

- [ ] **Step 5: Invalidate on any write**

After saving grades, approving participation, or any POST/PATCH:

```javascript
invalidateCache(`dashboard-${classId}`);
```

- [ ] **Step 6: Commit**

```bash
git add static/js/class-dashboard.js
git commit -m "perf: add 30s in-memory cache to class-dashboard.js for roster and dashboard"
```

---

### Task 11: Fix Remaining Color Violations

**Files:**
- Modify: `static/js/home.js`
- Modify: `static/js/class-dashboard.js`
- Modify: `static/index.html`
- Modify: `static/class-dashboard.html`

- [ ] **Step 1: Search for all color violations**

```bash
grep -rn "text-violet\|bg-violet\|#667eea\|#764ba2\|EA8251\|9C4927" static/
```

Note every file and line number.

- [ ] **Step 2: Replace all `text-violet-*` with `style="color:var(--warning)"`**

In JS files, replace any `.className` assignments or template literals that add `text-violet-500`:

```javascript
// Before:
// element.className = '... text-violet-500 ...'

// After:
// element.style.color = 'var(--warning)';
// OR in template literals:
// style="color:var(--warning)"
```

- [ ] **Step 3: Replace `#667eea` and `#764ba2`**

These are the purple gradient colors. Replace with lime/dark:
- Primary gradient: `#c8f135` → `#a8d020`
- As text color: `#2b2b2b` (dark)

- [ ] **Step 4: Replace `#EA8251` and `#9C4927`**

- `#EA8251` (orange) → `#c8f135` (lime) for accents
- `#9C4927` (rust) → `#2b2b2b` (dark) for dark elements

- [ ] **Step 5: Run the search again to confirm zero violations**

```bash
grep -rn "text-violet\|bg-violet\|#667eea\|#764ba2\|EA8251\|9C4927" static/
```
Expected: no output.

- [ ] **Step 6: Commit**

```bash
git add static/
git commit -m "fix: remove all orange/violet color violations, enforce lime+dark palette"
```

---

## Phase 4 — Polish & Validation

### Task 12: Verify Backend Dashboard API Has `today_present`, `today_absent`, `recent_forum_posts`

**Files:**
- Read: `routes/admin.py` (dashboard endpoint)
- Modify: `routes/admin.py` if fields are missing

- [ ] **Step 1: Read the `/api/admin/classes/{id}/dashboard` endpoint**

In `routes/admin.py`, find `@router.get("/classes/{class_id}/dashboard")` and check what it returns.

- [ ] **Step 2: Add today's attendance counts if missing**

If `today_present` / `today_absent` are not in the response, add:

```python
from datetime import date

today_str = date.today().isoformat()
today_records = db.query(Attendance).filter(
    Attendance.class_id == class_id,
    Attendance.date == today_str
).all()
today_present = sum(1 for r in today_records if r.status in ('present', 'late', 'excused'))
today_absent = sum(1 for r in today_records if r.status == 'absent')
```

Add to response dict:
```python
"today_present": today_present,
"today_absent": today_absent,
```

- [ ] **Step 3: Add recent forum posts if missing**

```python
recent_posts = db.query(ForumPost).filter(
    ForumPost.class_id == class_id
).order_by(ForumPost.created_at.desc()).limit(3).all()

"recent_forum_posts": [
    {"title": p.title, "author_name": p.author.name, "like_count": p.like_count}
    for p in recent_posts
],
```

- [ ] **Step 4: Test the endpoint**

```bash
# Get a valid class ID from DB first
curl -s -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/admin/classes/1/dashboard | python3 -m json.tool | grep -E "today_|recent_forum"
```
Expected: `today_present`, `today_absent`, `recent_forum_posts` in response.

- [ ] **Step 5: Commit**

```bash
git add routes/admin.py
git commit -m "feat: add today attendance counts and recent forum posts to dashboard API"
```

---

### Task 13: Mobile QA Pass

**Files:** No code changes — verification only.

- [ ] **Step 1: Open Chrome DevTools → Toggle device toolbar (Cmd+Shift+M)**

Test at 390×844 (iPhone 14 viewport).

- [ ] **Step 2: Student portal checks**

- Class cards fit without horizontal scroll
- Participation button is large, tap-friendly
- Bug FAB not overlapping important content
- Pending work section readable
- Forum posts readable

- [ ] **Step 3: Teacher dashboard checks**

- Tab nav scrolls horizontally on mobile (confirm `-webkit-overflow-scrolling:touch`)
- Alumnos/Asistencia mode toggle buttons large enough to tap
- Student detail drawer opens correctly (360px wide = full screen on small phones)
- Drawer close (✕) is tappable
- "Guardar Asistencia" button is full-width

- [ ] **Step 4: Fix any mobile issues found**

Common fixes:
- Tap targets under 44px: add `min-height:44px` or `padding` to buttons
- Text overflow: add `overflow:hidden;text-overflow:ellipsis;white-space:nowrap` where needed
- Drawer too narrow on 320px screens: add `max-width:100vw`

- [ ] **Step 5: Commit any fixes**

```bash
git add static/
git commit -m "fix: mobile layout polish — tap targets, drawer width, tab scroll"
```

---

### Task 14: End-to-End Flow Verification

**Files:** No code changes — verification only.

- [ ] **Step 1: Test teacher preview mode**

1. Log in as teacher → class dashboard
2. Click "Vista de Estudiante"
3. Verify student portal loads with impersonated data
4. Verify bug FAB is hidden (role = teacher during preview)
5. Return to teacher panel

- [ ] **Step 2: Test exam grading modal**

1. Teacher → Evaluaciones tab → open an existing exam
2. Type a student name in search → verify filter works
3. Tab to score input → enter score → Enter to save
4. Verify student moves from "Por Calificar" to "Calificados"
5. Esc to close

- [ ] **Step 3: Test online exam flow**

1. Create an online exam in Evaluaciones tab
2. Upload exam HTML via the upload button
3. As student (via preview), navigate to `/exam/{id}`
4. Verify exam loads in iframe
5. Submit exam → verify receipt and grade created

- [ ] **Step 4: Test forum casino toasts**

1. As student, post to forum
2. As teacher, like the post
3. Verify no points awarded (teacher excluded from casino)
4. As second student, like the post
5. Verify toast notification appears

- [ ] **Step 5: Test participation tap logic**

1. Student → participation button
2. Single tap → ×1
3. Quick double tap → ×2
4. Triple tap → ×3
5. Teacher → approve → verify grade points added

- [ ] **Step 6: Document any regressions**

If any test fails, create a fix commit before marking this task complete.

---

### Task 15: Final Cleanup + Production Push

**Files:**
- Verify: `.gitignore` has `.superpowers/`
- Verify: no stray `console.log` debug statements

- [ ] **Step 1: Check .gitignore**

```bash
grep "superpowers" .gitignore
```
Expected: `.superpowers/` is present.

- [ ] **Step 2: Remove debug console.logs**

```bash
grep -n "console.log" static/js/home.js static/js/class-dashboard.js | grep -v "// " | head -20
```

Remove or comment any debug logs that log sensitive data (user tokens, passwords). Informational logs are fine.

- [ ] **Step 3: Final lint check**

```bash
# Check for any remaining TODO/FIXME placeholders introduced during this work
grep -rn "TODO\|FIXME\|HACK\|XXX" static/js/home.js static/js/class-dashboard.js
```

- [ ] **Step 4: Verify server starts cleanly**

```bash
uvicorn app.main:app --reload 2>&1 | head -20
```
Expected: no Python errors, server starts on port 8000.

- [ ] **Step 5: Final commit + push**

```bash
git add -A
git status  # verify only expected files changed
git commit -m "chore: final cleanup — remove debug logs, verify gitignore"
# Only push when user confirms:
# git push origin main
```

---

## Spec Self-Review Notes

### Coverage check
- [x] Brand tokens (Graphik, CSS vars, lime/dark/cream) — Tasks 1, 3
- [x] teacher_email in /api/config — Task 2
- [x] Student portal rebrand (colors, emoji→SVG, font) — Task 3
- [x] Pending work section (conditional, correct order) — Task 4
- [x] admin.html + forum.html rebrand — Task 5
- [x] 5-tab dark teacher dashboard structure — Task 6
- [x] Student detail drawer (name clickable) — Task 7
- [x] JS wired to new 5-tab structure — Task 8
- [x] API caching (home.js + class-dashboard.js) — Tasks 9, 10
- [x] Color violations removed — Task 11
- [x] Backend API fields for Hoy tab — Task 12
- [x] Mobile QA — Task 13
- [x] E2E flow verification — Task 14
- [x] Final cleanup — Task 15

### Notes
- **JS file splitting** (home-*.js, dashboard-*.js modules) from the spec is deferred — the caching layer (Tasks 9-10) addresses the main performance concern without the risk of a full module refactor. The split can be done as a follow-up once the rebrand is stable.
- **`today_status` on roster students**: The `renderHoyTab` in Task 8 uses `dashData.today_present` from the dashboard endpoint (not per-student `today_status`). This is simpler and doesn't require per-student status on the dashboard call.
- **Forum embedded in Foro tab**: If `loadForumPosts` is not exported from `forum.js` into `class-dashboard.js`, the fallback link to `/forum.html` is shown. The full embed can be wired in a follow-up.
