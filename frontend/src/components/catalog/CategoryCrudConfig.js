import { useCategories } from '@/hooks/catalogHooks/categoryQueries';
import {
  useCreateCategory,
  useUpdateCategory,
  useDeleteCategory,
} from '@/hooks/catalogHooks/categoryMutations';
import { categoryCreateSchema, categoryUpdateSchema } from '@/validations/catalogSchemas';
import { categoryKeys } from '@/utils/queryKeys';

export const categoryCrudConfig = {
  queryKey: categoryKeys,
  useList: useCategories,
  useCreate: useCreateCategory,
  useUpdate: useUpdateCategory,
  useDelete: useDeleteCategory,
  columns: [{ key: 'name', label: 'Name' }],
  createSchema: categoryCreateSchema,
  updateSchema: categoryUpdateSchema,
  fields: [{ name: 'name', label: 'Name', component: 'text' }],
};
