import { useState } from 'react';
import { FormCombobox } from '@/components/custom/FormCombobox';
import { useDebouncedValue } from '@/hooks/useDebouncedValue';

const SEARCH_DEBOUNCE_MS = 300;

// Pick one invoice number from a list instead of typing a "contains" search — choosing "5" shows
// only invoice 5, not 35, 541 and 25. The list is fetched from the server (most recently used
// first) and narrowed as you type; "All invoices" clears the filter.
//
// Shared by Sales Orders and Purchase Orders: each passes its own `useOptions` hook (a query hook
// taking the search text and returning the options list) and `optionLabel` (how one option reads).
// `useOptions` is called as a hook, so it must be a stable, module-level hook — never an inline or
// conditionally chosen function (that would break the Rules of Hooks).
//
// `value` is the invoice number itself ('' = no filter), so a selected number that has scrolled out
// of the current search results is added back to the options and its label still renders.
export function InvoiceCombobox({ value, onChange, useOptions, optionLabel, label = 'Invoice' }) {
  const [inputValue, setInputValue] = useState('');
  const debouncedSearch = useDebouncedValue(inputValue.trim(), SEARCH_DEBOUNCE_MS);
  const { data, isFetching } = useOptions(debouncedSearch);

  // "All invoices" is only offered while nothing is being searched: with it always present, a search
  // with no matches would still show one row and the "No invoice numbers found." message could never appear.
  const options = [
    ...(debouncedSearch ? [] : [{ value: '', label: 'All invoices' }]),
    ...(data ?? []).map((option) => ({ value: option.invoice_number, label: optionLabel(option) })),
  ];
  if (value && !options.some((option) => option.value === value)) {
    options.push({ value, label: value });
  }

  return (
    <FormCombobox
      name="invoice_filter"
      label={label}
      placeholder="All invoices"
      searchPlaceholder="Search invoice numbers…"
      emptyLabel="No invoice numbers found."
      options={options}
      value={value}
      onChange={onChange}
      inputValue={inputValue}
      onInputValueChange={setInputValue}
      loading={isFetching}
    />
  );
}
