# Phase 7 Frontend — Spec

Governed by `PLAN.md` (what) and `CLAUDE.md` (how the code is shaped) and `.claude/skills/frontend-design-system/SKILL.md` (how it should look). This document plans the frontend build for Phase 7 — `ExpenseCategory`, `Expense`, `RecurringExpenseTemplate` — against the backend already fully implemented and reviewed in `.claude/specs/phase-7-backend.md`. Every citation to `frontend/src` below was verified by reading the actual current code (not the phase-6 spec doc, which has since drifted from it in small ways — noted where relevant), so file:line references reflect what's really on disk today, 2026-08-10.

**Done when** (from `PLAN.md`): a lunch order and this month's rent both land in the same ledger, categorized, from the same screen shape. **Build:** `ExpenseCategory` dynamic CRUD with a daily/monthly flag; an expense-entry screen paid from a `PaymentAccount`; `RecurringExpenseTemplate` for the monthly fixed ones, generating a draft `Expense` each month you confirm rather than silently auto-posting.

---

## 1. Scope

`find frontend/src -iname '*expense*'` returns nothing — this phase's frontend is 100% new work, same starting point Phase 6 had. `CLAUDE.md` §3.3 already names the target files: `components/expenses/ExpenseList.jsx` / `RecurringExpenseList.jsx` and `form/ExpenseForm.jsx`, `hooks/expensesHooks/`, `services/expensesService.js`, `validations/expensesSchemas.js`, `pages/ExpensesPage.jsx` — this spec follows that naming exactly, and adds the two `*CrudConfig.js` files and one container CLAUDE.md's tree doesn't spell out (the same way `ExchangeRateCrudConfig.js`/`PaymentMethodCrudConfig.js`/`CargoModeCrudConfig.js` all exist today without being named in CLAUDE.md's illustrative tree — an established, not a new, omission).

`ExpensesPage` gets **one page**, same shape Phase 6 settled on for Payments (`phase-6-frontend.md` §1: "Payments gets one page... `Sheet` action, not a routed screen") — `RecurringExpenseTemplate` and `Expense` are both hosted on it; `ExpenseCategory` goes to the **Settings** tabs instead (§6.1), mirroring exactly how `PaymentMethod` (the lookup `PaymentAccount` is built on) lives in Settings while `PaymentAccount`/`PaymentTransaction` themselves got their own page.

### 1.1 Confirmed API surface (from `phase-7-backend.md`, cross-checked against the backend's actual schemas)

| Method | Path | Request | Response |
|---|---|---|---|
| GET | `/expenses/expense-categories` | pagination | `{items: ExpenseCategoryRead[], total, page, page_size}` |
| POST | `/expenses/expense-categories` | `ExpenseCategoryCreate` | `ExpenseCategoryRead` (201) |
| PUT | `/expenses/expense-categories/{id}` | `ExpenseCategoryUpdate` | `ExpenseCategoryRead` |
| DELETE | `/expenses/expense-categories/{id}` | — | 204 (soft delete) |
| GET | `/expenses/recurring-expense-templates` | pagination | `{items: RecurringExpenseTemplateRead[], total, page, page_size}` |
| POST | `/expenses/recurring-expense-templates` | `RecurringExpenseTemplateCreate` | `RecurringExpenseTemplateRead` (201) |
| PUT | `/expenses/recurring-expense-templates/{id}` | `RecurringExpenseTemplateUpdate` | `RecurringExpenseTemplateRead` |
| DELETE | `/expenses/recurring-expense-templates/{id}` | — | 204 (soft delete) |
| POST | `/expenses/recurring-expense-templates/{id}/generate` | — (optional `?period=YYYY-MM-DD`, unused by this phase's UI, §9) | `ExpenseRead` (201), `status: "draft"` |
| GET | `/expenses/entries` | pagination + **real server-side** `category_id`/`payment_account_id`/`status` filters | `{items: ExpenseRead[], total, page, page_size}`, ordered `expense_date desc, id desc` |
| POST | `/expenses/entries` | `ExpenseCreate` | `ExpenseRead` (201), `status: "confirmed"` |
| POST | `/expenses/entries/{id}/confirm` | — | `ExpenseRead`, 409 if not `"draft"` |
| DELETE | `/expenses/entries/{id}` | — | 204 (hard delete), 409 if not `"draft"` |

No `GET /expenses/entries/{id}` consumed (no detail page needed — the list already surfaces every `ExpenseRead` field, same posture Phase 6 took for `PaymentTransaction`). **No `ExpenseUpdate` schema exists at all** — `Expense` has no edit route, matching `PaymentTransaction`'s immutable-once-created posture (`phase-7-backend.md` §2.4).

**Schema fields** (from `backend/src/expenses/schemas.py`, per `phase-7-backend.md` §4.1):
- `ExpenseCategoryCreate`: `name: str(max 120)`, `frequency: "daily"|"monthly"`. `ExpenseCategoryRead` adds `id`, `is_active`. `ExpenseCategoryUpdate`: both optional.
- `RecurringExpenseTemplateCreate`: `name: str(max 120)`, `category_id: int`, `payment_account_id: int`, `amount: Decimal(gt 0)`, `day_of_month: int(1–28) | None`, `description: str(max 255) | None`. `RecurringExpenseTemplateRead` adds `id`, `is_active`. `RecurringExpenseTemplateUpdate`: every field optional — a genuine `.partial()` of create, unlike `PaymentAccountUpdate`'s narrower deviation (`phase-6-frontend.md` §5.4).
- `ExpenseCreate`: `category_id: int`, `payment_account_id: int`, `amount: Decimal(gt 0)`, `expense_date: date`, `description: str(max 255) | None`.
- `ExpenseRead`: `id`, `category_id`, `payment_account_id`, `amount`, `expense_date`, `description`, `status: "draft"|"confirmed"`, `recurring_template_id: int | None`, `created_at`. No `is_active`.

`day_of_month` is advisory display-only data — nothing server-side uses it to auto-trigger generation (`phase-7-backend.md` §3.1, §9); the frontend must not treat it as anything more than a hint either (§6.2).

---

## 2. Decisions

1. **`ExpenseCategory` → a 5th Settings tab; `Expense`/`RecurringExpenseTemplate` → their own `/expenses` page.** Direct precedent: `PaymentMethod` (Settings tab) vs. `PaymentAccount`/`PaymentTransaction` (own `PaymentsPage`) — `ExpenseCategory` is structurally the same kind of pure two-field lookup `PaymentMethod` is, consumed by other domain entities but owning none of the transactional logic itself.

2. **`CrudTable` cannot be reused for `RecurringExpenseTemplate` or `Expense` — confirmed by reading `components/common/CrudTable.jsx` in full.** Its row actions are hardcoded to exactly Edit + Delete (`CrudTable.jsx:97-116`); there is no `rowActions` prop, no `actions`-typed column, no children slot — nothing pluggable. Both entities need a third action `CrudTable` has no room for (`RecurringExpenseTemplate` needs "Generate this month"; `Expense` needs "Confirm"/"Discard", and has no Edit at all). This mirrors the exact shape of decision the backend spec already made for the same reason (`phase-7-backend.md` §2.3: a hand-written action bolted on beside — not instead of — the generic CRUD) and the existing frontend precedent for it:
   - `RecurringExpenseTemplate`'s base CRUD (create/edit/delete) has no side effects (`phase-7-backend.md` §2.3) — same as `PaymentAccount`'s CRUD is side-effect-free apart from `opening_balance`, so `components/expenses/RecurringExpenseList.jsx` **hand-rolls the `Card`/`Table`/`PaginationControls` shell `CrudTable` would otherwise provide, but reuses `CrudDrawer` and `ConfirmDeleteDialog` directly** (both are already decoupled, config-driven components — confirmed by reading `CrudDrawer.jsx` in full, it takes `{config, open, mode, row, onOpenChange, entityLabel}` and knows nothing about `CrudTable`) — so only the shell (~row rendering, pagination, the two dialogs' open state) is duplicated, not the create/edit form logic. This is the same "hand-roll around a real side effect" shape `PurchaseOrderDetail.jsx` already uses for its per-line "Receive" button (§2.4 below) — not a new pattern, applied to CRUD-plus-an-action instead of read-only-plus-an-action.
   - `Expense` has no update at all and only a conditional delete (§2.5 below) — `components/expenses/ExpenseList.jsx` is fully hand-rolled, closer to `PaymentTransactionList.jsx`'s shape (a raw `Table`, no `CrudDrawer` involved) than to `CrudTable`.
   
   Flagged explicitly, matching prior specs' honesty about non-precedented shapes: if a *third* domain ever needs "generic CRUD + one extra row action," it's worth adding a `config.rowActions` render-prop to `CrudTable` itself at that point rather than hand-rolling a third time — not done here because two isn't yet a pattern worth generalizing, and touching a shared, cross-domain component for one domain's need isn't this phase's call to make unilaterally.

3. **File-extension convention for `*CrudConfig` files: always `.js`, regardless of whether the config's `options` get injected later.** The existing codebase has a real, minor inconsistency here — `PaymentMethodCrudConfig.js`/`CargoModeCrudConfig.js`/`CargoCostBasisCrudConfig.js`/`ExchangeRateCrudConfig.js` are `.js`, but `PaymentAccountCrudConfig.jsx` is `.jsx` despite its content also being a plain object literal with no JSX in it. This phase doesn't repeat that inconsistency: `ExpenseCategoryCrudConfig.js` and `RecurringExpenseTemplateCrudConfig.js` are both `.js`, since neither file contains JSX — the fact that the latter's `category_id`/`payment_account_id` fields get their `options` filled in later by `RecurringExpenseList.jsx` (§2.2 above, §6.2 below) doesn't change what's actually written in the config file itself.

4. **`Expense`'s "Confirm" and "Discard" actions each get their own `ConfirmDialog`, not `ConfirmDeleteDialog`.** `ConfirmDeleteDialog`'s description is hardcoded — `"This soft-deletes the record — it disappears from the list but isn't permanently removed"` (`components/common/ConfirmDeleteDialog.jsx:11`) — which is **factually wrong** for discarding a draft `Expense`: `DELETE /expenses/entries/{id}` is a real hard delete, not a soft delete (`phase-7-backend.md` §2.4, no `is_active` column on `Expense` at all). Reusing `ConfirmDeleteDialog` here would ship a misleading confirmation. Both actions instead call the lower-level, fully generic `ConfirmDialog` (`components/common/ConfirmDialog.jsx` — `{open, onOpenChange, onConfirm, isPending, title, description, confirmLabel, pendingLabel, confirmVariant}`, no built-in copy) directly, with copy that says what actually happens (§6.3). `RecurringExpenseTemplate`'s own delete, by contrast, **is** a real soft delete (generic CRUD factory, `is_active` column) — its delete keeps using `ConfirmDeleteDialog` unchanged, same as every other lookup entity.

5. **`"expense"` is added to `PAYMENT_REFERENCE_TYPE` (the plain value map) but deliberately withheld from `PAYMENT_REFERENCE_TYPE_OPTIONS` (the selectable dropdown list).** `utils/constants.js:59-63`'s existing comment says to "Add it once Phase 7 ships" — read literally, that would put "Expense" into `PaymentForm.jsx`'s "Link to a sales order or purchase order" checkbox as a third pickable document type. This spec does **not** do that, and the reasoning is worth stating plainly: `Expense.create`/`.confirm` **already** create their own `PaymentTransaction` server-side, synchronously, with `reference_type="expense"` set for them (`phase-7-backend.md` §2.1, §5.2 `_post_expense_payment`) — a user manually picking "Expense" from `PaymentForm`'s dropdown and linking a *second*, independently-created `PaymentTransaction` to that same expense would double-post money that already moved once through the expense's own confirm/create flow. There's no legitimate manual-entry use case for it the way there is for linking a payment to an existing sales/purchase order (which don't auto-create their own `PaymentTransaction`). The value is still added to the plain map, purely so `PaymentTransactionList.jsx`'s reference-column display has a name to look up for the transactions that *do* arrive with `reference_type="expense"` (§4 below) — a read/display need, not a write/selection one.

6. **`RecurringExpenseList`'s category picker is narrowed to `frequency === "monthly"` categories, client-side, as a UX nicety — not a validation rule.** A recurring template conceptually only makes sense against a monthly-cadence category (daily categories are for one-off manual entries). The backend deliberately leaves this unenforced (`phase-7-backend.md` §9: "`RecurringExpenseTemplate.category_id` is not validated against `ExpenseCategory.frequency == "monthly"`... revisit only if this proves confusing in practice"). The frontend follows that same restraint — it *guides* by filtering the dropdown's options, but adds no Yup `.test()` and no backend-side check, so nothing breaks if a future path (e.g. a raw API call) creates a template against a daily category anyway.

7. **The `Expense`-creation form (`ExpenseForm.jsx`) always posts immediately — there is no "save as draft" option in it.** This isn't an oversight; it mirrors the backend precisely (`phase-7-backend.md` §2.2): manual entry (`create_expense`) always inserts `status="confirmed"` and posts a `PaymentTransaction` in the same call — `"draft"` is a state **only** `generate_expense_from_template` can produce. Giving the manual form a status toggle would imply a backend capability that doesn't exist.

8. **`Expense`/`RecurringExpenseTemplate` list filters use real server-side query params, unlike `PaymentTransactionList`'s client-side-only account filter.** `GET /expenses/entries` genuinely supports `?category_id=`/`?payment_account_id=`/`?status=` (`phase-7-backend.md` §5.6/§6) — Phase 6's equivalent (`GET /payment-transactions`) has no such filter, forcing `PaymentTransactionList.jsx` into a page-local, not-the-full-history workaround (`phase-6-frontend.md` §2 decision 7, still true today, confirmed in the live file at `PaymentTransactionList.jsx:35-41`). `ExpenseList.jsx`'s filters are the real thing — selecting a category actually re-queries the backend and narrows the entire history, not just the fetched page.

9. Every new screen still follows `.claude/skills/frontend-design-system/SKILL.md`'s checklist: page header in the container (no card wrapper), `Card`s with the `size-9 rounded-lg bg-primary/10 text-primary` icon badge, hand-rolled loading/error/empty states matching `CrudTable`'s own three-state shape verbatim wherever a list isn't `CrudTable`-based, icon-only ghost row actions with `aria-label`s, mobile-first classes, `overflow-x-auto` on every table.

---

## 3. Shared utility changes

### 3.1 `utils/queryKeys.js` additions

```js
export const expenseCategoryKeys = {
  all: ['expenseCategories'],
  lists: () => [...expenseCategoryKeys.all, 'list'],
  list: (params) => [...expenseCategoryKeys.lists(), params],
};

export const recurringExpenseTemplateKeys = {
  all: ['recurringExpenseTemplates'],
  lists: () => [...recurringExpenseTemplateKeys.all, 'list'],
  list: (params) => [...recurringExpenseTemplateKeys.lists(), params],
};

export const expenseKeys = {
  all: ['expenses'],
  lists: () => [...expenseKeys.all, 'list'],
  list: (params) => [...expenseKeys.lists(), params],
};
```
No `detail(id)` on any of the three — none gets its own detail route (§1).

### 3.2 `utils/constants.js` additions

```js
export const EXPENSE_CATEGORY_FREQUENCY = {
  DAILY: 'daily',
  MONTHLY: 'monthly',
};

export const EXPENSE_CATEGORY_FREQUENCY_OPTIONS = [
  { value: EXPENSE_CATEGORY_FREQUENCY.DAILY, label: 'Daily' },
  { value: EXPENSE_CATEGORY_FREQUENCY.MONTHLY, label: 'Monthly' },
];

export const EXPENSE_STATUS = {
  DRAFT: 'draft',
  CONFIRMED: 'confirmed',
};

export const EXPENSE_STATUS_OPTIONS = [
  { value: EXPENSE_STATUS.DRAFT, label: 'Draft' },
  { value: EXPENSE_STATUS.CONFIRMED, label: 'Confirmed' },
];
```

### 3.3 `utils/constants.js` — `PAYMENT_REFERENCE_TYPE` change (§2 decision 5)

Replace the existing block (`utils/constants.js:59-72`):
```js
// "expense" now exists as a real backend value (Expense/RecurringExpenseTemplate,
// Phase 7) but is deliberately NOT in PAYMENT_REFERENCE_TYPE_OPTIONS below —
// Expense.create/.confirm always create their own PaymentTransaction server-side
// (phase-7-backend.md §2.1), so letting a user manually pick "Expense" from
// PaymentForm.jsx's reference-type dropdown would let them link a second,
// duplicate payment to money that already moved once. See
// phase-7-frontend.md §2 decision 5. It's still added to this plain map so
// PaymentTransactionList.jsx's reference-column label lookup (§4 below) has a
// name for transactions that DO arrive with this reference_type — read-only,
// display-only use.
export const PAYMENT_REFERENCE_TYPE = {
  SALES_ORDER: 'sales_order',
  PURCHASE_ORDER: 'purchase_order',
  EXPENSE: 'expense',
};

export const PAYMENT_REFERENCE_TYPE_OPTIONS = [
  { value: PAYMENT_REFERENCE_TYPE.SALES_ORDER, label: 'Sales order' },
  { value: PAYMENT_REFERENCE_TYPE.PURCHASE_ORDER, label: 'Purchase order' },
];

export const PAYMENT_REFERENCE_TYPE_LABEL = {
  [PAYMENT_REFERENCE_TYPE.SALES_ORDER]: 'SO',
  [PAYMENT_REFERENCE_TYPE.PURCHASE_ORDER]: 'PO',
  [PAYMENT_REFERENCE_TYPE.EXPENSE]: 'Expense',
};
```
`PaymentForm.jsx` itself needs **no changes** — its `referenceOptions`/`PAYMENT_REFERENCE_TYPE_OPTIONS`-driven checkbox already only ever offers `SALES_ORDER`/`PURCHASE_ORDER` (§2 decision 5), so nothing there references the new `EXPENSE` value.

---

## 4. Cross-domain fix: `PaymentTransactionList.jsx`'s reference-column label

Confirmed by reading the live file: `PaymentTransactionList.jsx:118-122` renders
```jsx
<TableCell>
  {txn.reference_type
    ? `${txn.reference_type === 'sales_order' ? 'SO' : 'PO'} #${txn.reference_id}`
    : '—'}
</TableCell>
```
This two-way ternary silently mislabels anything that isn't `"sales_order"` as `"PO"`. It's harmless today because `"expense"` never appears in real data before this phase — but the moment `Expense.create`/`.confirm` starts posting `PaymentTransaction` rows with `reference_type="expense"` (§2 decision 5), every one of them would render as `"PO #<id>"` in this list, which is simply wrong. This phase must fix it as part of shipping, even though the file itself belongs to the `payments/` domain, not `expenses/`:
```jsx
<TableCell>
  {txn.reference_type
    ? `${PAYMENT_REFERENCE_TYPE_LABEL[txn.reference_type] ?? txn.reference_type} #${txn.reference_id}`
    : '—'}
</TableCell>
```
Add `PAYMENT_REFERENCE_TYPE_LABEL` to the existing `import { PAYMENT_DIRECTION } from '@/utils/constants';` line (`PaymentTransactionList.jsx:11`). The `?? txn.reference_type` fallback means a future fourth reference type added without updating this map degrades to showing the raw value instead of a wrong label — never silently mislabeling again.

---

## 5. Expenses domain — data access

### 5.1 `services/expensesService.js` (new)

```js
import { fetchClient } from '@/middleware/fetchClient';
import { buildQueryString } from '@/utils/queryParams';

export async function listExpenseCategories(params) {
  const { data } = await fetchClient.get(`/expenses/expense-categories${buildQueryString(params)}`);
  return data;
}

export async function createExpenseCategory(payload) {
  const { data } = await fetchClient.post('/expenses/expense-categories', payload);
  return data;
}

export async function updateExpenseCategory({ id, ...payload }) {
  const { data } = await fetchClient.put(`/expenses/expense-categories/${id}`, payload);
  return data;
}

export async function deleteExpenseCategory(id) {
  await fetchClient.delete(`/expenses/expense-categories/${id}`);
}

export async function listRecurringExpenseTemplates(params) {
  const { data } = await fetchClient.get(`/expenses/recurring-expense-templates${buildQueryString(params)}`);
  return data;
}

export async function createRecurringExpenseTemplate(payload) {
  const { data } = await fetchClient.post('/expenses/recurring-expense-templates', payload);
  return data;
}

export async function updateRecurringExpenseTemplate({ id, ...payload }) {
  const { data } = await fetchClient.put(`/expenses/recurring-expense-templates/${id}`, payload);
  return data;
}

export async function deleteRecurringExpenseTemplate(id) {
  await fetchClient.delete(`/expenses/recurring-expense-templates/${id}`);
}

// No ?period= passed — the backend defaults to the current month (§9, no
// back-dated-generation UI in this phase).
export async function generateExpenseFromTemplate(templateId) {
  const { data } = await fetchClient.post(`/expenses/recurring-expense-templates/${templateId}/generate`);
  return data; // ExpenseRead, the new draft
}

export async function listExpenses(params) {
  const { data } = await fetchClient.get(`/expenses/entries${buildQueryString(params)}`);
  return data;
}

export async function createExpense(payload) {
  const { data } = await fetchClient.post('/expenses/entries', payload);
  return data;
}

export async function confirmExpense(id) {
  const { data } = await fetchClient.post(`/expenses/entries/${id}/confirm`);
  return data;
}

export async function discardExpense(id) {
  await fetchClient.delete(`/expenses/entries/${id}`);
}
```

### 5.2 `hooks/expensesHooks/expensesQueries.js` (new)

```js
import { useQuery } from '@tanstack/react-query';
import { expenseCategoryKeys, recurringExpenseTemplateKeys, expenseKeys } from '@/utils/queryKeys';
import {
  listExpenseCategories,
  listRecurringExpenseTemplates,
  listExpenses,
} from '@/services/expensesService';

export function useExpenseCategories(params) {
  return useQuery({
    queryKey: expenseCategoryKeys.list(params),
    queryFn: () => listExpenseCategories(params),
  });
}

export function useRecurringExpenseTemplates(params) {
  return useQuery({
    queryKey: recurringExpenseTemplateKeys.list(params),
    queryFn: () => listRecurringExpenseTemplates(params),
  });
}

export function useExpenses(params) {
  return useQuery({
    queryKey: expenseKeys.list(params),
    queryFn: () => listExpenses(params),
  });
}

// Same derived-Set-over-a-fetched-page shape as useReceivedLineIds
// (hooks/inventoryHooks/inventoryQueries.js:29-33) — there's no backend
// "has this template already been generated this month" flag, so it's
// computed client-side from a LOOKUP_PAGE-sized fetch of entries. Inherits
// that hook's own known limitation: a template whose matching expense falls
// outside the first 100 entries (page_size=100) won't be detected as
// already-generated. Acceptable for a single-user system generating at most
// a handful of entries a day (same trade-off already accepted throughout
// this codebase's other LOOKUP_PAGE uses).
export function useTemplateIdsGeneratedThisMonth() {
  const monthStart = `${new Date().toISOString().slice(0, 7)}-01`;
  const query = useExpenses({ page: 1, page_size: 100 });
  const ids = new Set(
    (query.data?.items ?? [])
      .filter((expense) => expense.recurring_template_id != null && expense.expense_date === monthStart)
      .map((expense) => expense.recurring_template_id),
  );
  return { ...query, ids };
}
```

### 5.3 `hooks/expensesHooks/expensesMutations.js` (new)

```js
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { expenseCategoryKeys, recurringExpenseTemplateKeys, expenseKeys, paymentAccountKeys } from '@/utils/queryKeys';
import * as expensesService from '@/services/expensesService';

export function useCreateExpenseCategory() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: expensesService.createExpenseCategory,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: expenseCategoryKeys.lists() }),
  });
}

export function useUpdateExpenseCategory() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: expensesService.updateExpenseCategory,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: expenseCategoryKeys.lists() }),
  });
}

export function useDeleteExpenseCategory() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: expensesService.deleteExpenseCategory,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: expenseCategoryKeys.lists() }),
  });
}

export function useCreateRecurringExpenseTemplate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: expensesService.createRecurringExpenseTemplate,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: recurringExpenseTemplateKeys.lists() }),
  });
}

export function useUpdateRecurringExpenseTemplate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: expensesService.updateRecurringExpenseTemplate,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: recurringExpenseTemplateKeys.lists() }),
  });
}

export function useDeleteRecurringExpenseTemplate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: expensesService.deleteRecurringExpenseTemplate,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: recurringExpenseTemplateKeys.lists() }),
  });
}

// Generating a draft touches no money — only expenseKeys needs invalidating
// (ExpenseList and the "Generated this month" badge both re-read from it).
// No paymentAccountKeys.balances() invalidation here, unlike confirm/create
// below — nothing has posted yet (phase-7-backend.md §2.2).
export function useGenerateExpenseFromTemplate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: expensesService.generateExpenseFromTemplate,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: expenseKeys.lists() }),
  });
}

// Posts immediately (status="confirmed") — invalidates account balances too,
// the same paired invalidation useCreatePaymentTransaction/
// useCreatePaymentAccount already use (hooks/paymentsHooks/paymentsMutations.js).
export function useCreateExpense() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: expensesService.createExpense,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: expenseKeys.lists() });
      queryClient.invalidateQueries({ queryKey: paymentAccountKeys.balances() });
    },
  });
}

// Confirming a draft is the other moment money actually moves — same paired
// invalidation as create, above.
export function useConfirmExpense() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: expensesService.confirmExpense,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: expenseKeys.lists() });
      queryClient.invalidateQueries({ queryKey: paymentAccountKeys.balances() });
    },
  });
}

// Discarding a still-draft expense never touched an account balance
// (phase-7-backend.md §2.4/§5.5) — only expenseKeys needs invalidating.
export function useDiscardExpense() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: expensesService.discardExpense,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: expenseKeys.lists() }),
  });
}
```
No `partyKeys` invalidation anywhere in this file — `Expense` has no party link at all (`phase-7-backend.md` §2.5, scoped out on the backend, nothing to invalidate here as a result).

### 5.4 `validations/expensesSchemas.js` (new)

```js
import { object, string, number } from 'yup';
import { EXPENSE_CATEGORY_FREQUENCY } from '@/utils/constants';

export const expenseCategoryCreateSchema = object({
  name: string().required('Name is required').max(120),
  frequency: string().oneOf(Object.values(EXPENSE_CATEGORY_FREQUENCY)).required('Select a frequency'),
});

// ExpenseCategoryUpdate mirrors ExpenseCategoryCreate with every field optional —
// plain .partial() is correct here (same reasoning as paymentMethodUpdateSchema).
export const expenseCategoryUpdateSchema = expenseCategoryCreateSchema.partial();

export const recurringExpenseTemplateCreateSchema = object({
  name: string().required('Name is required').max(120),
  category_id: number().typeError('Select a category').required('Select a category'),
  payment_account_id: number().typeError('Select an account').required('Select an account'),
  amount: number().typeError('Amount must be a number').positive('Amount must be positive').required('Amount is required'),
  // Optional numeric field: the transform casts an untouched '' to null rather
  // than NaN before typeError runs — the same pattern paymentsSchemas.js's
  // party_id/reference_id already use.
  day_of_month: number()
    .transform((value, originalValue) => (originalValue === '' ? null : value))
    .typeError('Day of month must be a number')
    .min(1, 'Day of month must be between 1 and 28')
    .max(28, 'Day of month must be between 1 and 28')
    .nullable()
    .default(null),
  description: string().max(255).nullable().default(null),
});

// RecurringExpenseTemplateUpdate genuinely accepts every field optional, unlike
// PaymentAccountUpdate's narrower backend schema — .partial() applies cleanly.
export const recurringExpenseTemplateUpdateSchema = recurringExpenseTemplateCreateSchema.partial();

export const expenseCreateSchema = object({
  category_id: number().typeError('Select a category').required('Select a category'),
  payment_account_id: number().typeError('Select an account').required('Select an account'),
  amount: number().typeError('Amount must be a number').positive('Amount must be positive').required('Amount is required'),
  expense_date: string().required('Date is required'),
  description: string().max(255).nullable().default(null),
});
// No expenseUpdateSchema — Expense has no update endpoint (§1.1, §2 decision 2).
```

---

## 6. Components

### 6.1 `components/expenses/ExpenseCategoryCrudConfig.js` (new)

Fully static — `frequency`'s options are a fixed two-value enum, not a live lookup, so (unlike `RecurringExpenseTemplateCrudConfig` below) nothing needs injecting at render time:
```js
import { useExpenseCategories } from '@/hooks/expensesHooks/expensesQueries';
import {
  useCreateExpenseCategory,
  useUpdateExpenseCategory,
  useDeleteExpenseCategory,
} from '@/hooks/expensesHooks/expensesMutations';
import { expenseCategoryCreateSchema, expenseCategoryUpdateSchema } from '@/validations/expensesSchemas';
import { expenseCategoryKeys } from '@/utils/queryKeys';
import { EXPENSE_CATEGORY_FREQUENCY_OPTIONS } from '@/utils/constants';

function frequencyLabel(value) {
  return EXPENSE_CATEGORY_FREQUENCY_OPTIONS.find((option) => option.value === value)?.label ?? value;
}

export const expenseCategoryCrudConfig = {
  queryKey: expenseCategoryKeys,
  useList: useExpenseCategories,
  useCreate: useCreateExpenseCategory,
  useUpdate: useUpdateExpenseCategory,
  useDelete: useDeleteExpenseCategory,
  columns: [
    { key: 'name', label: 'Name' },
    { key: 'frequency', label: 'Frequency', render: (row) => frequencyLabel(row.frequency) },
  ],
  createSchema: expenseCategoryCreateSchema,
  updateSchema: expenseCategoryUpdateSchema,
  fields: [
    { name: 'name', label: 'Name', component: 'text' },
    { name: 'frequency', label: 'Frequency', component: 'select', options: EXPENSE_CATEGORY_FREQUENCY_OPTIONS },
  ],
};
```
This plugs straight into `CrudTable` inside a Settings tab (§7) — no hand-rolling needed, since plain lookup CRUD with zero side effects is exactly `CrudTable`'s home case.

### 6.2 `components/expenses/RecurringExpenseTemplateCrudConfig.js` (new)

```js
import { useRecurringExpenseTemplates } from '@/hooks/expensesHooks/expensesQueries';
import {
  useCreateRecurringExpenseTemplate,
  useUpdateRecurringExpenseTemplate,
  useDeleteRecurringExpenseTemplate,
} from '@/hooks/expensesHooks/expensesMutations';
import {
  recurringExpenseTemplateCreateSchema,
  recurringExpenseTemplateUpdateSchema,
} from '@/validations/expensesSchemas';
import { recurringExpenseTemplateKeys } from '@/utils/queryKeys';

// category_id/payment_account_id need live ExpenseCategory/PaymentAccount rows
// for both their column display and their drawer <select> options — a plain
// exported object can't call a hook. RecurringExpenseList.jsx (§6.4) injects
// both at render time, the same split PaymentAccountCrudConfig.jsx/
// PaymentAccountList.jsx already established for payment_method_id.
export const recurringExpenseTemplateCrudConfig = {
  queryKey: recurringExpenseTemplateKeys,
  useList: useRecurringExpenseTemplates,
  useCreate: useCreateRecurringExpenseTemplate,
  useUpdate: useUpdateRecurringExpenseTemplate,
  useDelete: useDeleteRecurringExpenseTemplate,
  columns: [
    { key: 'name', label: 'Name' },
    { key: 'category_id', label: 'Category' },
    { key: 'payment_account_id', label: 'Account' },
    { key: 'amount', label: 'Amount' },
    { key: 'day_of_month', label: 'Day of month' },
    { key: 'description', label: 'Description' },
  ],
  createSchema: recurringExpenseTemplateCreateSchema,
  updateSchema: recurringExpenseTemplateUpdateSchema,
  fields: [
    { name: 'name', label: 'Name', component: 'text' },
    { name: 'category_id', label: 'Category', component: 'select', options: [] },
    { name: 'payment_account_id', label: 'Payment account', component: 'select', options: [] },
    { name: 'amount', label: 'Amount', component: 'number', step: '0.01' },
    // Informational only (§1.1, §2 decision 6) — nothing server-side or
    // client-side uses this to auto-trigger generation.
    { name: 'day_of_month', label: 'Day of month (informational only)', component: 'number' },
    { name: 'description', label: 'Description', component: 'text' },
  ],
};
```

### 6.3 `components/expenses/RecurringExpenseList.jsx` (new)

Hand-rolled shell (§2 decision 2) — same Card/Table/PaginationControls/CrudDrawer/ConfirmDeleteDialog composition `CrudTable.jsx` itself uses internally, plus one extra "Generate this month" column:
```jsx
import { useState } from 'react';
import { Plus, Pencil, Trash2, Loader2, Inbox, Repeat, CheckCircle2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table';
import { Card, CardHeader, CardTitle, CardDescription, CardAction, CardContent } from '@/components/ui/card';
import { PaginationControls } from '@/components/common/PaginationControls';
import { ConfirmDeleteDialog } from '@/components/common/ConfirmDeleteDialog';
import { CrudDrawer } from '@/components/common/CrudDrawer';
import { CurrencyAmount } from '@/components/common/CurrencyAmount';
import { recurringExpenseTemplateCrudConfig } from '@/components/expenses/RecurringExpenseTemplateCrudConfig';
import { useExpenseCategories, useTemplateIdsGeneratedThisMonth } from '@/hooks/expensesHooks/expensesQueries';
import { usePaymentAccounts } from '@/hooks/paymentsHooks/paymentsQueries';
import { useGenerateExpenseFromTemplate } from '@/hooks/expensesHooks/expensesMutations';
import { EXPENSE_CATEGORY_FREQUENCY } from '@/utils/constants';

const DEFAULT_PAGE_SIZE = 20;
const LOOKUP_PAGE = { page: 1, page_size: 100 };

export function RecurringExpenseList() {
  const [page, setPage] = useState(1);
  const [drawerState, setDrawerState] = useState(null); // { mode: 'create' | 'edit', row? }
  const [deleteRow, setDeleteRow] = useState(null);

  const { data, isLoading, isError } = recurringExpenseTemplateCrudConfig.useList({ page, page_size: DEFAULT_PAGE_SIZE });
  const deleteMutation = recurringExpenseTemplateCrudConfig.useDelete();
  const generateMutation = useGenerateExpenseFromTemplate();
  const { data: categoriesData } = useExpenseCategories(LOOKUP_PAGE);
  const { data: accountsData } = usePaymentAccounts(LOOKUP_PAGE);
  const { ids: generatedThisMonth } = useTemplateIdsGeneratedThisMonth();

  const categoryNameById = Object.fromEntries((categoriesData?.items ?? []).map((c) => [c.id, c.name]));
  const accountLabelById = Object.fromEntries((accountsData?.items ?? []).map((a) => [a.id, a.label]));
  // Only monthly categories are offered here — a UX nicety, not a backend rule
  // (§2 decision 6).
  const monthlyCategoryOptions = (categoriesData?.items ?? [])
    .filter((c) => c.frequency === EXPENSE_CATEGORY_FREQUENCY.MONTHLY)
    .map((c) => ({ value: String(c.id), label: c.name }));
  const accountOptions = (accountsData?.items ?? []).map((a) => ({ value: String(a.id), label: a.label }));

  const config = {
    ...recurringExpenseTemplateCrudConfig,
    columns: recurringExpenseTemplateCrudConfig.columns.map((column) => {
      if (column.key === 'category_id') {
        return { ...column, render: (row) => categoryNameById[row.category_id] ?? `Category #${row.category_id}` };
      }
      if (column.key === 'payment_account_id') {
        return { ...column, render: (row) => accountLabelById[row.payment_account_id] ?? `Account #${row.payment_account_id}` };
      }
      if (column.key === 'amount') {
        return { ...column, render: (row) => <CurrencyAmount value={row.amount} /> };
      }
      return column;
    }),
    fields: recurringExpenseTemplateCrudConfig.fields.map((field) => {
      if (field.name === 'category_id') return { ...field, options: monthlyCategoryOptions };
      if (field.name === 'payment_account_id') return { ...field, options: accountOptions };
      return field;
    }),
  };

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const columnCount = config.columns.length + 1; // + Actions

  return (
    <Card>
      <CardHeader className="[.border-b]:pb-4 border-b">
        <div className="flex items-center gap-3">
          <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <Repeat className="size-4.5" />
          </span>
          <div>
            <CardTitle className="text-base">Recurring Templates</CardTitle>
            <CardDescription>
              Monthly fixed costs — generate this month's draft, then confirm it once it's actually paid.
            </CardDescription>
          </div>
        </div>
        <CardAction>
          <Button size="sm" onClick={() => setDrawerState({ mode: 'create' })}>
            <Plus />
            Add template
          </Button>
        </CardAction>
      </CardHeader>

      <CardContent className="flex flex-col gap-4">
        <div className="overflow-x-auto rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow className="bg-muted/50">
                {config.columns.map((column) => (
                  <TableHead key={column.key}>{column.label}</TableHead>
                ))}
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading && (
                <TableRow>
                  <TableCell colSpan={columnCount} className="h-32 text-center text-muted-foreground">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <Loader2 className="size-5 animate-spin" />
                      Loading…
                    </div>
                  </TableCell>
                </TableRow>
              )}
              {isError && (
                <TableRow>
                  <TableCell colSpan={columnCount} className="h-32 text-center text-destructive">
                    Failed to load.
                  </TableCell>
                </TableRow>
              )}
              {!isLoading && !isError && items.length === 0 && (
                <TableRow>
                  <TableCell colSpan={columnCount} className="h-32 text-center text-muted-foreground">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <Inbox className="size-6 text-muted-foreground/60" />
                      No recurring templates yet — add the first one above.
                    </div>
                  </TableCell>
                </TableRow>
              )}
              {items.map((row) => (
                <TableRow key={row.id} className="hover:bg-muted/40">
                  {config.columns.map((column) => (
                    <TableCell key={column.key}>{column.render ? column.render(row) : (row[column.key] ?? '—')}</TableCell>
                  ))}
                  <TableCell className="text-right">
                    <div className="flex items-center justify-end gap-1">
                      {generatedThisMonth.has(row.id) ? (
                        <span className="inline-flex items-center gap-1.5 text-sm text-muted-foreground">
                          <CheckCircle2 className="size-4 text-primary" />
                          Generated
                        </span>
                      ) : (
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={generateMutation.isPending}
                          onClick={() => generateMutation.mutate(row.id)}
                        >
                          Generate
                        </Button>
                      )}
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        aria-label="Edit recurring expense template"
                        onClick={() => setDrawerState({ mode: 'edit', row })}
                      >
                        <Pencil />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        aria-label="Delete recurring expense template"
                        onClick={() => setDeleteRow(row)}
                      >
                        <Trash2 className="text-destructive" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>

        <PaginationControls page={page} pageSize={DEFAULT_PAGE_SIZE} total={total} onPageChange={setPage} />
      </CardContent>

      <CrudDrawer
        config={config}
        open={Boolean(drawerState)}
        mode={drawerState?.mode}
        row={drawerState?.row}
        entityLabel="recurring expense template"
        onOpenChange={(nextOpen) => !nextOpen && setDrawerState(null)}
      />

      <ConfirmDeleteDialog
        open={Boolean(deleteRow)}
        onOpenChange={(nextOpen) => !nextOpen && setDeleteRow(null)}
        isPending={deleteMutation.isPending}
        itemLabel="recurring expense template"
        onConfirm={async () => {
          await deleteMutation.mutateAsync(deleteRow.id);
          setDeleteRow(null);
        }}
      />
    </Card>
  );
}
```
`generateMutation.mutate(row.id)` (not `mutateAsync`, no `await`, no try/catch) — matches the fire-and-forget shape a simple in-table action button needs; `fetchClient` already toasts success/failure, and a failure (e.g. 409 "already generated this month" if the derived Set momentarily lagged behind a concurrent generate) needs no special local handling beyond the toast.

### 6.4 `components/expenses/ExpenseList.jsx` (new)

```jsx
import { useState } from 'react';
import { Loader2, Inbox, Receipt } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { PaginationControls } from '@/components/common/PaginationControls';
import { CurrencyAmount } from '@/components/common/CurrencyAmount';
import { ConfirmDialog } from '@/components/common/ConfirmDialog';
import { FormSelect } from '@/components/custom';
import { useExpenses, useExpenseCategories } from '@/hooks/expensesHooks/expensesQueries';
import { usePaymentAccounts } from '@/hooks/paymentsHooks/paymentsQueries';
import { useConfirmExpense, useDiscardExpense } from '@/hooks/expensesHooks/expensesMutations';
import { EXPENSE_STATUS, EXPENSE_STATUS_OPTIONS } from '@/utils/constants';

const DEFAULT_PAGE_SIZE = 20;
const LOOKUP_PAGE = { page: 1, page_size: 100 };
const ALL = 'all';

export function ExpenseList() {
  const [page, setPage] = useState(1);
  const [categoryFilter, setCategoryFilter] = useState(ALL);
  const [accountFilter, setAccountFilter] = useState(ALL);
  const [statusFilter, setStatusFilter] = useState(ALL);
  const [confirmingRow, setConfirmingRow] = useState(null);
  const [discardingRow, setDiscardingRow] = useState(null);

  const { data: categoriesData } = useExpenseCategories(LOOKUP_PAGE);
  const { data: accountsData } = usePaymentAccounts(LOOKUP_PAGE);

  // Real server-side filters (§2 decision 8) — unlike PaymentTransactionList's
  // client-side-only account filter, these narrow the full history.
  const { data, isLoading, isError } = useExpenses({
    page,
    page_size: DEFAULT_PAGE_SIZE,
    ...(categoryFilter !== ALL ? { category_id: categoryFilter } : {}),
    ...(accountFilter !== ALL ? { payment_account_id: accountFilter } : {}),
    ...(statusFilter !== ALL ? { status: statusFilter } : {}),
  });

  const confirmMutation = useConfirmExpense();
  const discardMutation = useDiscardExpense();

  const categoryNameById = Object.fromEntries((categoriesData?.items ?? []).map((c) => [c.id, c.name]));
  const accountLabelById = Object.fromEntries((accountsData?.items ?? []).map((a) => [a.id, a.label]));
  const categoryOptions = [
    { value: ALL, label: 'All categories' },
    ...(categoriesData?.items ?? []).map((c) => ({ value: String(c.id), label: c.name })),
  ];
  const accountOptions = [
    { value: ALL, label: 'All accounts' },
    ...(accountsData?.items ?? []).map((a) => ({ value: String(a.id), label: a.label })),
  ];
  const statusOptions = [{ value: ALL, label: 'All statuses' }, ...EXPENSE_STATUS_OPTIONS];

  const expenses = data?.items ?? [];
  const total = data?.total ?? 0;

  return (
    <Card>
      <CardHeader className="[.border-b]:pb-4 border-b">
        <div className="flex items-center gap-3">
          <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <Receipt className="size-4.5" />
          </span>
          <div>
            <CardTitle className="text-base">Expenses</CardTitle>
            <CardDescription>
              Every expense recorded — drafts wait for confirmation before they touch an account's balance.
            </CardDescription>
          </div>
        </div>
      </CardHeader>

      <CardContent className="flex flex-col gap-4">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <FormSelect name="category_filter" label="Category" options={categoryOptions} value={categoryFilter} onChange={setCategoryFilter} />
          <FormSelect name="account_filter" label="Account" options={accountOptions} value={accountFilter} onChange={setAccountFilter} />
          <FormSelect name="status_filter" label="Status" options={statusOptions} value={statusFilter} onChange={setStatusFilter} />
        </div>

        <div className="overflow-x-auto rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow className="bg-muted/50">
                <TableHead>Date</TableHead>
                <TableHead>Category</TableHead>
                <TableHead>Account</TableHead>
                <TableHead className="text-right">Amount</TableHead>
                <TableHead>Description</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading && (
                <TableRow>
                  <TableCell colSpan={7} className="h-32 text-center text-muted-foreground">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <Loader2 className="size-5 animate-spin" />
                      Loading…
                    </div>
                  </TableCell>
                </TableRow>
              )}
              {isError && (
                <TableRow>
                  <TableCell colSpan={7} className="h-32 text-center text-destructive">
                    Failed to load.
                  </TableCell>
                </TableRow>
              )}
              {!isLoading && !isError && expenses.length === 0 && (
                <TableRow>
                  <TableCell colSpan={7} className="h-32 text-center text-muted-foreground">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <Inbox className="size-6 text-muted-foreground/60" />
                      No expenses yet — add the first one above.
                    </div>
                  </TableCell>
                </TableRow>
              )}
              {expenses.map((expense) => (
                <TableRow key={expense.id} className="hover:bg-muted/40">
                  <TableCell>{expense.expense_date}</TableCell>
                  <TableCell>{categoryNameById[expense.category_id] ?? `Category #${expense.category_id}`}</TableCell>
                  <TableCell>{accountLabelById[expense.payment_account_id] ?? `Account #${expense.payment_account_id}`}</TableCell>
                  <TableCell className="text-right">
                    <CurrencyAmount value={expense.amount} />
                  </TableCell>
                  <TableCell className="max-w-40 truncate" title={expense.description ?? ''}>
                    {expense.description || '—'}
                  </TableCell>
                  <TableCell>
                    <Badge variant={expense.status === EXPENSE_STATUS.DRAFT ? 'outline' : 'secondary'}>
                      {expense.status === EXPENSE_STATUS.DRAFT ? 'Draft' : 'Confirmed'}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right">
                    {expense.status === EXPENSE_STATUS.DRAFT ? (
                      <div className="flex justify-end gap-1">
                        <Button size="sm" onClick={() => setConfirmingRow(expense)}>
                          Confirm
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          aria-label="Discard draft expense"
                          onClick={() => setDiscardingRow(expense)}
                        >
                          <Inbox className="text-destructive" />
                        </Button>
                      </div>
                    ) : (
                      '—'
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>

        <PaginationControls page={page} pageSize={DEFAULT_PAGE_SIZE} total={total} onPageChange={setPage} />
      </CardContent>

      <ConfirmDialog
        open={Boolean(confirmingRow)}
        onOpenChange={(nextOpen) => !nextOpen && setConfirmingRow(null)}
        isPending={confirmMutation.isPending}
        title="Confirm this expense?"
        description="This posts a payment transaction against the account immediately — its balance will drop by the expense amount."
        confirmLabel="Confirm & pay"
        pendingLabel="Confirming…"
        onConfirm={async () => {
          await confirmMutation.mutateAsync(confirmingRow.id);
          setConfirmingRow(null);
        }}
      />

      {/* Not ConfirmDeleteDialog — its hardcoded copy claims a soft delete,
          but a draft expense is genuinely hard-deleted (§2 decision 4). */}
      <ConfirmDialog
        open={Boolean(discardingRow)}
        onOpenChange={(nextOpen) => !nextOpen && setDiscardingRow(null)}
        isPending={discardMutation.isPending}
        title="Discard this draft expense?"
        description="Nothing has posted yet, so this is a permanent delete — there's no ledger entry to undo."
        confirmLabel="Discard"
        pendingLabel="Discarding…"
        confirmVariant="destructive"
        onConfirm={async () => {
          await discardMutation.mutateAsync(discardingRow.id);
          setDiscardingRow(null);
        }}
      />
    </Card>
  );
}
```
`Inbox` doubles as the "discard" icon here (no dedicated "discard/trash for a draft" icon already imported elsewhere in this codebase) — swap for a plain `Trash2` if a reviewer prefers matching `RecurringExpenseList`'s delete icon exactly; either reads fine since the `aria-label` and destructive-red tint carry the meaning either way.

### 6.5 `components/expenses/form/ExpenseForm.jsx` (new)

```jsx
import { useForm, Controller } from 'react-hook-form';
import { yupResolver } from '@hookform/resolvers/yup';
import { Button } from '@/components/ui/button';
import { FormField, FormSelect } from '@/components/custom';
import { expenseCreateSchema } from '@/validations/expensesSchemas';
import { useCreateExpense } from '@/hooks/expensesHooks/expensesMutations';
import { useExpenseCategories } from '@/hooks/expensesHooks/expensesQueries';
import { usePaymentAccounts } from '@/hooks/paymentsHooks/paymentsQueries';

const LOOKUP_PAGE = { page: 1, page_size: 100 };
const todayIso = () => new Date().toISOString().slice(0, 10);

export function ExpenseForm({ onSuccess }) {
  const { data: categoriesData } = useExpenseCategories(LOOKUP_PAGE);
  const { data: accountsData } = usePaymentAccounts(LOOKUP_PAGE);
  const categoryOptions = (categoriesData?.items ?? []).map((c) => ({ value: String(c.id), label: c.name }));
  const accountOptions = (accountsData?.items ?? []).map((a) => ({ value: String(a.id), label: a.label }));

  const {
    control,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm({
    resolver: yupResolver(expenseCreateSchema, {}, { raw: true }),
    defaultValues: { category_id: '', payment_account_id: '', amount: '', expense_date: todayIso(), description: '' },
  });
  const createMutation = useCreateExpense();

  const onSubmit = async (values) => {
    try {
      // Omit an unset optional description entirely rather than sending '' —
      // same shape PaymentForm.onSubmit/PurchaseOrderForm.onSubmit already use.
      const payload = {
        category_id: values.category_id,
        payment_account_id: values.payment_account_id,
        amount: values.amount,
        expense_date: values.expense_date,
        ...(values.description ? { description: values.description } : {}),
      };
      await createMutation.mutateAsync(payload);
      onSuccess?.();
    } catch {
      // fetchClient already toasted the backend's error detail — keep the
      // form open so the user can fix (e.g. an inactive account) and retry.
    }
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4">
      <Controller
        name="category_id"
        control={control}
        render={({ field }) => (
          <FormSelect {...field} label="Category" placeholder="Select a category" options={categoryOptions} error={errors.category_id?.message} />
        )}
      />
      <Controller
        name="payment_account_id"
        control={control}
        render={({ field }) => (
          <FormSelect {...field} label="Paid from" placeholder="Select an account" options={accountOptions} error={errors.payment_account_id?.message} />
        )}
      />
      <Controller
        name="amount"
        control={control}
        render={({ field }) => <FormField {...field} type="number" step="0.01" label="Amount" error={errors.amount?.message} />}
      />
      <Controller
        name="expense_date"
        control={control}
        render={({ field }) => <FormField {...field} type="date" label="Date" error={errors.expense_date?.message} />}
      />
      <Controller
        name="description"
        control={control}
        render={({ field }) => <FormField {...field} label="Description (optional)" error={errors.description?.message} />}
      />
      <Button type="submit" size="lg" disabled={isSubmitting} className="self-end">
        {isSubmitting ? 'Saving…' : 'Record expense'}
      </Button>
    </form>
  );
}
```
Every category is offered here (daily **and** monthly) — unlike `RecurringExpenseList`'s narrowed picker (§2 decision 6), a manual one-off entry is exactly what daily categories are for.

---

## 7. Settings tab wiring

### 7.1 `containers/SettingsContainer.jsx` — new 5th tab

```jsx
import { ArrowLeftRight, Wallet, Truck, Scale, Tags } from 'lucide-react'; // + Tags
import { expenseCategoryCrudConfig } from '@/components/expenses/ExpenseCategoryCrudConfig'; // new import
// ...
<TabsList>
  {/* existing 4 triggers unchanged */}
  <TabsTrigger value="expense-categories">
    <Tags className="size-4" />
    Expense Categories
  </TabsTrigger>
</TabsList>
{/* existing 4 contents unchanged */}
<TabsContent value="expense-categories" className="pt-4">
  <CrudTable
    config={expenseCategoryCrudConfig}
    title="Expense Categories"
    description="Food, repairs, rent, bills, salaries — daily float vs. monthly fixed overhead."
    icon={Tags}
    addLabel="Add category"
    entityLabel="expense category"
  />
</TabsContent>
```
`DEFAULT_TAB` (`SettingsContainer.jsx:10`, currently `'exchange-rates'`) stays unchanged — this phase doesn't change which tab opens by default.

---

## 8. Pages / containers

### 8.1 `containers/ExpensesContainer.jsx` (new)

Same shape `PaymentsContainer.jsx` already uses (no URL params, no Suspense boundary needed — no detail route exists for anything in this domain):
```jsx
import { useState } from 'react';
import { Plus } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from '@/components/ui/sheet';
import { RecurringExpenseList } from '@/components/expenses/RecurringExpenseList';
import { ExpenseList } from '@/components/expenses/ExpenseList';
import { ExpenseForm } from '@/components/expenses/form/ExpenseForm';

export function ExpensesContainer() {
  const [addOpen, setAddOpen] = useState(false);

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6 px-4 py-8 sm:py-10">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">Expenses</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Daily float and fixed overhead, categorized, from one screen — paid from an account the moment it's confirmed.
          </p>
        </div>
        <Button onClick={() => setAddOpen(true)}>
          <Plus />
          Add expense
        </Button>
      </div>

      <RecurringExpenseList />
      <ExpenseList />

      <Sheet open={addOpen} onOpenChange={setAddOpen}>
        <SheetContent className="overflow-y-auto sm:max-w-lg">
          <SheetHeader>
            <SheetTitle>Record expense</SheetTitle>
            <SheetDescription>Posts immediately — the account's balance drops by this amount as soon as you save.</SheetDescription>
          </SheetHeader>
          <div className="px-4">
            <ExpenseForm onSuccess={() => setAddOpen(false)} />
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}
```
`RecurringExpenseList` is placed above `ExpenseList` — same ordering logic Phase 6 used (`PaymentAccountList` above `PaymentTransactionList`: the "setup/config" list above the "transactional history" list).

### 8.2 `pages/ExpensesPage.jsx` (new) — the same two-line shape every existing page file follows

```jsx
import { ExpensesContainer } from '@/containers/ExpensesContainer';

export function ExpensesPage() {
  return <ExpensesContainer />;
}
```

---

## 9. App shell updates

### 9.1 `App.jsx` — new route

```jsx
import { ExpensesPage } from '@/pages/ExpensesPage';
// ...
<Route path="/payments" element={<PaymentsPage />} />
<Route path="/expenses" element={<ExpensesPage />} />
<Route path="/" element={<Navigate to="/purchase-orders" replace />} />
```
Inserted immediately after `/payments` (`App.jsx:54`) and before the `/` redirect (`App.jsx:55`) — no other route changes.

### 9.2 `Navbar.jsx` — `NAV_LINKS`

```js
const NAV_LINKS = [
  { to: '/purchase-orders', label: 'Purchase Orders' },
  { to: '/cargo-shipments', label: 'Cargo Shipments' },
  { to: '/inventory', label: 'Inventory' },
  { to: '/sales-orders', label: 'Sales Orders' },
  { to: '/payments', label: 'Payments' },
  { to: '/expenses', label: 'Expenses' },
  { to: '/parties', label: 'Parties' },
  { to: '/catalog', label: 'Catalog' },
  { to: '/settings', label: 'Settings' },
];
```
Inserted after "Payments" (`Navbar.jsx:15`), same transactional-flow ordering rationale Phase 6 used for its own insertion — no icon, matching every other entry (`Navbar.jsx`'s links carry no icons at all; only `SettingsContainer`'s tabs do).

---

## 10. Out of scope / known limitations

- **No back-dated "generate for a past month" UI.** `POST .../generate` supports an optional `?period=` (`phase-7-backend.md` §6), but `RecurringExpenseList`'s "Generate" button always calls it with no period, taking the backend's own default (today, normalized to the 1st). If a month gets missed, there's currently no way to generate that month's draft after the fact from the UI — only this month's. Revisit with a small date-picker dialog if this proves limiting; the service function (`generateExpenseFromTemplate`) already accepts being extended to take one.
- **"Generated this month" detection can miss a template if entries data grows past the first 100 rows** (`useTemplateIdsGeneratedThisMonth`, §5.2) — the same `LOOKUP_PAGE`-sized-fetch trade-off this codebase already accepts everywhere else it derives a Set client-side (`useReceivedLineIds`). Not expected to matter for a single-user trading system's realistic expense volume.
- **`ExpenseList`'s filters are real backend filters, but there's still no free-text search** over description — matches this codebase's consistent lack of search on any list endpoint (`PaymentTransactionList`, `PurchaseOrderList`, etc. have none either).
- **`"expense"` stays unavailable as a manually-selectable `reference_type` in `PaymentForm.jsx`'s checkbox**, by deliberate design (§2 decision 5) — not a gap to "finish later" the way Phase 6's own doc flagged it, but a considered reversal of that doc's assumption.
- **No `RecurringExpenseTemplate.category_id` ↔ `frequency === "monthly"` enforcement**, anywhere — the dropdown narrows to monthly categories as a nicety (§2 decision 6), but nothing stops a template from referencing a daily category through any other path (matches the backend's own accepted gap, `phase-7-backend.md` §9).

---

## 11. Testing checklist (manual, matches `PLAN.md`'s "done when")

1. Settings → new **Expense Categories** tab: add `Food` (`daily`) and `Rent` (`monthly`). Confirm both appear with the right frequency label, and the other four tabs are unaffected.
2. Open the new **Expenses** nav link → `/expenses`. Add a recurring template: `Shop rent`, category `Rent`, an existing payment account, amount `15000`. Confirm the `Recurring Templates` table shows it with a **Generate** button (not yet "Generated").
3. Click **Generate** on that row — confirm it flips to a "Generated" badge, and a new row appears at the top of the `Expenses` table below with **status = Draft**, `recurring_template_id` implied by matching the template's category/account/amount, and note that `GET /payments/payment-accounts/balances` (visible on `/payments`) has **not** changed yet.
4. Click **Generate** again on the same template/row — confirm it's already showing "Generated" (button is gone) and no duplicate draft appears; if forced via a stale UI state, confirm a 409 toast instead of a silent failure.
5. On the draft row in `Expenses`, click **Confirm** → confirm the dialog's copy ("posts... immediately"), confirm it, and confirm the status flips to **Confirmed** and the linked account's balance (back on `/payments`) drops by the expense's amount.
6. Click **Add expense** (top of `/expenses`), fill in `Food` category, an account, amount `500`, today's date, submit — confirm it appears immediately with **status = Confirmed** (never passes through Draft) and the account balance drops right away.
7. Generate a second draft from the same recurring template next month (or manually adjust and retest once a month rolls over) — or, for now, confirm generating for a *different* template works independently and produces its own draft, unaffected by the first template's already-generated state.
8. On a still-draft row, click the discard action — confirm the dialog's copy says "permanent delete," confirm it, and confirm the row disappears entirely with no change to any account balance.
9. Exercise `ExpenseList`'s three filters (category/account/status) — confirm each one narrows the **full** result set (change page size expectations, i.e. `total` in the pagination footer actually changes), not just the currently-fetched page — this is the concrete difference from `PaymentTransactionList`'s filter (§2 decision 8).
10. Back on `/payments`, confirm a `PaymentTransactionList` row exists for step 5's/6's expense payment(s) and its **Reference** column reads `Expense #<id>`, not `PO #<id>` (§4's fix).
11. Resize to ~375px / ~768px / ~1280px: both new tables scroll horizontally inside their own container; the Settings tab list and the Expenses page's filter grid both stack to one column on mobile; the nav's new "Expenses" link appears inside the collapsed mobile menu.

---

## 12. Implementation checklist

New:
- `frontend/src/services/expensesService.js`
- `frontend/src/hooks/expensesHooks/expensesQueries.js`
- `frontend/src/hooks/expensesHooks/expensesMutations.js`
- `frontend/src/validations/expensesSchemas.js`
- `frontend/src/components/expenses/ExpenseCategoryCrudConfig.js`
- `frontend/src/components/expenses/RecurringExpenseTemplateCrudConfig.js`
- `frontend/src/components/expenses/RecurringExpenseList.jsx`
- `frontend/src/components/expenses/ExpenseList.jsx`
- `frontend/src/components/expenses/form/ExpenseForm.jsx`
- `frontend/src/containers/ExpensesContainer.jsx`
- `frontend/src/pages/ExpensesPage.jsx`

Changed:
- `frontend/src/utils/queryKeys.js` — §3.1 additions
- `frontend/src/utils/constants.js` — §3.2 additions, §3.3 `PAYMENT_REFERENCE_TYPE`/`_OPTIONS`/`_LABEL` change
- `frontend/src/components/payments/PaymentTransactionList.jsx` — §4 reference-label fix (cross-domain, required before shipping this phase)
- `frontend/src/containers/SettingsContainer.jsx` — §7.1, new 5th tab
- `frontend/src/App.jsx` — new `/expenses` route
- `frontend/src/components/Navbar.jsx` — new `NAV_LINKS` entry

Not changed (confirmed, not assumed):
- `backend/` — entire tree, already implemented and reviewed in `phase-7-backend.md`
- `frontend/src/components/payments/PaymentAccountCrudConfig.jsx`, `PaymentAccountList.jsx`, `PaymentMethodCrudConfig.js`, `form/PaymentForm.jsx` (apart from §4's fix to the sibling `PaymentTransactionList.jsx`, no other payments file changes)
- Every other domain's frontend code (catalog, parties, purchasing, cargo, inventory, sales)
