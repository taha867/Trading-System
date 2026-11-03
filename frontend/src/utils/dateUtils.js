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
