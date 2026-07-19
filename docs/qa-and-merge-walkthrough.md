# UI/UX Rebrand — QA & Merge Walkthrough

Branch: `feature/ui-ux-rebrand`  
Worktree: `.worktrees/ui-ux-rebrand`

---

## How git worktrees work (read this first)

A worktree is a second checkout of the same repo in a different folder. The worktree and the main repo **share one git history** — they are not separate repos. Because of this:

- **You cannot `git switch main` from inside the worktree.** `main` is already checked out in the parent folder, and git refuses to check out the same branch twice. You'll get: `fatal: 'main' is already checked out at '...'`
- **All branch operations (merge, push, switch) must be done from the main repo folder**, not from inside the worktree.
- The worktree stays on `feature/ui-ux-rebrand` the entire time. That's intentional.

```
/school-app/                   ← main repo, branch: main
/school-app/.worktrees/
  ui-ux-rebrand/               ← worktree, branch: feature/ui-ux-rebrand
```

---

## Step 0 — Start the server

The worktree directory doesn't have a `.env` file — it lives only in the main repo. Fix this once with a symlink, then start the server:

```bash
cd /Users/marionomics/Documents/trabajo/coding/school-app/.worktrees/ui-ux-rebrand

# One-time: create a symlink so the worktree can see the .env
ln -s ../../.env .env

# Activate venv and start
source ../../venv/bin/activate
uvicorn app.main:app --reload
```

Leave this terminal running throughout QA. Wait for:

```
INFO:     Application startup complete.
```

Open **http://localhost:8000** in Chrome.

---

## Task 13 — Mobile QA (390×844)

### Open DevTools device emulation

1. Press `Cmd+Opt+I` to open DevTools
2. Click the phone/tablet icon in the top-left of DevTools (or `Cmd+Shift+M`)
3. Set dimensions to **iPhone 14 Pro** (390×844) — or type `390` × `844` manually
4. Hard-refresh: `Cmd+Shift+R`

### Student landing page (`/`)

Log in as a student. Verify:

- [ ] Class cards stack vertically, text doesn't overflow
- [ ] "Ver calificación" button is tappable (not too small)
- [ ] Participation form fits without horizontal scroll
- [ ] Assignment cards are readable
- [ ] Forum posts load and scroll smoothly

### Teacher class dashboard (`/admin/class/{id}`)

Log in as teacher, click a class card. Check each tab:

- [ ] **Hoy** — loads on open, attendance summary shows numbers or "—", forum activity section visible
- [ ] **Alumnos** — student list renders, search input full-width, names don't clip
- [ ] **Evaluaciones** — participation list loads, grades and retos sections appear
- [ ] **Historial** — date picker and attendance list render; justificaciones section shows with filter buttons
- [ ] **Foro** — fallback link visible (or embedded forum if configured)

### Modals on mobile

- [ ] Click a student name in Alumnos → drawer opens, has close button, content scrollable
- [ ] Click "Calificar" on an exam → modal opens, search bar usable, keyboard doesn't cover input
- [ ] Click a reto card → submissions modal opens, table scrolls horizontally if needed

### Red flags

| Symptom | Status |
|---|---|
| Horizontal scrollbar appears anywhere | Bug |
| Buttons smaller than ~44px tap target | Bug |
| Text truncated mid-word (not `…`) | Bug |
| Modal backdrop doesn't cover full screen | Bug |

---

## Task 14 — E2E Flow Verification

Run these on desktop (no device emulation needed).

### Flow 1: Take attendance → verify Hoy tab updates

1. Teacher → open a class dashboard
2. Click **Hoy** tab — note the "Presentes hoy" / "Ausentes hoy" numbers (likely `0 / 0`)
3. Click **Historial** tab → date defaults to today
4. Mark 2 students **Presente**, 1 student **Ausente** → click "Guardar asistencia"
5. Click **Hoy** tab — numbers should now read **Presentes: 2 / Ausentes: 1**

> The dashboard uses a 30s cache. If numbers look stale, wait 30s and re-click the tab.

### Flow 2: Justification review

1. Open an incognito window, log in as a student
2. Go to `/` → find a class with an absence → click "Justificar ausencia"
3. Fill in the justification text → submit
4. In the teacher window → **Historial** tab → "Justificaciones pendientes" should show the entry
5. Click "Aprobar" → entry disappears from pending list
6. Back in the student window, the absence should now show as "excused"

### Flow 3: Exam grading (keyboard-first modal)

1. Teacher → **Evaluaciones** tab → "Nuevo Examen Presencial" form → enter a name → "Crear y Calificar"
2. Grading modal opens immediately
3. Type part of a student's name in the search bar
4. Press **Tab** or **↓** to move focus to the score input
5. Type a score → press **Enter**
6. Student moves from "Por Calificar" to "Calificados" without closing the modal
7. Press **Esc** from score input → focus returns to search
8. Press **Esc** from search → modal closes

### Flow 4: Online exam shell

> Requires an `online`-type exam with an uploaded HTML file (needs R2). If none exists in dev, this flow is a smoke test only.

1. Teacher → **Evaluaciones** tab → click "Vista previa" on an online exam
2. Shell at `/exam/{id}` loads — top bar shows `👁 Vista Previa — [teacher name]`
3. Preview banner visible below top bar
4. Loading spinner appears; exam loads (or shows error if no R2 file — that's acceptable in dev)

### Flow 5: Student preview (impersonation)

1. Teacher → main admin panel (`/admin`)
2. Click "Vista de Estudiante" → select a class → "Ver como estudiante"
3. Redirected to `/` with a "MODO VISTA PREVIA" banner
4. Class cards show that student's grades and data (not the teacher's)
5. Participation form is hidden
6. Navigate back to `/admin` — teacher view restored

### Flow 6: Casino toasts (forum)

1. Open two incognito windows, log in as two different students
2. Student A creates a forum post
3. Student B likes the post → a toast appears bottom-right with points info
4. Verify toast styles: normal (dark), mini (✨), double (🎰), jackpot (💰) all use the dark/lime brand palette — no orange or violet

---

## Step 5 — Merge to main and push

> **Important:** You must run these commands from the **main repo**, not from inside the worktree. `git switch main` inside the worktree will fail because main is already checked out in the parent folder.

```bash
# 1. Confirm the worktree is clean (run this from inside the worktree)
cd /Users/marionomics/Documents/trabajo/coding/school-app/.worktrees/ui-ux-rebrand
git status
# Expected: nothing to commit, working tree clean

# 2. Move to the main repo folder — this is where you do all branch operations
cd /Users/marionomics/Documents/trabajo/coding/school-app

# 3. You're already on main here. Merge the rebrand branch.
git merge feature/ui-ux-rebrand

# 4. Push (triggers Railway auto-deploy)
git push
```

Watch the Railway dashboard — build goes green in ~2 minutes. After deploy, open the Railway URL and spot-check the class dashboard on mobile.

### If there are merge conflicts

Unlikely (main hasn't changed during the rebrand). If they do appear:

```bash
# Open conflicted files, keep the rebrand version for all UI/JS files
git add .
git commit
```

---

## Step 6 — Cleanup (after merge)

```bash
# Remove the worktree
git worktree remove .worktrees/ui-ux-rebrand

# Delete the branch
git branch -d feature/ui-ux-rebrand
```

---

## Commits merged (reference)

| Hash | Description |
|---|---|
| `81db764` | chore: remove debug console.logs |
| `2e07e4c` | feat: add today attendance counts + recent forum posts to dashboard API |
| `9d84077` | fix: remove all off-brand color violations |
| `f251dc3` | perf: 30s cache in class-dashboard.js |
| `68bd27b` | perf: 30s cache in home.js |
| `6c0a81c` | fix: loadHistorialAttendance + loadEvaluaciones error handling |
| `cc05413` | fix: renderHoyTab detail fallback + showTab condition |
| `2ea31da` | feat: wire 5-tab JS (Hoy, Evaluaciones, Historial, Foro, Alumnos) |
