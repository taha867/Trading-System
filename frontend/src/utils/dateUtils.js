// Month helpers for <input type="month"> values ("2026-10"). Everything here works
// in the browser's LOCAL time on purpose: `new Date().toISOString()` is UTC, which
// reports the wrong month for the first hours of a month in Pakistan time (UTC+5).

const MONTH_PATTERN = /^\d{4}-(0[1-9]|1[0-2])$/;

const pad = (value) => String(value).padStart(2, '0');

export function isValidMonth(value) {
  return MONTH_PATTERN.test(value ?? '');
}

export function currentMonth() {
  const now = new Date();
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}`;
}

// "2026-09" -> { from: "2026-09-01", to: "2026-09-30" }, or null for anything that
// isn't a valid month (an empty filter, a hand-edited URL param).
export function monthBounds(month) {
  if (!isValidMonth(month)) return null;
  const [year, monthNumber] = month.split('-').map(Number);
  // Day 0 of the NEXT month index is the last day of this one (JS months are 0-indexed,
  // so the 1-indexed monthNumber already points one index past the month typed).
  const lastDay = new Date(year, monthNumber, 0).getDate();
  return { from: `${month}-01`, to: `${month}-${pad(lastDay)}` };
}

export function shiftMonth(month, delta) {
  const [year, monthNumber] = month.split('-').map(Number);
  const shifted = new Date(year, monthNumber - 1 + delta, 1);
  return `${shifted.getFullYear()}-${pad(shifted.getMonth() + 1)}`;
}

export function monthLabel(month) {
  const [year, monthNumber] = month.split('-').map(Number);
  return new Date(year, monthNumber - 1, 1).toLocaleString('en-US', { month: 'long', year: 'numeric' });
}

// An ISO timestamp from the API (e.g. a row's created_at) -> "22 Oct 2026, 3:41 pm" in the
// browser's local time. Returns "—" for a missing value so callers can render it unconditionally.
export function formatDateTime(isoString) {
  if (!isoString) return '—';
  return new Date(isoString).toLocaleString('en-GB', { dateStyle: 'medium', timeStyle: 'short' });
}

// Today as "YYYY-MM-DD" in the browser's LOCAL time — the default for every date field. Not
// `new Date().toISOString().slice(0, 10)`, which is UTC and gives yesterday's date between midnight
// and 5 am in Pakistan.
export function todayIso() {
  const now = new Date();
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

// ---- date filter (month, From / To range, or all dates) ------------------------------------------------

const DATE_PATTERN = /^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$/;

// "YYYY-MM-DD" that is a real calendar day (rejects 2026-02-30).
export function isValidDate(value) {
  if (!DATE_PATTERN.test(value ?? '')) return false;
  const [year, month, day] = value.split('-').map(Number);
  const date = new Date(year, month - 1, day);
  return date.getFullYear() === year && date.getMonth() === month - 1 && date.getDate() === day;
}

const formatDay = (iso) => new Date(`${iso}T00:00:00`).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });

// A human label for a period: "October 2026", "3 Sep 2026 – 5 Oct 2026", "from 3 Sep 2026", "all dates".
export function periodLabel({ mode, month, dateFrom, dateTo }) {
  if (mode === 'month' && month) return monthLabel(month);
  if (dateFrom && dateTo) return `${formatDay(dateFrom)} – ${formatDay(dateTo)}`;
  if (dateFrom) return `from ${formatDay(dateFrom)}`;
  if (dateTo) return `up to ${formatDay(dateTo)}`;
  return 'all dates';
}

// Turn the URL's date params into the filter in force. `month` = one month, `from` / `to` = a range (either end may
// be missing = open-ended; `dates=range` keeps the range boxes open while both are still empty), `dates=all` = no
// date filter. Nothing valid in the URL means the screen's default: the current month, or all dates.
// Returns { mode: 'month' | 'range' | 'all', month, from, to, dateFrom, dateTo, isDefault }.
export function resolveDateFilter({ month, from, to, dates }, defaultMode = 'month') {
  const validFrom = isValidDate(from) ? from : '';
  const validTo = isValidDate(to) ? to : '';
  const inverted = validFrom && validTo && validFrom > validTo;
  // true when the URL holds no date choice at all (the screen is showing its own default)
  const isDefault = !month && !from && !to && !dates;
  if (validFrom || validTo || dates === 'range') {
    // an inverted range stays on screen (so the boxes can show the message) but is not sent to the API
    return { mode: 'range', month: '', from: validFrom, to: validTo, dateFrom: inverted ? undefined : validFrom || undefined, dateTo: inverted ? undefined : validTo || undefined, isDefault };
  }
  if (dates === 'all') return { mode: 'all', month: '', from: '', to: '', dateFrom: undefined, dateTo: undefined, isDefault };
  const chosen = isValidMonth(month) ? month : defaultMode === 'month' ? currentMonth() : '';
  if (chosen) {
    const bounds = monthBounds(chosen);
    return { mode: 'month', month: chosen, from: '', to: '', dateFrom: bounds.from, dateTo: bounds.to, isDefault };
  }
  return { mode: 'all', month: '', from: '', to: '', dateFrom: undefined, dateTo: undefined, isDefault };
}

// Label for the period a report returned: a whole calendar month reads "September 2026", anything else "3 Sep 2026 – 5 Oct 2026".
export function labelForDates(dateFrom, dateTo) {
  const month = dateFrom.slice(0, 7);
  const bounds = monthBounds(month);
  if (bounds && bounds.from === dateFrom && bounds.to === dateTo) return monthLabel(month);
  return periodLabel({ mode: 'range', dateFrom, dateTo });
}

// The URL params that reproduce a filter on another screen: ?month=2026-09 or ?from=..&to=.. (empty for all dates).
export function dateFilterParams({ mode, month, dateFrom, dateTo }) {
  if (mode === 'month' && month) return `month=${month}`;
  const parts = [];
  if (dateFrom) parts.push(`from=${dateFrom}`);
  if (dateTo) parts.push(`to=${dateTo}`);
  return parts.join('&');
}
