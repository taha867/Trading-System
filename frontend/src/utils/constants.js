import {
  LayoutDashboard,
  ShoppingCart,
  Truck,
  Boxes,
  Receipt,
  Wallet,
  Banknote,
  Users2,
  Package,
  Settings,
  Grid2x2,
  Share2,
} from 'lucide-react';

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

// Shared by Sidebar.jsx (desktop icon rail) and BottomNav.jsx's mobile "More"
// sheet — one source of truth for the app's primary navigation. shortLabel is
// only used by BottomNav's primary tab row, which is width-constrained.
export const NAV_LINKS = [
  { to: '/dashboard', label: 'Dashboard', shortLabel: 'Home', icon: LayoutDashboard },
  { to: '/purchase-orders', label: 'Purchase Orders', shortLabel: 'Purchases', icon: ShoppingCart },
  { to: '/cargo-shipments', label: 'Cargo Shipments', icon: Truck },
  { to: '/inventory', label: 'Inventory', shortLabel: 'Stock', icon: Boxes },
  { to: '/sales-orders', label: 'Sales Orders', shortLabel: 'Sales', icon: Receipt },
  { to: '/payments', label: 'Payments', icon: Wallet },
  { to: '/expenses', label: 'Expenses', icon: Banknote },
  { to: '/parties', label: 'Parties', icon: Users2 },
  { to: '/catalog', label: 'Catalog', icon: Package },
  { to: '/stock-list', label: 'Stock List', icon: Share2 },
  { to: '/settings', label: 'Settings', icon: Settings },
];

// The four highest-traffic destinations on a phone (CLAUDE.md §3.7 names
// "checking stock" and "confirming a sale" explicitly as the mobile personas)
// get a fixed bottom tab in BottomNav.jsx; everything else lives behind its
// "More" tab.
export const BOTTOM_NAV_PRIMARY_PATHS = ['/dashboard', '/sales-orders', '/inventory', '/purchase-orders'];
export const BOTTOM_NAV_MORE_ICON = Grid2x2;

// Radix Select can't represent "no selection" as an empty-string item value —
// shared sentinel for every "All <something>" filter option in the app
// (StockListShare.jsx's category filter, etc).
export const SELECT_ALL_VALUE = '__all__';

// StockListShare.jsx's export page geometry — wide enough for several
// brand-block "cards" side by side, tall enough that a large multi-brand
// category packs into few pages instead of one page per screenful of rows.
export const STOCK_LIST_PAGE_WIDTH = 1000;
export const STOCK_LIST_PAGE_HEIGHT = 1500;
export const STOCK_LIST_MAX_COLUMNS = 4; // "as many columns as fit" — capped, not fixed; a sparse page uses fewer
export const STOCK_LIST_HEADER_HEIGHT_LINES = 4; // title + "Available Models" subtitle + divider, in "line" units
export const STOCK_LIST_LINE_HEIGHT_PX = 20;

// One column's line capacity, ignoring the page header (the header only
// costs space once per page, not once per column).
export const STOCK_LIST_LINES_PER_COLUMN =
  Math.floor(STOCK_LIST_PAGE_HEIGHT / STOCK_LIST_LINE_HEIGHT_PX) - STOCK_LIST_HEADER_HEIGHT_LINES;

// Plain hex-color CSS, deliberately isolated from the app's own Tailwind
// stylesheet — both html-to-image and html2canvas fail on this app's real
// stylesheet (confirmed by hand: one hangs indefinitely inside its SVG→canvas
// step with no error, the other throws "Attempting to parse an unsupported
// color function 'oklch'" outright, since Tailwind v4's entire default
// palette resolves through oklch() custom properties neither library's color
// parser understands). Colors below are literal hex — swap them for the
// shop's real brand colors freely; the isolation only requires they never be
// a CSS custom property pointing back at the app's own stylesheet.
export const STOCK_LIST_EXPORT_STYLES = `
  body { margin: 0; padding: 0; width: ${STOCK_LIST_PAGE_WIDTH}px; font-family: Arial, Helvetica, sans-serif; color: #111111; background: #ffffff; }
  .title-block { text-align: center; padding: 26px 28px 6px; }
  .category-title { margin: 0; font-size: 32px; font-weight: 800; color: #1e3a8a; letter-spacing: 0.02em; text-transform: uppercase; }
  .category-subtitle { margin: 6px 0 0; font-size: 14px; color: #6b7280; }
  .divider { border: none; border-top: 2px solid #1e3a8a; margin: 14px 28px 0; }
  .page-columns { position: relative; column-gap: 28px; column-rule: 1px solid #d1d5db; padding: 18px 28px; }
  .column-divider { position: absolute; top: 0; width: 1px; background: #d1d5db; }
  .brand-block { break-inside: avoid; margin: 0 0 12px; }
  .brand-name { margin: 0 0 2px; font-size: 13px; font-weight: 700; color: #1d4ed8; }
  .model-list { margin: 0; }
  .model-item { margin: 0; font-size: 12px; line-height: ${STOCK_LIST_LINE_HEIGHT_PX}px; color: #111111; }
  .model-number { display: inline-block; min-width: 18px; }
  .footer { text-align: center; padding: 14px 28px; }
  .footer-shop { margin: 0; font-size: 13px; font-weight: 600; color: #6b7280; }
  .footer-address { margin: 2px 0 0; font-size: 11px; color: #9ca3af; }
  .footer-page { margin: 4px 0 0; font-size: 10px; color: #9ca3af; }
`;
