import { useCategories } from '@/hooks/catalogHooks/categoryQueries';
import { useModels } from '@/hooks/catalogHooks/modelQueries';
import { useBrands } from '@/hooks/catalogHooks/brandQueries';
import { useItems } from '@/hooks/catalogHooks/itemQueries';
import { useCreateItem, useUpdateItem, useDeleteItem } from '@/hooks/catalogHooks/itemMutations';
import { itemCreateSchema, itemUpdateSchema } from '@/validations/catalogSchemas';
import { itemKeys } from '@/utils/queryKeys';
import { LOOKUP_PAGE } from '@/utils/queryParams';

export function useItemCrudConfig() {
  const { data: categoriesData } = useCategories(LOOKUP_PAGE);
  const { data: modelsData } = useModels(LOOKUP_PAGE);

  const { data: brandsData } = useBrands(LOOKUP_PAGE);

  const categories = categoriesData?.items ?? [];
  // Model names no longer repeat the brand ("Y15", "A35"), so every pick-list shows brand + model: "Vivo Y15".
  const brandNameById = Object.fromEntries((brandsData?.items ?? []).map((b) => [b.id, b.name]));
  const models = (modelsData?.items ?? []).map((m) => ({ ...m, label: `${brandNameById[m.brand_id] ?? ''} ${m.name}`.trim() }));

  return {
    queryKey: itemKeys,
    useList: useItems,
    useCreate: useCreateItem,
    useUpdate: useUpdateItem,
    useDelete: useDeleteItem,
    columns: [
      { key: 'sku', label: 'SKU' },
      // ItemRead already embeds category_name/model_name — no separate lookup needed.
      { key: 'category_id', label: 'Category', render: (row) => row.category_name ?? '—' },
      { key: 'model_id', label: 'Model', render: (row) => row.model_name ?? '—' },
      { key: 'variant', label: 'Variant' },
      {
        key: 'compatible_models',
        label: 'Also fits',
        render: (row) => (row.compatible_models?.length ? row.compatible_models.map((m) => m.name).join(', ') : '—'),
      },
    ],
    createSchema: itemCreateSchema,
    updateSchema: itemUpdateSchema,
    filters: [
      {
        key: 'category_id',
        label: 'Category',
        component: 'select',
        options: categories.map((c) => ({ value: String(c.id), label: c.name })),
      },
      {
        key: 'model_id',
        label: 'Model',
        component: 'select',
        options: models.map((m) => ({ value: String(m.id), label: m.label })),
      },
      {
        key: 'variant',
        label: 'Variant',
        component: 'search',
        placeholder: 'Search variant…',
      },
    ],
    fields: [
      {
        name: 'category_id',
        label: 'Category',
        component: 'select',
        placeholder: 'Select a category',
        options: categories.map((c) => ({ value: String(c.id), label: c.name })),
      },
      {
        name: 'model_id',
        label: 'Model',
        component: 'select',
        placeholder: 'Select a model',
        options: models.map((m) => ({ value: String(m.id), label: m.label })),
      },
      // sku is not present in ItemUpdate on the backend — immutable after create.
      // Left empty on create, the server builds the code from category + brand + model + colour (e.g. OG-VIVO-Y15).
      { name: 'sku', label: 'SKU (empty = created automatically)', component: 'text', placeholder: 'e.g. OG-VIVO-Y15', editableOnUpdate: false },
      { name: 'variant', label: 'Variant', component: 'text' },
      {
        name: 'compatible_model_ids',
        label: 'Also compatible with',
        component: 'multiselect',
        // Raw int value (not String(m.id)) — compatible_model_ids is numeric end-to-end
        // (backend list[int], ItemRead.compatible_model_ids returns raw ints), unlike
        // the model_id/category_id selects above which target a string-based control.
        options: models.map((m) => ({ value: m.id, label: m.label })),
        defaultValue: [],
      },
    ],
  };
}
