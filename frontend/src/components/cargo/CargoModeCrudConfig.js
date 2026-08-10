import { useCargoModes } from '@/hooks/cargoHooks/cargoQueries';
import { useCreateCargoMode, useUpdateCargoMode, useDeleteCargoMode } from '@/hooks/cargoHooks/cargoMutations';
import { cargoModeCreateSchema, cargoModeUpdateSchema } from '@/validations/cargoSchemas';
import { cargoModeKeys } from '@/utils/queryKeys';

export const cargoModeCrudConfig = {
  queryKey: cargoModeKeys,
  useList: useCargoModes,
  useCreate: useCreateCargoMode,
  useUpdate: useUpdateCargoMode,
  useDelete: useDeleteCargoMode,
  columns: [{ key: 'name', label: 'Name' }],
  createSchema: cargoModeCreateSchema,
  updateSchema: cargoModeUpdateSchema,
  fields: [{ name: 'name', label: 'Name', component: 'text' }],
};
