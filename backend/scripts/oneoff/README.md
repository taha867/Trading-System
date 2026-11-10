# One-off production data fixes

Small, guarded scripts for single data corrections that were run against the production database. They
are kept here as a record (see `/PRODUCTION_CHANGES_LOG.md` at the repo root) — **they have already been
applied**. Each one checks that production still looks exactly as it did when it was written and aborts
(writing nothing) if it doesn't, so re-running one is harmless.

Conventions every script follows:

- The connection string comes from the `PROD_DSN` environment variable (`postgresql://user:password@host/db`).
  Never put it in a file.
- Default is a **dry run**: it prints exactly what would change, inside a transaction that is rolled back.
  `--apply` writes, in one transaction, and checks the result before committing.
- Preconditions (row ids, current values, amounts) are asserted before anything is written.

```
PROD_DSN='postgresql://…' backend/.venv/bin/python backend/scripts/oneoff/<script>.py [--apply]
```
