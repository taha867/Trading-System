import { currentMonth, monthBounds, periodLabel, resolveDateFilter } from '@/utils/dateUtils';

// The date filter of a list / report screen, kept in the URL next to its other filters (pass the object returned by
// useSearchParamFilters). URL: ?month=2026-10 | ?from=2026-09-03&to=2026-10-05 | ?dates=all. Nothing in the URL =
// `defaultMode` ('month' = the current month, 'all' = every date). Returns the resolved filter plus setters; the
// screen sends `dateFrom` / `dateTo` (YYYY-MM-DD or undefined) to its query hook.
export const DATE_FILTER_KEYS = ['month', 'from', 'to', 'dates'];

export function useDateFilter(filters, { defaultMode = 'month' } = {}) {
  const resolved = resolveDateFilter(
    { month: filters.get('month'), from: filters.get('from'), to: filters.get('to'), dates: filters.get('dates') },
    defaultMode,
  );

  const setMonth = (month) =>
    filters.setFilters({ month, from: '', to: '', dates: month ? '' : 'all' });
  const setRange = ({ from = resolved.from, to = resolved.to }) =>
    filters.setFilters({ from, to, month: '', dates: from || to ? '' : 'range' });
  const setAll = () => filters.setFilters({ month: '', from: '', to: '', dates: 'all' });
  const setMode = (mode) => {
    if (mode === resolved.mode) return;
    if (mode === 'all') return setAll();
    if (mode === 'month') return setMonth(resolved.dateFrom ? resolved.dateFrom.slice(0, 7) : currentMonth());
    // range: start from the month in view so the boxes are not empty
    const bounds = resolved.mode === 'month' ? monthBounds(resolved.month) : null;
    return setRange({ from: bounds?.from ?? '', to: bounds?.to ?? '' });
  };

  return {
    ...resolved,
    label: periodLabel(resolved),
    defaultMode,
    setMonth,
    setRange,
    setAll,
    setMode,
  };
}
