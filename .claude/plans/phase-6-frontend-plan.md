# Phase 6 Frontend Implementation Plan — Payments

## Context

`.claude/specs/phase-6-frontend.md` is a fully-written, code-verified spec for Phase 6's frontend (`PaymentAccount` CRUD, a record-payment flow, an account-balances view, a read-only transaction history), written against the backend already implemented and verified in `.claude/plans/phase-6-backend-plan.md`. This plan executed that spec end to end and reached `PLAN.md`'s Phase 6 done-when line: recording a payment updates the account's balance and, when a party is linked, that party's credit/debit — in one action. **Status: complete and verified** — see the walkthrough in Verification below.

A Plan-agent reconciliation pass, run before writing any code, checked the spec's illustrative drafts against the real current file contents and caught three issues the spec's draft would have introduced as-written:

1. **`PaymentForm.jsx`'s two-column grids would have broken inside its `Sheet`.** `components/ui/sheet.jsx`'s `SheetContent` caps at a few hundred px wide, but Tailwind's `md:` breakpoint keys off viewport width, not the panel's rendered width — `md:grid-cols-2` would activate on any normal desktop viewport and squeeze two columns into a narrow Sheet. Fixed: the form is single-column throughout (`flex flex-col gap-4`/`gap-3`), matching `CrudDrawer.jsx`'s established convention — the only other Sheet-hosted form in the codebase.
2. **An empty-string `SelectItem` value is a real Radix constraint.** Radix Select reserves `value=""` internally to mean "nothing selected" — a "clear the filter" option needs a real sentinel value instead. Fixed: `PaymentTransactionList.jsx`'s "Filter by account" select uses `'all'` as its default and first option, not `''`.
3. **Direction badge color broke the established two-value-badge convention.** Every existing two-value status/role/source badge in the codebase (`PurchaseOrderList`'s source badge, `PartyRoleBadges`, cargo's cost-basis badge) uses `variant="secondary"` uniformly, label-text-only — `destructive` is reserved for a genuinely negative financial state. Fixed: the direction badge is `variant="secondary"` for both `in` and `out`.

A fourth issue surfaced during implementation itself, not caught by the reconciliation pass (which worked from the spec's hand-drafted `FormCombobox.jsx` before the real shadcn `command.jsx` existed): the spec's draft manually rendered a `<Check>` icon inside each `CommandItem`, but the actual generated `components/ui/command.jsx` (from `npx shadcn@latest add command`) already renders its own trailing `CheckIcon`, toggled via a `data-checked` attribute on the item (`group-data-[checked=true]/command-item:opacity-100`) — the standard shadcn combobox pattern. Fixed: `FormCombobox.jsx` drops the manual `Check` import entirely and passes `data-checked={option.value === value}` to `CommandItem` instead, letting the primitive's own checkmark do the work.

Also caught and fixed during implementation, unprompted by the reconciliation pass: every file the `shadcn` CLI generated (`command.jsx`, `popover.jsx`, and their pulled-in dependencies `textarea.jsx`, `input-group.jsx`) started with an unused `import * as React from "react"` — `.claude/skills/frontend-design-system/SKILL.md` explicitly calls out stripping this from every new primitive (React 19's JSX transform doesn't need it, and every existing primitive already has it removed). All four were stripped.

Full design rationale lives in `.claude/specs/phase-6-frontend.md`.

---

## Files created

- `frontend/src/components/custom/FormCombobox.jsx` — generic `Popover`+`Command` searchable combobox (not payments-specific), built on the newly-added shadcn primitives.
- `frontend/src/components/payments/PaymentAccountCrudConfig.jsx` — `CrudTable`/`CrudDrawer` config for `PaymentAccount`, mirroring `PartyCrudConfig.jsx`'s shape for a hand-written (non-generic-factory) backend entity. `payment_method_id` and `opening_balance` both `editableOnUpdate: false`.
- `frontend/src/components/payments/PaymentAccountList.jsx` — wraps the static config, injecting `payment_method_id`'s live select options/display name and an appended `balance` column joined in from `usePaymentAccountBalances()` by id (balance isn't a field on `PaymentAccountRead`, only on the separate `/balances` endpoint).
- `frontend/src/components/payments/PaymentTransactionList.jsx` — read-only, paginated, with the `'all'`-sentinel account filter and plain-`secondary` direction badges (fixes #2/#3 applied).
- `frontend/src/components/payments/form/PaymentForm.jsx` — hand-written record-payment form (single-column, fix #1 applied), with a `hasReference` checkbox gating a document-type select + the searchable `FormCombobox` reference picker, and a payload builder that omits unset optional fields entirely rather than sending `null`/`''` (mirrors `PurchaseOrderForm.onSubmit`'s conditional-field pattern).
- `frontend/src/containers/PaymentsContainer.jsx` — page chrome, composes `PaymentAccountList` + `PaymentTransactionList`, and the "Record payment" `Sheet`.
- `frontend/src/pages/PaymentsPage.jsx` — two-line pass-through, same shape every page file uses.
- `frontend/src/components/ui/command.jsx`, `frontend/src/components/ui/popover.jsx` (+ pulled-in `textarea.jsx`, `input-group.jsx`) — via `npx shadcn@latest add command popover`, `cmdk` added to `package.json`.

## Files changed

- `frontend/src/utils/queryKeys.js` — added `paymentAccountKeys` (`all/lists/list` + `balances()`) and `paymentTransactionKeys` (`all/lists/list`, no `detail`).
- `frontend/src/utils/constants.js` — added `PAYMENT_DIRECTION`/`PAYMENT_DIRECTION_OPTIONS` and `PAYMENT_REFERENCE_TYPE`/`PAYMENT_REFERENCE_TYPE_OPTIONS` (`expense` omitted — no domain until Phase 7).
- `frontend/src/services/paymentsService.js` — added `listPaymentAccounts`, `createPaymentAccount`, `updatePaymentAccount`, `deletePaymentAccount`, `getPaymentAccountBalances` (returns a plain array, not `{items,total,...}`), `listPaymentTransactions`, `createPaymentTransaction`. `PaymentMethod*` functions untouched.
- `frontend/src/hooks/paymentsHooks/paymentsQueries.js` — added `usePaymentAccounts`, `usePaymentAccountBalances`, `usePaymentTransactions`.
- `frontend/src/hooks/paymentsHooks/paymentsMutations.js` — added `useCreatePaymentAccount`, `useUpdatePaymentAccount`, `useDeletePaymentAccount`, `useCreatePaymentTransaction` (conditionally invalidates `partyKeys.statement(variables.party_id)` only when a party was linked, mirroring `useCreateSalesOrder`).
- `frontend/src/validations/paymentsSchemas.js` — added `paymentAccountCreateSchema`, `paymentAccountUpdateSchema` (its own object, not `.partial()` — backend's `PaymentAccountUpdate` rejects `payment_method_id`/`opening_balance` outright), `paymentTransactionCreateSchema` (both-or-neither `reference_type`/`reference_id` `.test()`, mirroring the backend's `model_validator`).
- `frontend/src/components/custom/index.js` — exported `FormCombobox`.
- `frontend/src/App.jsx` — new `/payments` route inside the existing `ProtectedRoute` group.
- `frontend/src/components/Navbar.jsx` — new `NAV_LINKS` entry, `{ to: '/payments', label: 'Payments' }`, after "Sales Orders" and before "Parties".

## Not changed

`backend/` (entire tree — already implemented, per `phase-6-backend-plan.md`), `frontend/src/components/payments/PaymentMethodCrudConfig.js`, `frontend/src/containers/SettingsContainer.jsx`, `frontend/src/components/common/CrudTable.jsx`/`CrudDrawer.jsx`/`PaginationControls.jsx`/`ConfirmDeleteDialog.jsx`, `frontend/src/components/custom/FormField.jsx`/`FormSelect.jsx`/`FormMultiSelect.jsx`, `frontend/src/hooks/partyHooks/*`, `frontend/src/hooks/salesHooks/*`, `frontend/src/hooks/purchasingHooks/*`, every other domain's frontend code.

---

## Verification performed

1. **Lint**: `npx eslint` across every new/changed file — 0 errors. One pre-existing warning class (`react-hooks/incompatible-library` on RHF's `watch()`) appears in `PaymentForm.jsx`, confirmed to also appear identically in the already-shipped `PurchaseOrderForm.jsx`/`SalesOrderForm.jsx` — not a regression.
2. **Build**: `npm run build` — clean, no errors.
3. **Functional, end-to-end, against the real dev backend** (started fresh: `uvicorn src.main:app --port 8001`, Postgres already running via the existing `docker-compose.yml`; frontend via `npm run dev`), driven through an actual browser:
   - Created a `PaymentAccount` ("Cash drawer" / Cash, `opening_balance=5000`) via the new `/payments` page's `Add account` drawer — the `payment_method_id` select correctly listed the four seeded methods (Bank/JazzCash/Easypaisa/Cash) injected live by `PaymentAccountList`. Balance column showed `₨5,000.00` immediately, sourced from `/payment-accounts/balances`, not re-derived client-side.
   - Recorded a "Money in" payment of `1000` against that account with no party/reference — balance moved to `₨6,000.00`; the transaction row showed `In` (plain `secondary` badge), `Cash drawer`, `—` for party and reference.
   - Recorded a "Money out" payment of `500` against the same account, linked to party "Test Vendor A" and, via the searchable reference combobox, "Sales order → #3 — 2026-08-08 — Phase 4 QA Customer" (typed "Phase 4" and confirmed the list live-filtered to exactly that one order before selecting it). Balance moved to `₨5,500.00`; the transaction row showed `Out`, `Test Vendor A`, `SO #3`.
   - Opened Test Vendor A's Party Statement and confirmed the new ledger row: `2026-08-10, Accounts Payable, payment_transaction #4, Debit ₨500.00`, running balance moved from `89,769.85` to `90,269.85` — a debit on a payable-holding party correctly moves their balance *up* (toward "we owe them less"), confirming the account leg and party leg both posted with the sign convention the backend spec documents, and that they're two independent ledger rows (the account balance and the party balance each moved by exactly the transaction amount, not double-counted).
   - Confirmed `PaymentTransactionList` has no edit/delete controls on any row, and the `Sheet` form rendered single-column at full desktop width (fix #1's regression check) rather than attempting the spec draft's two-column grid.
4. **Testing-environment note, not a product defect**: mid-session, Chrome's `Page.captureScreenshot` intermittently timed out for a few seconds right after interacting with a Radix `Select` inside the `Sheet`. Direct JS execution (`document.querySelector(...)`) during those windows confirmed the page was fully responsive and the DOM/form state was exactly as expected the whole time — the screenshot pipeline itself was the only thing stalling, not the app. Switching to a fresh tab and reference-based clicks (via `find`/`read_page` refs rather than raw coordinates) avoided it entirely for the rest of the walkthrough. Flagged here so it isn't mistaken for an app bug if seen again.

## Follow-ups (not part of this phase, flagged for later)

- **"Filter by account" only narrows the current page** — `GET /payment-transactions` has no `?payment_account_id=` query param on the backend (confirmed in `phase-6-backend-plan.md`), so an account with transactions spread across many pages won't show a complete filtered history from this screen alone. Add the backend filter later if this proves limiting.
- **No detail view for a single `PaymentTransaction`** — matches `CLAUDE.md`'s page list (no such page planned) and the list's columns already surface everything `PaymentTransactionRead` has.
- **`PaymentForm`'s optional "Party" select has no explicit "clear" affordance** once a party is picked, short of closing and reopening the Sheet — accepted as a minor, non-blocking gap (same posture the spec itself already flagged this with).
