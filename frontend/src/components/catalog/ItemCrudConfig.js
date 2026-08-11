import { useCategories } from '@/hooks/catalogHooks/categoryQueries';
import { useModels } from '@/hooks/catalogHooks/modelQueries';
import { useItems } from '@/hooks/catalogHooks/itemQueries';
import { useCreateItem, useUpdateItem, useDeleteItem } from '@/hooks/catalogHooks/itemMutations';
import { itemCreateSchema, itemUpdateSchema } from '@/validations/catalogSchemas';
import { itemKeys } from '@/utils/queryKeys';

// No server-side filter/sort exists on any Phase 1 list endpoint — fetching one
// page_size=100 page and mapping client-side is a deliberate, documented limitation
// (phase-1-frontend spec §1.1/§2), reused here for the category/model lookups.
const LOOKUP_PAGE = { page: 1, page_size: 100 };

export function useItemCrudConfig() {
  const { data: categoriesData } = useCategories(LOOKUP_PAGE);
  const { data: modelsData } = useModels(LOOKUP_PAGE);

  const categories = categoriesData?.items ?? [];
  const models = modelsData?.items ?? [];
  const categoryNameById = Object.fromEntries(categories.map((c) => [c.id, c.name]));
  const modelNameById = Object.fromEntries(models.map((m) => [m.id, m.name]));

  return {
    queryKey: itemKeys,
    useList: useItems,
    useCreate: useCreateItem,
    useUpdate: useUpdateItem,
    useDelete: useDeleteItem,
    columns: [
      { key: 'sku', label: 'SKU' },
      { key: 'category_id', label: 'Category', render: (row) => categoryNameById[row.category_id] ?? '—' },
      { key: 'model_id', label: 'Model', render: (row) => modelNameById[row.model_id] ?? '—' },
      { key: 'variant', label: 'Variant' },
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
        options: models.map((m) => ({ value: String(m.id), label: m.name })),
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
        options: models.map((m) => ({ value: String(m.id), label: m.name })),
      },
      // sku is not present in ItemUpdate on the backend — immutable after create.
      { name: 'sku', label: 'SKU', component: 'text', editableOnUpdate: false },
      { name: 'variant', label: 'Variant', component: 'text' },
    ],
  };
}
