# Phase 6 Frontend — Spec

Governed by `PLAN.md` (what) and `CLAUDE.md` (how the code is shaped) and `.claude/skills/frontend-design-system/SKILL.md` (how it should look). This document plans the frontend build for Phase 6 — `PaymentAccount` and `PaymentTransaction` — against the backend that's already fully implemented and reviewed in `.claude/specs/phase-6-backend.md` (verified against the running code, no drift). Nothing here overrides `CLAUDE.md`; every new file follows a shipped precedent from Phases 0–5, cited by path.

**Done when** (from `PLAN.md`): receiving a customer's payment or paying a vendor updates that account's balance and the party's credit/debit in the same action. **Build:** `PaymentAccount` CRUD; a record-payment screen with direction (in/out), account, amount, optional link to a party/invoice/PO/expense; an account-balances view.

---

## 1. Scope

`grep -rn "PaymentAccount|PaymentTransaction" frontend/src` returns nothing — this phase's frontend is 100% new work. What already exists and stays untouched: `PaymentMethod`'s CRUD (`components/payments/PaymentMethodCrudConfig.js`, its hooks/service/schema, and its tab in `containers/SettingsContainer.jsx`) — Phase 0 work, unrelated to the two new entities.

`CLAUDE.md` §3.3 already resolves the page shape for this domain: Payments gets **one page** (`PaymentsPage.jsx`), unlike Purchasing/Sales which get List+Create+Detail. This settles "record a payment" as an in-page `Sheet` action, not a routed screen — the same shape `CrudDrawer` already uses for add/edit, just hand-written instead of config-driven (§6.4).

### 1.1 Confirmed API surface (from the running backend code, cross-checked against `phase-6-backend.md`)

| Method | Path | Request | Response |
|---|---|---|---|
| GET | `/payments/payment-accounts` | pagination | `{items: PaymentAccountRead[], total, page, page_size}` |
| POST | `/payments/payment-accounts` | `PaymentAccountCreate` | `PaymentAccountRead` (201) |
| GET | `/payments/payment-accounts/{id}` | — | `PaymentAccountRead` |
| PUT | `/payments/payment-accounts/{id}` | `PaymentAccountUpdate` | `PaymentAccountRead` |
| DELETE | `/payments/payment-accounts/{id}` | — | 204 (soft delete) |
| GET | `/payments/payment-accounts/balances` | — | `PaymentAccountBalanceRead[]` — **a plain list, not the `{items,total,...}` wrapper** every other list endpoint returns; active accounts only |
| GET | `/payments/payment-transactions` | pagination only — **no `payment_account_id`/`party_id` query filter exists** | `{items: PaymentTransactionRead[], total, page, page_size}`, ordered `transaction_date desc, id desc` |
| POST | `/payments/payment-transactions` | `PaymentTransactionCreate` | `PaymentTransactionRead` (201) |
| GET | `/payments/payment-transactions/{id}` | — | `PaymentTransactionRead` |

No PUT/DELETE for `PaymentTransaction` — it's create/list/get only, matching `SalesOrder`/`PurchaseOrder`'s existing immutable-once-created posture.

**Schema fields** (from `backend/src/payments/schemas.py`, verified against the code):
- `PaymentAccountCreate`: `payment_method_id: int`, `label: str(max 120)`, `account_number: str(max 64) | None`, `opening_balance: Decimal = 0`.
- `PaymentAccountRead`: adds `id`, `is_active`; **does not include a `balance` field** — that only exists on `PaymentAccountBalanceRead` from the separate `/balances` endpoint. The frontend must never treat `PaymentAccountRead.opening_balance` as "current balance."
- `PaymentAccountUpdate`: **only** `label`, `account_number` — no `payment_method_id`, no `opening_balance`.
- `PaymentAccountBalanceRead`: `id`, `label`, `payment_method_id`, `balance: Decimal` (already the full ledger-summed figure, opening balance included — never add `opening_balance` to it again).
- `PaymentTransactionCreate`: `payment_account_id: int`, `direction: "in"|"out"`, `amount: Decimal (gt 0)`, `transaction_date: date`, `party_id: int | None`, `reference_type: "sales_order"|"purchase_order"|"expense" | None`, `reference_id: int | None`, `note: str(max 255) | None`. Backend `model_validator` enforces `reference_type`/`reference_id` both-set-or-both-null.
- `PaymentTransactionRead`: adds `id`, `created_at`; no `is_active`.

`"expense"` is a real value in the backend's `PaymentReferenceType` Literal but has no domain yet (Phase 7) — omitted from this phase's selectable UI options (§3.2).

---

## 2. Decisions

1. **New top-level route `/payments`**, nav link added to `Navbar.jsx`'s `NAV_LINKS`. `PaymentMethod` stays exactly where it is (Settings tab) — confirmed unchanged, no code in `SettingsContainer.jsx` or `PaymentMethodCrudConfig.js` touches this phase.

2. **`PaymentAccount` reuses `CrudTable`/`CrudDrawer`** via a new `PaymentAccountCrudConfig.jsx` — the direct precedent is `components/parties/PartyCrudConfig.jsx`: `Party` is also a hand-written (non-generic-factory) backend entity that plugs into the generic frontend engine with zero special-casing, and it already has the exact `opening_balance` treatment (`component: 'number', editableOnUpdate: false`) `PaymentAccount.opening_balance` needs for the identical reason — write-once, already posted its own ledger row (`phase-6-backend.md` §2.2).

3. **`payment_method_id`'s select options are injected by the wrapping list component, not baked into the static config export.** Every existing `*CrudConfig` file's `fields[].options` is either a static constant (`PARTY_ROLE_OPTIONS`) or absent — none needs a *live* lookup table's rows as options. A plain exported config object can't call `usePaymentMethods()` itself (it's not a component), so `PaymentAccountList.jsx` (§6.2) fetches `usePaymentMethods(LOOKUP_PAGE)` and spreads a copy of the config with that field's `options` (and the `payment_method_id` column's `render`) filled in at render time. This is the one new small pattern this phase introduces — flagged explicitly since it's not copied from an existing file verbatim.

4. **Account balance is a joined-in column, not a config field.** `PaymentAccountBalanceRead` comes from a separate endpoint (`GET /payment-accounts/balances`), not a column on `PaymentAccountRead` (§1.1) — so it can't be a plain `columns` entry on the static config either. `PaymentAccountList.jsx` fetches `usePaymentAccountBalances()` alongside the account list and joins by `id` into an appended `balance` column, the same "fetch two lists, merge client-side by id" shape `SalesOrderList.jsx` already uses for customer names (`customerNameById`).

5. **Reference-document picker is a searchable combobox** (per your explicit choice), not a raw numeric-id input and not omitted. New reusable `components/custom/FormCombobox.jsx`, built on shadcn's `Command`+`Popover` primitives — **not yet installed** in this codebase (`ls frontend/src/components/ui` has no `command.jsx`/`popover.jsx`; `package.json` has no `cmdk`). Run `npx shadcn@latest add command popover` from `frontend/` before building this component; it adds those two files plus the `cmdk` dependency. `FormCombobox` is generic (not payments-specific) so any later domain needing a searchable picker over a large lookup can reuse it. It's fed by `useSalesOrders(LOOKUP_PAGE)` or `usePurchaseOrders(LOOKUP_PAGE)` depending on the chosen `reference_type`, filtered client-side as the user types (via `cmdk`'s built-in fuzzy match against each option's label) — matching the "no backend search endpoint, fetch page_size=100" posture `useDraftPurchaseOrders`/`useExchangeRateForDate` already established (`hooks/purchasingHooks/purchasingQueries.js`).

6. **`PaymentForm.jsx` is hand-written**, not a `CrudDrawer` config — same posture as `SalesOrderForm.jsx`/`PurchaseOrderForm.jsx` — because of the conditional reference-type/id pair and the optional party link. It renders inside a `Sheet` opened from a "Record payment" button on `PaymentsPage`, per the design skill's "`Sheet` for add/edit, `Dialog`/`ConfirmDialog` only for confirmations" rule.

7. **`PaymentTransactionList.jsx` is read-only** — no edit/delete actions, matching the backend having none. It gets a **client-side** "Filter by account" select, because `GET /payment-transactions` has no `?payment_account_id=` query param (§1.1) — the filter only narrows the currently-fetched page, not the full history; flagged again in §9 as a known limitation, not silently glossed over.

8. **Form payload omits unset optional fields entirely rather than sending `null`** — the exact pattern `PurchaseOrderForm.onSubmit` already uses (it sends `{item_id, qty, rate_rmb}` *or* `{item_id, qty, rate_pkr}`, never both, never an empty-string placeholder for the unused one). `PaymentForm.onSubmit` builds its payload the same way: `party_id`/`reference_type`+`reference_id`/`note` are spread in only when truthy. This sidesteps the `raw: true` yupResolver behavior (`handleSubmit` receives the form's literal typed values, never Yup's cast/transformed ones — confirmed in `CrudDrawer.jsx`'s own comment) — Yup's `.transform('' → null)` on those fields still matters for *validation* correctness (so `number().typeError` doesn't misfire on an empty optional field), but the actual submitted object is built by hand in the component, not derived from the schema's cast output.

9. Every new screen follows `.claude/skills/frontend-design-system/SKILL.md`'s checklist verbatim: page header (title + description, no card wrapper) in the container; content in `Card`s with the `size-9 rounded-lg bg-primary/10 text-primary` icon badge; `CrudTable`'s three loading/error/empty states reproduced by hand in `PaymentTransactionList` (since it isn't `CrudTable`-based); icon-only ghost row actions with `aria-label`s wherever there are any; mobile-first classes; `overflow-x-auto` on both tables.

---

## 3. Shared utility changes

### 3.1 `utils/queryKeys.js` additions

```js
export const paymentAccountKeys = {
  all: ['paymentAccounts'],
  lists: () => [...paymentAccountKeys.all, 'list'],
  list: (params) => [...paymentAccountKeys.lists(), params],
  balances: () => [...paymentAccountKeys.all, 'balances'],
};

export const paymentTransactionKeys = {
  all: ['paymentTransactions'],
  lists: () => [...paymentTransactionKeys.all, 'list'],
  list: (params) => [...paymentTransactionKeys.lists(), params],
};
```
No `detail(id)` on either — `PaymentAccount` never gets its own detail route (it's a row in a `CrudTable`) and `PaymentTransaction` has no detail page (§2 decision 7).

### 3.2 `utils/constants.js` additions

```js
export const PAYMENT_DIRECTION = {
  IN: 'in',
  OUT: 'out',
};

export const PAYMENT_DIRECTION_OPTIONS = [
  { value: PAYMENT_DIRECTION.IN, label: 'Money in' },
  { value: PAYMENT_DIRECTION.OUT, label: 'Money out' },
];

// "expense" is a real value in the backend's PaymentReferenceType Literal
// (payments/constants.py) but the expenses domain doesn't exist until Phase 7 —
// there's nothing to link against yet, so it's left out of the selectable options
// here. Add it once Phase 7 ships; validations/paymentsSchemas.js's reference_type
// check already needs no change since it validates against the backend's full set.
export const PAYMENT_REFERENCE_TYPE = {
  SALES_ORDER: 'sales_order',
  PURCHASE_ORDER: 'purchase_order',
};

export const PAYMENT_REFERENCE_TYPE_OPTIONS = [
  { value: PAYMENT_REFERENCE_TYPE.SALES_ORDER, label: 'Sales order' },
  { value: PAYMENT_REFERENCE_TYPE.PURCHASE_ORDER, label: 'Purchase order' },
];
```

---

## 4. New shared component — `components/custom/FormCombobox.jsx`

Prerequisite: `npx shadcn@latest add command popover` from `frontend/` (§2 decision 5).

```jsx
import { useState } from 'react';
import { Check, ChevronsUpDown } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Command, CommandInput, CommandList, CommandEmpty, CommandGroup, CommandItem } from '@/components/ui/command';
import { cn } from '@/lib/utils';

export function FormCombobox({
  label,
  error,
  options = [],
  value,
  onChange,
  name,
  placeholder = 'Select…',
  searchPlaceholder = 'Search…',
  emptyLabel = 'No results.',
  disabled,
}) {
  const [open, setOpen] = useState(false);
  const selected = options.find((option) => option.value === value);

  return (
    <div className="flex flex-col gap-1.5">
      {label && <Label htmlFor={name}>{label}</Label>}
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            id={name}
            type="button"
            variant="outline"
            role="combobox"
            aria-expanded={open}
            disabled={disabled}
            className={cn(
              'w-full justify-between font-normal',
              !selected && 'text-muted-foreground',
              error && 'border-destructive',
            )}
          >
            {selected ? selected.label : placeholder}
            <ChevronsUpDown className="opacity-50" />
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-(--radix-popover-trigger-width) p-0" align="start">
          <Command>
            <CommandInput placeholder={searchPlaceholder} />
            <CommandList>
              <CommandEmpty>{emptyLabel}</CommandEmpty>
              <CommandGroup>
                {options.map((option) => (
                  <CommandItem
                    key={option.value}
                    value={option.label}
                    onSelect={() => {
                      onChange(option.value);
                      setOpen(false);
                    }}
                  >
                    <Check className={cn('mr-2', option.value === value ? 'opacity-100' : 'opacity-0')} />
                    {option.label}
                  </CommandItem>
                ))}
              </CommandGroup>
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>
      {error && <p className="text-sm text-destructive">{error}</p>}
    </div>
  );
}
```
`CommandItem`'s `value` prop is set to `option.label` (not `option.value`) deliberately — that's the string `cmdk` fuzzy-matches against as the user types, and matching on the human-readable label (`"#12 — 2026-08-01 — Acme Traders"`) is what makes the search useful; `onSelect` still writes the real `option.value` id into the form.

Add to the barrel export:
```js
// components/custom/index.js
export { FormField } from './FormField';
export { FormSelect } from './FormSelect';
export { FormMultiSelect } from './FormMultiSelect';
export { FormCombobox } from './FormCombobox';
```

---

## 5. Payments domain — data access

### 5.1 `services/paymentsService.js` additions (alongside the unchanged `PaymentMethod` functions)

```js
export async function listPaymentAccounts(params) {
  const { data } = await fetchClient.get(`/payments/payment-accounts${buildQueryString(params)}`);
  return data; // { items, total, page, page_size }
}

export async function createPaymentAccount(payload) {
  const { data } = await fetchClient.post('/payments/payment-accounts', payload);
  return data;
}

export async function updatePaymentAccount({ id, ...payload }) {
  const { data } = await fetchClient.put(`/payments/payment-accounts/${id}`, payload);
  return data;
}

export async function deletePaymentAccount(id) {
  await fetchClient.delete(`/payments/payment-accounts/${id}`);
}

// Returns a plain array, not {items,total,...} — GET /payment-accounts/balances is
// a full active-accounts dump, not paginated (§1.1). Don't wrap or paginate this.
export async function getPaymentAccountBalances() {
  const { data } = await fetchClient.get('/payments/payment-accounts/balances');
  return data;
}

export async function listPaymentTransactions(params) {
  const { data } = await fetchClient.get(`/payments/payment-transactions${buildQueryString(params)}`);
  return data;
}

export async function createPaymentTransaction(payload) {
  const { data } = await fetchClient.post('/payments/payment-transactions', payload);
  return data;
}
```

### 5.2 `hooks/paymentsHooks/paymentsQueries.js` additions

```js
import { paymentAccountKeys, paymentTransactionKeys } from '@/utils/queryKeys';
import {
  listPaymentAccounts,
  getPaymentAccountBalances,
  listPaymentTransactions,
} from '@/services/paymentsService';

export function usePaymentAccounts(params) {
  return useQuery({
    queryKey: paymentAccountKeys.list(params),
    queryFn: () => listPaymentAccounts(params),
  });
}

export function usePaymentAccountBalances() {
  return useQuery({
    queryKey: paymentAccountKeys.balances(),
    queryFn: getPaymentAccountBalances,
  });
}

export function usePaymentTransactions(params) {
  return useQuery({
    queryKey: paymentTransactionKeys.list(params),
    queryFn: () => listPaymentTransactions(params),
  });
}
```
(`usePaymentMethods` stays as-is, alongside these — same file.)

### 5.3 `hooks/paymentsHooks/paymentsMutations.js` additions

```js
import { paymentAccountKeys, paymentTransactionKeys, partyKeys } from '@/utils/queryKeys';

export function useCreatePaymentAccount() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: paymentsService.createPaymentAccount,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: paymentAccountKeys.lists() });
      queryClient.invalidateQueries({ queryKey: paymentAccountKeys.balances() });
    },
  });
}

export function useUpdatePaymentAccount() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: paymentsService.updatePaymentAccount,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: paymentAccountKeys.lists() }),
  });
}

export function useDeletePaymentAccount() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: paymentsService.deletePaymentAccount,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: paymentAccountKeys.lists() });
      queryClient.invalidateQueries({ queryKey: paymentAccountKeys.balances() });
    },
  });
}

export function useCreatePaymentTransaction() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: paymentsService.createPaymentTransaction,
    onSuccess: (transaction, variables) => {
      queryClient.invalidateQueries({ queryKey: paymentTransactionKeys.lists() });
      queryClient.invalidateQueries({ queryKey: paymentAccountKeys.balances() });
      // Only when a party was actually linked — mirrors useCreateSalesOrder's
      // conditional partyKeys.statement invalidation (hooks/salesHooks/salesMutations.js):
      // a payment with no party_id never touches that party's ledger rows.
      if (variables.party_id) {
        queryClient.invalidateQueries({ queryKey: partyKeys.statement(variables.party_id) });
      }
    },
  });
}
```

### 5.4 `validations/paymentsSchemas.js` additions

```js
import { object, string, number } from 'yup';
import { PAYMENT_DIRECTION } from '@/utils/constants';

export const paymentAccountCreateSchema = object({
  payment_method_id: number().typeError('Select a payment method').required('Select a payment method'),
  label: string().required('Label is required').max(120),
  account_number: string().max(64).nullable().default(null),
  opening_balance: number().typeError('Opening balance must be a number').default(0),
});

// PaymentAccountUpdate on the backend only accepts label/account_number — its own
// object rather than a .partial() of the create schema, since payment_method_id and
// opening_balance aren't merely optional on update, the backend rejects them
// outright (phase-6-backend.md §4.1's PaymentAccountUpdate).
export const paymentAccountUpdateSchema = object({
  label: string().required('Label is required').max(120),
  account_number: string().max(64).nullable().default(null),
});

export const paymentTransactionCreateSchema = object({
  payment_account_id: number().typeError('Select an account').required('Select an account'),
  direction: string().oneOf(Object.values(PAYMENT_DIRECTION)).required('Select a direction'),
  amount: number().typeError('Amount must be a number').positive('Amount must be positive').required('Amount is required'),
  transaction_date: string().required('Date is required'),
  // Optional numeric fields: the transform is required so an untouched '' from the
  // form casts to null rather than NaN before typeError runs — the same pattern
  // purchasingSchemas.js's rate_rmb/rate_pkr already use.
  party_id: number()
    .transform((value, originalValue) => (originalValue === '' ? null : value))
    .typeError('Select a party')
    .nullable()
    .default(null),
  reference_type: string()
    .transform((value) => (value === '' ? null : value))
    .nullable()
    .default(null),
  reference_id: number()
    .transform((value, originalValue) => (originalValue === '' ? null : value))
    .typeError('Pick a document')
    .nullable()
    .default(null),
  note: string().max(255).nullable().default(null),
})
  // Mirrors the backend's model_validator verbatim (phase-6-backend.md §4.1's
  // _reference_type_and_id_together) — both set or both null, checked here as a
  // sibling-field .test() the same shape purchasingSchemas.js's rate-matches-source
  // test already uses on its own object schema.
  .test(
    'reference-type-and-id-together',
    'Pick a document to link, or clear both the type and the selection',
    (values) => (values.reference_type == null) === (values.reference_id == null),
  );
```
`PaymentForm.onSubmit` (§6.4) does not rely on this schema's transformed output for the submitted payload (§2 decision 8) — the transforms above exist purely so validation doesn't misfire on an untouched optional field.

---

## 6. Components

### 6.1 `components/payments/PaymentAccountCrudConfig.jsx` (new)

```jsx
import { usePaymentAccounts } from '@/hooks/paymentsHooks/paymentsQueries';
import {
  useCreatePaymentAccount,
  useUpdatePaymentAccount,
  useDeletePaymentAccount,
} from '@/hooks/paymentsHooks/paymentsMutations';
import { paymentAccountCreateSchema, paymentAccountUpdateSchema } from '@/validations/paymentsSchemas';
import { paymentAccountKeys } from '@/utils/queryKeys';

// `payment_method_id`'s options and the same column's display value both need a
// live PaymentMethod lookup, which a plain exported config object can't fetch
// itself — PaymentAccountList (§6.2) injects both at render time before handing
// this config to CrudTable (§2 decision 3). Left empty/undecorated here.
export const paymentAccountCrudConfig = {
  queryKey: paymentAccountKeys,
  useList: usePaymentAccounts,
  useCreate: useCreatePaymentAccount,
  useUpdate: useUpdatePaymentAccount,
  useDelete: useDeletePaymentAccount,
  columns: [
    { key: 'label', label: 'Label' },
    { key: 'payment_method_id', label: 'Method' },
    { key: 'account_number', label: 'Account number' },
  ],
  createSchema: paymentAccountCreateSchema,
  updateSchema: paymentAccountUpdateSchema,
  fields: [
    // Update schema doesn't accept this field at all — disabled in edit mode so
    // RHF drops it from the submitted payload (same reasoning as opening_balance).
    { name: 'payment_method_id', label: 'Payment method', component: 'select', options: [], editableOnUpdate: false },
    { name: 'label', label: 'Label', component: 'text' },
    { name: 'account_number', label: 'Account number', component: 'text' },
    // Write-once on the backend — posts its own ledger row at creation
    // (phase-6-backend.md §2.2) — disabled in edit mode, same as
    // PartyCrudConfig.jsx's opening_balance field.
    {
      name: 'opening_balance',
      label: 'Opening balance',
      component: 'number',
      step: '0.01',
      defaultValue: 0,
      editableOnUpdate: false,
    },
  ],
};
```

### 6.2 `components/payments/PaymentAccountList.jsx` (new)

```jsx
import { Wallet } from 'lucide-react';
import { CrudTable } from '@/components/common/CrudTable';
import { CurrencyAmount } from '@/components/common/CurrencyAmount';
import { paymentAccountCrudConfig } from '@/components/payments/PaymentAccountCrudConfig';
import { usePaymentAccountBalances, usePaymentMethods } from '@/hooks/paymentsHooks/paymentsQueries';

const LOOKUP_PAGE = { page: 1, page_size: 100 };

export function PaymentAccountList() {
  const { data: balancesData } = usePaymentAccountBalances();
  const { data: methodsData } = usePaymentMethods(LOOKUP_PAGE);

  const balanceById = Object.fromEntries((balancesData ?? []).map((b) => [b.id, b.balance]));
  const methodNameById = Object.fromEntries((methodsData?.items ?? []).map((m) => [m.id, m.name]));
  const methodOptions = (methodsData?.items ?? []).map((m) => ({ value: String(m.id), label: m.name }));

  // Balance isn't a column on PaymentAccountRead (§1.1) — joined in here from a
  // second query by id, the same shape SalesOrderList.jsx uses for customer names.
  // payment_method_id's display value and its drawer field options are both
  // injected here too (§2 decision 3) since the static config can't fetch a hook.
  const config = {
    ...paymentAccountCrudConfig,
    columns: [
      ...paymentAccountCrudConfig.columns.map((column) =>
        column.key === 'payment_method_id'
          ? { ...column, render: (row) => methodNameById[row.payment_method_id] ?? `Method #${row.payment_method_id}` }
          : column,
      ),
      {
        key: 'balance',
        label: 'Balance',
        render: (row) => (
          <CurrencyAmount value={balanceById[row.id] ?? row.opening_balance} className="font-medium" />
        ),
      },
    ],
    fields: paymentAccountCrudConfig.fields.map((field) =>
      field.name === 'payment_method_id' ? { ...field, options: methodOptions } : field,
    ),
  };

  return (
    <CrudTable
      config={config}
      title="Payment Accounts"
      description="Concrete accounts under each payment method — balance is the sum of every ledger entry posted against it."
      icon={Wallet}
      addLabel="Add account"
      entityLabel="payment account"
    />
  );
}
```

### 6.3 `components/payments/PaymentTransactionList.jsx` (new)

```jsx
import { useState } from 'react';
import { Loader2, Inbox, History } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { PaginationControls } from '@/components/common/PaginationControls';
import { CurrencyAmount } from '@/components/common/CurrencyAmount';
import { FormSelect } from '@/components/custom';
import { usePaymentTransactions, usePaymentAccounts } from '@/hooks/paymentsHooks/paymentsQueries';
import { useParties } from '@/hooks/partyHooks/partyQueries';
import { PAYMENT_DIRECTION } from '@/utils/constants';

const DEFAULT_PAGE_SIZE = 20;
const LOOKUP_PAGE = { page: 1, page_size: 100 };

export function PaymentTransactionList() {
  const [page, setPage] = useState(1);
  const [accountFilter, setAccountFilter] = useState('');

  const { data, isLoading, isError } = usePaymentTransactions({ page, page_size: DEFAULT_PAGE_SIZE });
  const { data: accountsData } = usePaymentAccounts(LOOKUP_PAGE);
  const { data: partiesData } = useParties(LOOKUP_PAGE);

  const accountLabelById = Object.fromEntries((accountsData?.items ?? []).map((a) => [a.id, a.label]));
  const partyNameById = Object.fromEntries((partiesData?.items ?? []).map((p) => [p.id, p.name]));
  const accountOptions = (accountsData?.items ?? []).map((a) => ({ value: String(a.id), label: a.label }));

  // GET /payment-transactions has no ?payment_account_id= filter (§1.1) — this only
  // narrows the current page, not the full history (§9, known limitation).
  const allTransactions = data?.items ?? [];
  const transactions = accountFilter
    ? allTransactions.filter((t) => String(t.payment_account_id) === accountFilter)
    : allTransactions;
  const total = data?.total ?? 0;

  return (
    <Card>
      <CardHeader className="[.border-b]:pb-4 border-b">
        <div className="flex items-center gap-3">
          <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <History className="size-4.5" />
          </span>
          <div>
            <CardTitle className="text-base">Transactions</CardTitle>
            <CardDescription>Every payment recorded — each one already posted to the ledger, none editable.</CardDescription>
          </div>
        </div>
      </CardHeader>

      <CardContent className="flex flex-col gap-4">
        <div className="max-w-xs">
          <FormSelect
            name="account_filter"
            label="Filter by account"
            placeholder="All accounts"
            options={accountOptions}
            value={accountFilter}
            onChange={setAccountFilter}
          />
        </div>

        <div className="overflow-x-auto rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow className="bg-muted/50">
                <TableHead>Date</TableHead>
                <TableHead>Direction</TableHead>
                <TableHead>Account</TableHead>
                <TableHead>Party</TableHead>
                <TableHead>Reference</TableHead>
                <TableHead className="text-right">Amount</TableHead>
                <TableHead>Note</TableHead>
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
              {!isLoading && !isError && transactions.length === 0 && (
                <TableRow>
                  <TableCell colSpan={7} className="h-32 text-center text-muted-foreground">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <Inbox className="size-6 text-muted-foreground/60" />
                      No transactions yet — record the first payment above.
                    </div>
                  </TableCell>
                </TableRow>
              )}
              {transactions.map((txn) => (
                <TableRow key={txn.id} className="hover:bg-muted/40">
                  <TableCell>{txn.transaction_date}</TableCell>
                  <TableCell>
                    <Badge variant={txn.direction === PAYMENT_DIRECTION.IN ? 'default' : 'secondary'}>
                      {txn.direction === PAYMENT_DIRECTION.IN ? 'In' : 'Out'}
                    </Badge>
                  </TableCell>
                  <TableCell>{accountLabelById[txn.payment_account_id] ?? `Account #${txn.payment_account_id}`}</TableCell>
                  <TableCell>{txn.party_id ? partyNameById[txn.party_id] ?? `Party #${txn.party_id}` : '—'}</TableCell>
                  <TableCell>
                    {txn.reference_type
                      ? `${txn.reference_type === 'sales_order' ? 'SO' : 'PO'} #${txn.reference_id}`
                      : '—'}
                  </TableCell>
                  <TableCell className="text-right">
                    <CurrencyAmount value={txn.amount} />
                  </TableCell>
                  <TableCell className="max-w-40 truncate" title={txn.note ?? ''}>
                    {txn.note || '—'}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>

        <PaginationControls page={page} pageSize={DEFAULT_PAGE_SIZE} total={total} onPageChange={setPage} />
      </CardContent>
    </Card>
  );
}
```

### 6.4 `components/payments/form/PaymentForm.jsx` (new)

```jsx
import { useState } from 'react';
import { useForm, Controller } from 'react-hook-form';
import { yupResolver } from '@hookform/resolvers/yup';
import { Checkbox } from '@/components/ui/checkbox';
import { Button } from '@/components/ui/button';
import { FormField, FormSelect, FormCombobox } from '@/components/custom';
import { paymentTransactionCreateSchema } from '@/validations/paymentsSchemas';
import { useCreatePaymentTransaction } from '@/hooks/paymentsHooks/paymentsMutations';
import { usePaymentAccounts } from '@/hooks/paymentsHooks/paymentsQueries';
import { useParties } from '@/hooks/partyHooks/partyQueries';
import { useSalesOrders } from '@/hooks/salesHooks/salesQueries';
import { usePurchaseOrders } from '@/hooks/purchasingHooks/purchasingQueries';
import {
  PAYMENT_DIRECTION,
  PAYMENT_DIRECTION_OPTIONS,
  PAYMENT_REFERENCE_TYPE,
  PAYMENT_REFERENCE_TYPE_OPTIONS,
} from '@/utils/constants';

const LOOKUP_PAGE = { page: 1, page_size: 100 };
const todayIso = () => new Date().toISOString().slice(0, 10);

export function PaymentForm({ onSuccess }) {
  const [hasReference, setHasReference] = useState(false);

  const { data: accountsData } = usePaymentAccounts(LOOKUP_PAGE);
  const { data: partiesData } = useParties(LOOKUP_PAGE);
  const { data: salesOrdersData } = useSalesOrders(LOOKUP_PAGE);
  const { data: purchaseOrdersData } = usePurchaseOrders(LOOKUP_PAGE);

  const partyNameById = Object.fromEntries((partiesData?.items ?? []).map((p) => [p.id, p.name]));
  const accountOptions = (accountsData?.items ?? []).map((a) => ({ value: String(a.id), label: a.label }));
  const partyOptions = (partiesData?.items ?? []).map((p) => ({ value: String(p.id), label: p.name }));

  const {
    control,
    handleSubmit,
    watch,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm({
    resolver: yupResolver(paymentTransactionCreateSchema, {}, { raw: true }),
    defaultValues: {
      payment_account_id: '',
      direction: PAYMENT_DIRECTION.IN,
      amount: '',
      transaction_date: todayIso(),
      party_id: '',
      reference_type: '',
      reference_id: '',
      note: '',
    },
  });
  const createMutation = useCreatePaymentTransaction();
  const referenceType = watch('reference_type');

  // Same "fetch page_size=100, no backend search" posture as
  // useDraftPurchaseOrders/useExchangeRateForDate — neither list endpoint supports
  // search, and a solo-trading-system's order volume makes one page a fair trade.
  const referenceOptions = (
    referenceType === PAYMENT_REFERENCE_TYPE.SALES_ORDER
      ? (salesOrdersData?.items ?? [])
      : referenceType === PAYMENT_REFERENCE_TYPE.PURCHASE_ORDER
        ? (purchaseOrdersData?.items ?? [])
        : []
  ).map((order) => ({
    value: String(order.id),
    label: `#${order.id} — ${order.order_date} — ${partyNameById[order.party_id] ?? `Party #${order.party_id}`}`,
  }));

  const toggleReference = (checked) => {
    setHasReference(checked);
    if (!checked) {
      setValue('reference_type', '');
      setValue('reference_id', '');
    }
  };

  const onSubmit = async (values) => {
    try {
      // Omit unset optional fields entirely rather than sending null/'' — the
      // same shape PurchaseOrderForm.onSubmit uses for its conditional rate
      // field (§2 decision 8).
      const payload = {
        payment_account_id: values.payment_account_id,
        direction: values.direction,
        amount: values.amount,
        transaction_date: values.transaction_date,
        ...(values.party_id ? { party_id: values.party_id } : {}),
        ...(values.reference_type && values.reference_id
          ? { reference_type: values.reference_type, reference_id: values.reference_id }
          : {}),
        ...(values.note ? { note: values.note } : {}),
      };
      await createMutation.mutateAsync(payload);
      onSuccess?.();
    } catch {
      // fetchClient already toasted the backend's error detail — keep the form
      // open so the user can fix (e.g. an inactive account/party) and retry.
    }
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4">
      <div className="grid gap-4 md:grid-cols-2">
        <Controller
          name="direction"
          control={control}
          render={({ field }) => (
            <FormSelect {...field} label="Direction" options={PAYMENT_DIRECTION_OPTIONS} error={errors.direction?.message} />
          )}
        />
        <Controller
          name="payment_account_id"
          control={control}
          render={({ field }) => (
            <FormSelect
              {...field}
              label="Account"
              placeholder="Select an account"
              options={accountOptions}
              error={errors.payment_account_id?.message}
            />
          )}
        />
        <Controller
          name="amount"
          control={control}
          render={({ field }) => (
            <FormField {...field} type="number" step="0.01" label="Amount" error={errors.amount?.message} />
          )}
        />
        <Controller
          name="transaction_date"
          control={control}
          render={({ field }) => (
            <FormField {...field} type="date" label="Date" error={errors.transaction_date?.message} />
          )}
        />
        <Controller
          name="party_id"
          control={control}
          render={({ field }) => (
            <FormSelect
              {...field}
              label="Party (optional)"
              placeholder="No party linked"
              options={partyOptions}
              error={errors.party_id?.message}
            />
          )}
        />
        <Controller
          name="note"
          control={control}
          render={({ field }) => <FormField {...field} label="Note (optional)" error={errors.note?.message} />}
        />
      </div>

      <div className="flex flex-col gap-3 rounded-lg border p-3">
        <label className="flex items-center gap-2 text-sm font-medium">
          <Checkbox checked={hasReference} onCheckedChange={toggleReference} />
          Link to a sales order or purchase order
        </label>
        {hasReference && (
          <div className="grid gap-3 md:grid-cols-2">
            <Controller
              name="reference_type"
              control={control}
              render={({ field }) => (
                <FormSelect
                  {...field}
                  label="Document type"
                  placeholder="Select a type"
                  options={PAYMENT_REFERENCE_TYPE_OPTIONS}
                  error={errors.reference_type?.message}
                />
              )}
            />
            <Controller
              name="reference_id"
              control={control}
              render={({ field }) => (
                <FormCombobox
                  {...field}
                  label="Document"
                  placeholder={referenceType ? 'Select a document' : 'Pick a type first'}
                  searchPlaceholder="Search by id or party…"
                  options={referenceOptions}
                  disabled={!referenceType}
                  error={errors.reference_id?.message}
                />
              )}
            />
          </div>
        )}
      </div>

      <Button type="submit" size="lg" disabled={isSubmitting} className="self-end">
        {isSubmitting ? 'Recording…' : 'Record payment'}
      </Button>
    </form>
  );
}
```

---

## 7. Pages / containers

### 7.1 `containers/PaymentsContainer.jsx` (new)

```jsx
import { useState } from 'react';
import { Plus } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from '@/components/ui/sheet';
import { PaymentAccountList } from '@/components/payments/PaymentAccountList';
import { PaymentTransactionList } from '@/components/payments/PaymentTransactionList';
import { PaymentForm } from '@/components/payments/form/PaymentForm';

export function PaymentsContainer() {
  const [recordOpen, setRecordOpen] = useState(false);

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6 px-4 py-8 sm:py-10">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">Payments</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Every rupee tied to an account — record a payment and its account and party balance move together.
          </p>
        </div>
        <Button onClick={() => setRecordOpen(true)}>
          <Plus />
          Record payment
        </Button>
      </div>

      <PaymentAccountList />
      <PaymentTransactionList />

      <Sheet open={recordOpen} onOpenChange={setRecordOpen}>
        <SheetContent className="overflow-y-auto sm:max-w-lg">
          <SheetHeader>
            <SheetTitle>Record payment</SheetTitle>
            <SheetDescription>Money in or out, tied to an account and — optionally — a party.</SheetDescription>
          </SheetHeader>
          <div className="px-4">
            <PaymentForm onSuccess={() => setRecordOpen(false)} />
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}
```

### 7.2 `pages/PaymentsPage.jsx` (new) — same two-line shape every existing page file follows

```jsx
import { PaymentsContainer } from '@/containers/PaymentsContainer';

export function PaymentsPage() {
  return <PaymentsContainer />;
}
```

---

## 8. App shell updates

### 8.1 `App.jsx` — new route

```jsx
import { PaymentsPage } from '@/pages/PaymentsPage';
// ...
<Route path="/payments" element={<PaymentsPage />} />
```
Placed inside the existing `ProtectedRoute` group, alongside `/sales-orders/:orderId` and before the `/` redirect — no other route changes.

### 8.2 `Navbar.jsx` — `NAV_LINKS`

```js
const NAV_LINKS = [
  { to: '/purchase-orders', label: 'Purchase Orders' },
  { to: '/cargo-shipments', label: 'Cargo Shipments' },
  { to: '/inventory', label: 'Inventory' },
  { to: '/sales-orders', label: 'Sales Orders' },
  { to: '/payments', label: 'Payments' },
  { to: '/parties', label: 'Parties' },
  { to: '/catalog', label: 'Catalog' },
  { to: '/settings', label: 'Settings' },
];
```
Inserted after "Sales Orders" (transactional flow order) and before "Parties" — no icon, matching every other entry in this array (icons are a `SettingsContainer` tab convention, not a `Navbar` one).

---

## 9. Out of scope / known limitations

- **"Filter by account" on `PaymentTransactionList` only narrows the current page** — the backend has no `?payment_account_id=` query param on `GET /payment-transactions` (§1.1). A account with transactions spread across many pages won't show a complete filtered history from this screen alone. Fix later by adding the backend filter, following `get_party_statement`'s shape, if this proves limiting in practice — same posture prior phases' specs took toward their own acceptable gaps.
- **No detail view for a single `PaymentTransaction`** — `CLAUDE.md`'s page list has none, and the backend's `GET /payment-transactions/{id}` exists but isn't consumed here; the list's columns (date, direction, account, party, reference, amount, note) already surface everything `PaymentTransactionRead` has.
- **`reference_id` isn't validated against the chosen order actually existing beyond appearing in the fetched `LOOKUP_PAGE`** — since the combobox is populated from a real fetched list, a stale/deleted order can't be picked through the UI, but the backend itself still doesn't verify existence at write time (`phase-6-backend.md` §2.6) — unchanged, not something the frontend can add extra safety for.
- **`expense` reference type stays unavailable in the UI** until Phase 7 ships a real `expenses` domain to link against (§3.2).

---

## 10. Testing checklist (manual, matches `PLAN.md`'s "done when")

1. Sign in → Settings → Payment Methods: confirm the four seeded methods (`Bank`, `JazzCash`, `Easypaisa`, `Cash`) are unaffected by this phase.
2. Open the new **Payments** nav link → `/payments`. Add a payment account under `Cash` with `opening_balance = 5000`. Confirm it appears in the Payment Accounts table with **Balance = 5000.00**.
3. Click **Record payment** → direction "Money in", account = the new Cash account, amount `1000`, today's date, party = an existing customer, leave the reference checkbox off. Submit — confirm the Sheet closes and the account's Balance moves to `6000.00`.
4. Open that customer's Party Detail statement — confirm a new row with `credit = 1000` reduced their receivable, posted in the same action.
5. Record a "Money out" payment with **no** party linked (e.g. paying a cash expense informally) — confirm only the account balance moves; no party statement changes.
6. Record another "Money in" payment, check **Link to a sales order or purchase order**, pick "Sales order" as the type, and use the searchable combobox to find a real order by typing part of a customer's name — confirm it filters live and selecting one closes the popover with the order shown in the trigger.
7. Confirm `PaymentTransactionList` shows no edit/delete controls on any row, and the "Filter by account" select narrows the visible rows to the chosen account.
8. Resize to ~375px / ~768px / ~1280px: both tables scroll horizontally inside their own container rather than compressing; the nav collapses below `md`; the record-payment `Sheet`'s two-column grid drops to one column on mobile.

---

## 11. Implementation checklist

New:
- `frontend/src/components/custom/FormCombobox.jsx` (+ `npx shadcn@latest add command popover`)
- `frontend/src/components/payments/PaymentAccountCrudConfig.jsx`
- `frontend/src/components/payments/PaymentAccountList.jsx`
- `frontend/src/components/payments/PaymentTransactionList.jsx`
- `frontend/src/components/payments/form/PaymentForm.jsx`
- `frontend/src/containers/PaymentsContainer.jsx`
- `frontend/src/pages/PaymentsPage.jsx`

Changed:
- `frontend/src/services/paymentsService.js` — §5.1 additions
- `frontend/src/hooks/paymentsHooks/paymentsQueries.js` — §5.2 additions
- `frontend/src/hooks/paymentsHooks/paymentsMutations.js` — §5.3 additions
- `frontend/src/validations/paymentsSchemas.js` — §5.4 additions
- `frontend/src/utils/queryKeys.js` — §3.1 additions
- `frontend/src/utils/constants.js` — §3.2 additions
- `frontend/src/components/custom/index.js` — export `FormCombobox`
- `frontend/src/App.jsx` — new `/payments` route
- `frontend/src/components/Navbar.jsx` — new `NAV_LINKS` entry

Not changed (confirmed, not assumed):
- `backend/` — entire tree, already implemented and reviewed in `phase-6-backend.md`
- `frontend/src/components/payments/PaymentMethodCrudConfig.js`, `frontend/src/containers/SettingsContainer.jsx`
- Every other domain's frontend code (catalog, parties, purchasing, cargo, inventory, sales)
