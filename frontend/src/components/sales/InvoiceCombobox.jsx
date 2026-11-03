import { useState } from 'react';
import { FormCombobox } from '@/components/custom/FormCombobox';
import { useInvoiceOptions } from '@/hooks/salesHooks/salesQueries';
import { useDebouncedValue } from '@/hooks/useDebouncedValue';

const SEARCH_DEBOUNCE_MS = 300;

// Pick one invoice number from a list instead of typing a "contains" search — choosing "5" shows
// only invoice 5, not 35, 541 and 25. The list is fetched from the server (most recently used
// first) and narrowed as you type; "All invoices" clears the filter.
//
// `value` is the invoice number itself ('' = no filter), so a selected number that has scrolled out
// of the current search results is added back to the options and its label still renders.
export function InvoiceCombobox({ value, onChange, label = 'Invoice' }) {
  const [inputValue, setInputValue] = useState('');
  const debouncedSearch = useDebouncedValue(inputValue.trim(), SEARCH_DEBOUNCE_MS);
  const { data, isFetching } = useInvoiceOptions(debouncedSearch);

  const options = [
    { value: '', label: 'All invoices' },
    ...(data ?? []).map((option) => ({
      value: option.invoice_number,
      // One number can cover several sales (numbers aren't unique) — say so rather than hide it.
      label: option.sale_count > 1 ? `${option.invoice_number} (${option.sale_count} sales)` : option.invoice_number,
    })),
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
