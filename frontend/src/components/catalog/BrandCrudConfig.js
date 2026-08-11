import { useBrands } from '@/hooks/catalogHooks/brandQueries';
import { useCreateBrand, useUpdateBrand, useDeleteBrand } from '@/hooks/catalogHooks/brandMutations';
import { brandCreateSchema, brandUpdateSchema } from '@/validations/catalogSchemas';
import { brandKeys } from '@/utils/queryKeys';

export const brandCrudConfig = {
  queryKey: brandKeys,
  useList: useBrands,
  useCreate: useCreateBrand,
  useUpdate: useUpdateBrand,
  useDelete: useDeleteBrand,
  columns: [{ key: 'name', label: 'Name' }],
  createSchema: brandCreateSchema,
  updateSchema: brandUpdateSchema,
  fields: [{ name: 'name', label: 'Name', component: 'text' }],
};
