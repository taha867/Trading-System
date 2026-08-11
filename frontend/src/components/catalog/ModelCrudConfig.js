import { useBrands } from '@/hooks/catalogHooks/brandQueries';
import { useModels } from '@/hooks/catalogHooks/modelQueries';
import {
  useCreateModel,
  useUpdateModel,
  useDeleteModel,
} from '@/hooks/catalogHooks/modelMutations';
import { modelCreateSchema, modelUpdateSchema } from '@/validations/catalogSchemas';
import { modelKeys } from '@/utils/queryKeys';

// No server-side filter/sort exists on any Phase 1 list endpoint — fetching one
// page_size=100 page and mapping client-side is a deliberate, documented limitation
// (phase-1-frontend spec §1.1/§2), reused here for the brand lookup.
const LOOKUP_PAGE = { page: 1, page_size: 100 };

export function useModelCrudConfig() {
  const { data: brandsData } = useBrands(LOOKUP_PAGE);
  const brands = brandsData?.items ?? [];
  const brandNameById = Object.fromEntries(brands.map((b) => [b.id, b.name]));

  return {
    queryKey: modelKeys,
    useList: useModels,
    useCreate: useCreateModel,
    useUpdate: useUpdateModel,
    useDelete: useDeleteModel,
    columns: [
      { key: 'brand_id', label: 'Brand', render: (row) => brandNameById[row.brand_id] ?? '—' },
      { key: 'name', label: 'Name' },
      { key: 'priority', label: 'Priority' },
    ],
    createSchema: modelCreateSchema,
    updateSchema: modelUpdateSchema,
    fields: [
      {
        name: 'brand_id',
        label: 'Brand',
        component: 'select',
        placeholder: 'Select a brand',
        options: brands.map((b) => ({ value: String(b.id), label: b.name })),
      },
      { name: 'name', label: 'Name', component: 'text' },
      // Absent from ModelCreate on the backend — hidden until the row exists.
      {
        name: 'priority',
        label: 'Priority (used for reorder ranking from Phase 8)',
        component: 'number',
        hideOnCreate: true,
      },
    ],
  };
}
