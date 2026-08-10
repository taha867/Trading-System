export const HTTP_STATUS = {
  UNAUTHORIZED: 401,
  CONFLICT: 409,
};

export const TOAST_MESSAGES = {
  GENERIC_ERROR: 'Something went wrong. Please try again.',
  NETWORK_ERROR: 'Network error — check your connection and try again.',
  SESSION_EXPIRED: 'Your session has expired. Please sign in again.',
  NOT_AVAILABLE_YET: 'This isn’t available yet.',
};

export const PARTY_ROLE = {
  CHINA_VENDOR: 'china_vendor',
  CARGO_AGENT: 'cargo_agent',
  CUSTOMER: 'customer',
  LOCAL_VENDOR: 'local_vendor',
};

export const PARTY_ROLE_OPTIONS = [
  { value: PARTY_ROLE.CHINA_VENDOR, label: 'China Vendor' },
  { value: PARTY_ROLE.CARGO_AGENT, label: 'Cargo Agent' },
  { value: PARTY_ROLE.CUSTOMER, label: 'Customer' },
  { value: PARTY_ROLE.LOCAL_VENDOR, label: 'Local Vendor' },
];

export const CARGO_COST_BASIS_CODE = {
  WEIGHT: 'weight',
  CBM: 'cbm',
  PIECE: 'piece',
};

export const CARGO_COST_BASIS_CODE_OPTIONS = [
  { value: CARGO_COST_BASIS_CODE.WEIGHT, label: 'Weight' },
  { value: CARGO_COST_BASIS_CODE.CBM, label: 'CBM' },
  { value: CARGO_COST_BASIS_CODE.PIECE, label: 'Piece' },
];

export const PURCHASE_ORDER_SOURCE = {
  CHINA: 'china',
  LOCAL: 'local',
};

export const PURCHASE_ORDER_SOURCE_OPTIONS = [
  { value: PURCHASE_ORDER_SOURCE.CHINA, label: 'China (RMB)' },
  { value: PURCHASE_ORDER_SOURCE.LOCAL, label: 'Local vendor (PKR)' },
];

export const PAYMENT_DIRECTION = {
  IN: 'in',
  OUT: 'out',
};

export const PAYMENT_DIRECTION_OPTIONS = [
  { value: PAYMENT_DIRECTION.IN, label: 'Money in' },
  { value: PAYMENT_DIRECTION.OUT, label: 'Money out' },
];

// "expense" now exists as a real backend value (Expense/RecurringExpenseTemplate,
// Phase 7) but is deliberately NOT in PAYMENT_REFERENCE_TYPE_OPTIONS below —
// Expense.create/.confirm always create their own PaymentTransaction server-side
// (phase-7-backend.md §2.1), so letting a user manually pick "Expense" from
// PaymentForm.jsx's reference-type dropdown would let them link a second,
// duplicate payment to money that already moved once. See
// phase-7-frontend.md §2 decision 5. It's still added to this plain map so
// PaymentTransactionList.jsx's reference-column label lookup has a name for
// transactions that DO arrive with this reference_type — read-only,
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

export const WINDOW_DAYS_OPTIONS = [
  { value: '7', label: 'Last 7 days' },
  { value: '30', label: 'Last 30 days' },
  { value: '90', label: 'Last 90 days' },
  { value: '180', label: 'Last 180 days' },
];

// Mirrors backend/src/reporting/constants.py's DEFAULT_WINDOW_DAYS exactly —
// keep the two in sync if that value ever changes.
export const DEFAULT_WINDOW_DAYS = 30;
