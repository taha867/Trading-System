import { useModels } from '@/hooks/catalogHooks/modelQueries';
import {
  useCreateModel,
  useUpdateModel,
  useDeleteModel,
} from '@/hooks/catalogHooks/modelMutations';
import { modelCreateSchema, modelUpdateSchema } from '@/validations/catalogSchemas';
import { modelKeys } from '@/utils/queryKeys';

export const modelCrudConfig = {
  queryKey: modelKeys,
  useList: useModels,
  useCreate: useCreateModel,
  useUpdate: useUpdateModel,
  useDelete: useDeleteModel,
  columns: [
    { key: 'name', label: 'Name' },
    { key: 'priority', label: 'Priority' },
  ],
  createSchema: modelCreateSchema,
  updateSchema: modelUpdateSchema,
  fields: [
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
