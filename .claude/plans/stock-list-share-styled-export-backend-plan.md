# Stock List Share v2 — Backend: Shop setting

## Context

Part B of `.claude/specs/stock-list-share-styled-export.md`. `Setting` was planned as a `PLAN.md` Phase 0 entity but never built. This adds it now, with one field (`shop_name`), so the Stock List export (Part C) can print the shop's name at the top of every page. **Status: complete and verified.**

## Change made

- `backend/src/models.py`: added `Setting(Base)` — `id` (singleton, always `1`), `shop_name: str | None`. Lives in the shared `models.py` (no dedicated domain package), matching CLAUDE.md's own note that this entity has no domain owner.
- `backend/src/settings.py` (new, flat module — matches `crud.py`/`pagination.py`/`exceptions.py`'s already-flat, cross-cutting placement): `SettingRead`/`SettingUpdate` schemas, `get_or_create_setting(db)` (fetches `id=1`, creates it on first read if missing), and a router with `GET /settings` / `PUT /settings`. No `prefix=` set on the router itself — matches this codebase's actual convention (confirmed by reading `main.py`: every domain router is prefix-less internally, with `main.py` supplying the prefix at the `include_router` call site).
- `backend/src/main.py`: mounted `settings_router` at `/settings`.
- `backend/migrations/env.py`: added `Setting` to the `src.models` import so autogenerate could see it.
- New migration `2026-08-17_add_setting.py` — one table, no FKs, composite of nothing (`id` PK, nullable `shop_name`).

## Not changed

Every other domain's router/service/schemas; no changes to `src/config.py` (kept separate — that file is env-based Pydantic settings, this is a DB-backed runtime value).

## Verification performed

Against the running dev server (port 8001), with a real bearer token:
1. `GET /settings` before any row existed — returned `{"shop_name": null}`, `200` (confirmed get-or-create works, no 404).
2. `PUT /settings {"shop_name": "Shakeel Mobile Accessories"}` — `200`, returned the updated value.
3. `GET /settings` again — confirmed the value persisted.
4. `alembic current` confirmed the new migration applied cleanly on top of the existing head.
5. `python -c "from src.main import app"` confirmed no import/wiring errors after adding the new router.

## Follow-ups

None — this is deliberately minimal (one field). Add more fields to `Setting`/`SettingUpdate` directly if more shop-wide settings are needed later; the get-or-create singleton pattern already supports that with no structural change.
