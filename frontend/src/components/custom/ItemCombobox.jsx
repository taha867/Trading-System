import { useState } from 'react';
import { FormCombobox } from '@/components/custom/FormCombobox';
import { useItem, useItems } from '@/hooks/catalogHooks/itemQueries';
import { useDebouncedValue } from '@/hooks/useDebouncedValue';

const SEARCH_DEBOUNCE_MS = 300;
const SEARCH_PAGE_SIZE = 20;

function itemLabel(item) {
  return `${item.sku} · ${item.model_name}${item.variant ? ` (${item.variant})` : ''}`;
}

// Items are too numerous to fetch in full (see LOOKUP_PAGE's history in
// StockLotTable/PurchaseOrderForm/SalesOrderForm before this component
// existed) — this searches server-side instead, and separately resolves
// whatever item is already selected so its label still renders once the
// search text no longer matches it.
export function ItemCombobox({ value, onChange, error, label = 'Item', placeholder = 'Select an item' }) {
  const [inputValue, setInputValue] = useState('');
  const debouncedSearch = useDebouncedValue(inputValue, SEARCH_DEBOUNCE_MS);

  const { data: searchData, isFetching } = useItems(
    debouncedSearch ? { search: debouncedSearch, page_size: SEARCH_PAGE_SIZE } : { page_size: SEARCH_PAGE_SIZE },
  );
  const { data: selectedItem } = useItem(value || null);

  const options = new Map();
  for (const item of searchData?.items ?? []) {
    options.set(String(item.id), { value: String(item.id), label: itemLabel(item) });
  }
  if (selectedItem && !options.has(String(selectedItem.id))) {
    options.set(String(selectedItem.id), { value: String(selectedItem.id), label: itemLabel(selectedItem) });
  }

  return (
    <FormCombobox
      label={label}
      placeholder={placeholder}
      searchPlaceholder="Search by SKU or model…"
      options={Array.from(options.values())}
      value={value}
      onChange={onChange}
      inputValue={inputValue}
      onInputValueChange={setInputValue}
      loading={isFetching}
      error={error}
    />
  );
}
