# Reference: Modular FastAPI Structure (from the pasted example)

This documents the folder structure and file responsibilities from the
example project you shared (a Firebase-auth + SQLite student/GitHub-activity
tracker, refactored from one monolithic `api.py` into a modular layout). It
is **not** the structure used by this repo's `backend/` — see
`backend/FOLDER_STRUCTURE.md` for that. This file exists purely as a
reference to that other pattern.

## Folder tree

```
project-root/
├── main.py                 # FastAPI app entry point
├── schemas.py               # every Pydantic request-body model, in one place
├── db.py                     # get_connection(), init_db() — not shown in the example, assumed pre-existing
├── collector.py                # background data-collection job — pre-existing
├── permissions.py                # grant_default_permissions(), migrate_existing_users() — pre-existing
├── export_helpers.py               # generate_pdf/generate_excel/generate_word — pre-existing
├── config.yaml                       # runtime-editable app config (org name, deadlines, etc.)
├── firebase-credentials.json           # Firebase service-account key (never committed)
├── data/
│   └── github_activity.db                # SQLite database file
├── core/
│   ├── __init__.py                         # empty
│   ├── helpers.py                            # shared DB helpers + small utilities
│   └── dependencies.py                         # FastAPI auth/role Depends() functions
└── routers/
    ├── __init__.py                              # empty
    ├── auth.py                                    # /auth/*
    ├── admin.py                                     # /health, /admin/*
    ├── teacher.py                                     # /teacher/*, /history/*
    ├── student.py                                       # /my/*
    ├── export.py                                          # /export/*
    └── archive.py                                          # archive/restore endpoints, all domains
```

## What goes in each file

### `core/helpers.py`
Anything every router needs and none of them owns:
- `query(sql, params)` — run a SELECT, return `list[dict]`
- `execute(sql, params)` — run an INSERT/UPDATE/DELETE
- `now_utc()` — current UTC time as ISO string
- `generate_password()` — random secure password
- Module-level constants used across routers (`DB_PATH`, `UMT_DOMAIN`)

Rule of thumb: if two or more router files would otherwise duplicate a
function, it belongs here instead.

### `core/dependencies.py`
Every `Depends()` used by more than one router, specifically auth/role
gating:
- `verify_firebase_token()` — validates the bearer JWT against Firebase
- `get_current_user()` — decodes the token, enforces the email-domain rule,
  loads the full user row from the DB
- `require_admin` / `require_teacher` / `require_student` — role gates, each
  a thin wrapper around `get_current_user`
- `require_permission(key)` — a dependency **factory** (returns a `checker`
  function) for fine-grained per-permission checks, used alongside the role
  gates rather than instead of them

Nothing route-specific goes here — a dependency that only one router uses
(e.g. `valid_item`-style "fetch or 404") would instead live at the top of
that router file, not in `core/`.

### `schemas.py`
Every Pydantic request-body model for the whole app, flat, no matching
`Read`/`Update` split (this example returns raw dicts from `query()`, not
`response_model`-typed objects — that's a deliberate simplification specific
to this smaller project). One class per distinct POST/PUT/PATCH body,
grouped loosely by the router that consumes it, e.g. `ChangePasswordBody`
(auth), `AssessmentBody`/`AssessmentUpdate` (teacher), `ConfigUpdate`
(admin).

### `routers/<name>.py`
One file per role/concern, **not** per data entity. Each file:
1. Declares `router = APIRouter(prefix="...", tags=["..."])` (prefix omitted
   when routes need mixed prefixes, e.g. `admin.py` mixes `/health` and
   `/admin/*`).
2. Imports only what it needs from `core.dependencies`, `core.helpers`,
   `schemas`, and any pre-existing top-level modules (`collector`,
   `permissions`, `export_helpers`).
3. Contains route functions grouped under `# ── SECTION ──` comment banners
   when a file covers several sub-concerns (e.g. `admin.py` has GITHUB TOKEN
   MANAGEMENT / TEACHER MANAGEMENT / COURSE MANAGEMENT / COLLECTOR / CONFIG /
   RIGHTS MANAGEMENT sections).
4. Talks to the database only through `core.helpers.query`/`execute` (or a
   raw `db.get_connection()` for a multi-statement transaction, as
   `admin.py`'s CSV upload does) — never duplicates that plumbing.

Which router a route belongs in is decided by **who calls it**, not what
table it touches: `/admin/sections` (admin creating a section on a
teacher's behalf) lives in `admin.py`, while `/teacher/sections` (a teacher
creating their own) lives in `teacher.py`, even though both write the same
`sections` table.

- **`routers/auth.py`** — identity/session endpoints any logged-in user can
  call: `/auth/me`, `/auth/complete-first-login`, `/auth/update-last-login`,
  `/auth/change-password`.
- **`routers/admin.py`** — everything gated by `require_admin`: health
  check, GitHub token CRUD, teacher CRUD (+ CSV bulk-create), course CRUD,
  admin-side section creation, collector trigger/logs, config get/update,
  permission (rights) management.
- **`routers/teacher.py`** — everything gated by `require_teacher` (admins
  pass too): courses/sections/students scoped to that teacher, assessment
  CRUD, GitHub repo-collaborator management, analytics/leaderboard/at-risk
  queries, notes, collector trigger, score history.
- **`routers/student.py`** — everything gated to the logged-in student's own
  `linked_id`: their assessments, progress, leaderboard position, score
  history. Never accepts a `student_id` param — always derives it from
  `get_current_user()`.
- **`routers/export.py`** — CSV/PDF/Excel/Word generation. Route handlers
  build the query (via small private `_scores_context()` /
  `_at_risk_context()` helpers local to this file) and hand the rows to
  `export_helpers.generate_pdf/excel/word`; the file format is the only
  thing that varies per route.
- **`routers/archive.py`** — soft-delete (`is_active = 0`) and restore for
  every entity, plus cascade rules (archiving a course archives its
  sections and assessments too). Kept separate from `admin.py`/`teacher.py`
  because archive/restore is a distinct, symmetric concern that would
  otherwise double the length of those files.

### `main.py`
Composition root, nothing else:
1. `load_dotenv()`
2. Initialize Firebase (`firebase_admin.initialize_app`)
3. Run one-time idempotent startup migration (`init_db`,
   `migrate_existing_users`)
4. Create `app = FastAPI(...)`, add `CORSMiddleware`
5. Import each router and `app.include_router(...)` it — one line per file
   in `routers/`

No route logic, no DB helper logic, no schema definitions ever live here.

## Migration notes from the example (for that project, not this repo)

- Keep the old `api.py` around, emptied to a comment, so `git log` shows the
  transition instead of a file disappearing.
- Old run command `uvicorn api:app --reload --port 8000` →
  new command `uvicorn main:app --reload --port 8000`.
- Two commits: one adding `core/`, `routers/`, `schemas.py`, `main.py`; one
  emptying `api.py`.
