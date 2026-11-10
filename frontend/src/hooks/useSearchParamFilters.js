import { useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { isValidMonth } from '@/utils/dateUtils';

const SEARCH_DEBOUNCE_MS = 300;

// Generic, not domain-specific — keeps a list screen's filters and page in the URL's search
// params (so a filtered view survives a refresh and the browser Back button, and can be sent to
// someone) instead of in component state. The URL is the single source of truth; a filter's value
// is read straight off it.
//
// Any change to a filter resets the page to 1 (a narrow filter applied while sitting on page 3 of
// the full list would otherwise show an empty page) — only setPage() keeps the page.
//
// The free-text search box is the one exception that needs local state (the box must update on
// every keystroke), so it keeps its own `searchInput` and writes to the URL after a pause in
// typing. The debounce lives in the change handler, not in an effect, so clearing the box
// programmatically can't be raced by a stale pending write.
//
// The URL is user-editable, so values are read through the typed getters below (getMonth, getId,
// getOneOf) which fall back to "no filter" for anything malformed — a bad link shows the unfiltered
// list instead of a blank control or a 422 from the API.
export function useSearchParamFilters() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [searchInput, setSearchInput] = useState(() => searchParams.get('search') ?? '');
  const timerRef = useRef(null);

  useEffect(() => () => clearTimeout(timerRef.current), []);

  const get = (key) => searchParams.get(key) ?? '';
  const page = Math.max(1, Math.floor(Number(searchParams.get('page'))) || 1);

  // "YYYY-MM" or '' — an invalid month (?month=2026-13) is ignored rather than half-applied.
  const getMonth = () => (isValidMonth(get('month')) ? get('month') : '');
  // A positive integer id as a string, or ''.
  const getId = (key) => (/^[1-9]\d*$/.test(get(key)) ? get(key) : '');
  // The value if it is one of `allowed`, else ''.
  const getOneOf = (key, allowed) => (allowed.includes(get(key)) ? get(key) : '');

  // `changes` maps param name -> new value; an empty/undefined value removes the param. Uses the
  // functional form so other params (e.g. the container's `tab`) are preserved.
  const setFilters = (changes) => {
    setSearchParams(
      (previous) => {
        const next = new URLSearchParams(previous);
        for (const [key, value] of Object.entries(changes)) {
          if (value) next.set(key, String(value));
          else next.delete(key);
        }
        if (!('page' in changes)) next.delete('page');
        return next;
      },
      { replace: true },
    );
  };

  const handleSearchChange = (value) => {
    setSearchInput(value);
    clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => setFilters({ search: value.trim() }), SEARCH_DEBOUNCE_MS);
  };

  // Resets every named filter (and the search box) at once; params not named (like `tab`) stay.
  const clearFilters = (keys) => {
    clearTimeout(timerRef.current);
    setSearchInput('');
    setFilters(Object.fromEntries(keys.map((key) => [key, ''])));
  };

  return {
    get,
    getMonth,
    getId,
    getOneOf,
    page,
    setPage: (nextPage) => setFilters({ page: nextPage }),
    setFilters,
    searchInput,
    handleSearchChange,
    clearFilters,
  };
}
