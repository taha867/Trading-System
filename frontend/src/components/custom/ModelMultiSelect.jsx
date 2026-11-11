import { useState } from 'react';
import { X } from 'lucide-react';
import { Label } from '@/components/ui/label';
import { FormCombobox } from '@/components/custom/FormCombobox';
import { useBrands } from '@/hooks/catalogHooks/brandQueries';
import { useModels } from '@/hooks/catalogHooks/modelQueries';
import { useDebouncedValue } from '@/hooks/useDebouncedValue';
import { LOOKUP_PAGE } from '@/utils/queryParams';
import { modelLabel } from '@/utils/modelLabel';

const SEARCH_DEBOUNCE_MS = 300;
const SEARCH_PAGE_SIZE = 20;

// "Also fits": pick any number of models from a list too long to show in full. The chosen models are shown as
// removable chips; a search box (server-side, same as ModelCombobox) adds more. `value` is an array of model ids
// (numbers, like the API); `selectedModels` supplies names for ids that are already chosen when the form opens
// (an item's embedded compatible_models) - ids picked in this session keep the label they were picked with.
export function ModelMultiSelect({ label, error, value = [], onChange, selectedModels = [], excludeId }) {
  const [inputValue, setInputValue] = useState('');
  const [pickedLabels, setPickedLabels] = useState({});
  const debouncedSearch = useDebouncedValue(inputValue, SEARCH_DEBOUNCE_MS);

  const { data: brandsData } = useBrands(LOOKUP_PAGE);
  const brandNameById = Object.fromEntries((brandsData?.items ?? []).map((b) => [b.id, b.name]));
  const { data: searchData, isFetching } = useModels(
    debouncedSearch ? { name: debouncedSearch, page_size: SEARCH_PAGE_SIZE } : { page_size: SEARCH_PAGE_SIZE },
  );
  const results = searchData?.items ?? [];

  const labelById = {
    ...Object.fromEntries(selectedModels.map((m) => [m.id, modelLabel(m, brandNameById)])),
    ...pickedLabels,
  };
  const options = results
    .filter((model) => !value.includes(model.id) && model.id !== Number(excludeId))
    .map((model) => ({ value: String(model.id), label: modelLabel(model, brandNameById) }));

  const add = (modelId) => {
    if (!modelId) return;
    const id = Number(modelId);
    const picked = results.find((model) => model.id === id);
    if (picked) setPickedLabels((previous) => ({ ...previous, [id]: modelLabel(picked, brandNameById) }));
    onChange([...value, id]);
    setInputValue('');
  };

  return (
    <div className="flex flex-col gap-1.5">
      {label && <Label>{label}</Label>}
      {value.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {value.map((id) => (
            <span key={id} className="inline-flex items-center gap-1 rounded-full border bg-muted/40 px-2.5 py-1 text-xs">
              {labelById[id] ?? `Model #${id}`}
              <button
                type="button"
                className="text-muted-foreground hover:text-foreground"
                aria-label={`Remove ${labelById[id] ?? id}`}
                onClick={() => onChange(value.filter((v) => v !== id))}
              >
                <X className="size-3" />
              </button>
            </span>
          ))}
        </div>
      )}
      <FormCombobox
        placeholder="Add a phone that also fits…"
        searchPlaceholder="Search models…"
        options={options}
        value=""
        onChange={add}
        inputValue={inputValue}
        onInputValueChange={setInputValue}
        loading={isFetching}
      />
      {error && <p className="text-sm text-destructive">{error}</p>}
    </div>
  );
}
