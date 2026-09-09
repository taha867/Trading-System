import { useEffect, useState } from 'react';

// Generic, not domain-specific — delays reflecting a fast-changing value (a
// search input) so a query keyed on it fires once per pause in typing, not
// once per keystroke.
export function useDebouncedValue(value, delayMs) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);
  return debounced;
}
