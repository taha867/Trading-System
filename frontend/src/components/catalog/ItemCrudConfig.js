import { useCategories } from '@/hooks/catalogHooks/categoryQueries';
import { useItems } from '@/hooks/catalogHooks/itemQueries';
import { useCreateItem, useUpdateItem, useDeleteItem } from '@/hooks/catalogHooks/itemMutations';
import { itemCreateSchema, itemUpdateSchema } from '@/validations/catalogSchemas';
import { itemKeys } from '@/utils/queryKeys';
import { LOOKUP_PAGE } from '@/utils/queryParams';

export function useItemCrudConfig() {
  const { data: categoriesData } = useCategories(LOOKUP_PAGE);

  const categories = categoriesData?.items ?? [];

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
      // The model list is too long for a drop-down, so the list is searched instead (code, phone or colour).
      { key: 'search', label: 'Search', component: 'search', placeholder: 'Search code, phone or colour…' },
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
        component: 'model-combobox',
        placeholder: 'Select a model',
      },
      // sku is not present in ItemUpdate on the backend — immutable after create.
      // Left empty on create, the server builds the code from category + brand + model + colour (e.g. OG-VIVO-Y15).
      { name: 'sku', label: 'SKU (empty = created automatically)', component: 'text', placeholder: 'e.g. OG-VIVO-Y15', editableOnUpdate: false },
      { name: 'variant', label: 'Variant', component: 'text' },
      {
        name: 'compatible_model_ids',
        label: 'Also compatible with',
        component: 'model-multiselect',
        // Raw int ids (compatible_model_ids is numeric end-to-end: backend list[int]); names for the ids already
        // saved on the item come from its embedded compatible_models.
        initialFrom: 'compatible_models',
        defaultValue: [],
      },
    ],
  };
}
