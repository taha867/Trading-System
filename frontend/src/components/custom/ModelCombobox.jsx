import { useState } from 'react';
import { FormCombobox } from '@/components/custom/FormCombobox';
import { useBrands } from '@/hooks/catalogHooks/brandQueries';
import { useModel, useModels } from '@/hooks/catalogHooks/modelQueries';
import { useDebouncedValue } from '@/hooks/useDebouncedValue';
import { LOOKUP_PAGE } from '@/utils/queryParams';
import { modelLabel } from '@/utils/modelLabel';

const SEARCH_DEBOUNCE_MS = 300;
const SEARCH_PAGE_SIZE = 20;

// Same reasoning as ItemCombobox — Models is large and growing (past 500), too big to fetch in full for a
// picker. Searches server-side via the generic CRUD factory's `name` search_filter, and separately resolves
// whatever model is already selected so its label survives once the search text no longer matches it.
// Labels are "Brand Model" (see utils/modelLabel.js). `emptyLabel` adds a leading "no choice" row for filters;
// forms pass emptyLabel={null} so a model must be picked.
export function ModelCombobox({
  value,
  onChange,
  error,
  label = 'Model',
  placeholder = 'All models',
  emptyLabel = 'All models',
}) {
  const [inputValue, setInputValue] = useState('');
  const debouncedSearch = useDebouncedValue(inputValue, SEARCH_DEBOUNCE_MS);

  const { data: brandsData } = useBrands(LOOKUP_PAGE);
  const brandNameById = Object.fromEntries((brandsData?.items ?? []).map((b) => [b.id, b.name]));

  const { data: searchData, isFetching } = useModels(
    debouncedSearch ? { name: debouncedSearch, page_size: SEARCH_PAGE_SIZE } : { page_size: SEARCH_PAGE_SIZE },
  );
  const { data: selectedModel } = useModel(value || null);

  const options = new Map();
  if (emptyLabel) options.set('', { value: '', label: emptyLabel });
  for (const model of searchData?.items ?? []) {
    options.set(String(model.id), { value: String(model.id), label: modelLabel(model, brandNameById) });
  }
  if (selectedModel && !options.has(String(selectedModel.id))) {
    options.set(String(selectedModel.id), { value: String(selectedModel.id), label: modelLabel(selectedModel, brandNameById) });
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
