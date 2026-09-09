import { useState } from 'react';
import { FormCombobox } from '@/components/custom/FormCombobox';
import { useModel, useModels } from '@/hooks/catalogHooks/modelQueries';
import { useDebouncedValue } from '@/hooks/useDebouncedValue';

const SEARCH_DEBOUNCE_MS = 300;
const SEARCH_PAGE_SIZE = 20;

// Same reasoning as ItemCombobox — Models is large and growing (past 400),
// too big to fetch in full for a picker. Searches server-side via the
// generic CRUD factory's `name` search_filter, and separately resolves
// whatever model is already selected so its label survives once the search
// text no longer matches it.
export function ModelCombobox({ value, onChange, error, label = 'Model', placeholder = 'All models' }) {
  const [inputValue, setInputValue] = useState('');
  const debouncedSearch = useDebouncedValue(inputValue, SEARCH_DEBOUNCE_MS);

  const { data: searchData, isFetching } = useModels(
    debouncedSearch ? { name: debouncedSearch, page_size: SEARCH_PAGE_SIZE } : { page_size: SEARCH_PAGE_SIZE },
  );
  const { data: selectedModel } = useModel(value || null);

  const options = new Map();
  options.set('', { value: '', label: 'All models' });
  for (const model of searchData?.items ?? []) {
    options.set(String(model.id), { value: String(model.id), label: model.name });
  }
  if (selectedModel && !options.has(String(selectedModel.id))) {
    options.set(String(selectedModel.id), { value: String(selectedModel.id), label: selectedModel.name });
  }

  return (
    <FormCombobox
      label={label}
      placeholder={placeholder}
      searchPlaceholder="Search models…"
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
