import { useCargoCostBases } from '@/hooks/cargoHooks/cargoQueries';
import {
  useCreateCargoCostBasis,
  useUpdateCargoCostBasis,
  useDeleteCargoCostBasis,
} from '@/hooks/cargoHooks/cargoMutations';
import { cargoCostBasisCreateSchema, cargoCostBasisUpdateSchema } from '@/validations/cargoSchemas';
import { cargoCostBasisKeys } from '@/utils/queryKeys';
import { CARGO_COST_BASIS_CODE_OPTIONS } from '@/utils/constants';

export const cargoCostBasisCrudConfig = {
  queryKey: cargoCostBasisKeys,
  useList: useCargoCostBases,
  useCreate: useCreateCargoCostBasis,
  useUpdate: useUpdateCargoCostBasis,
  useDelete: useDeleteCargoCostBasis,
  columns: [
    { key: 'name', label: 'Name' },
    { key: 'code', label: 'Code' },
  ],
  createSchema: cargoCostBasisCreateSchema,
  updateSchema: cargoCostBasisUpdateSchema,
  fields: [
    { name: 'name', label: 'Name', component: 'text' },
    // Backend's CargoCostBasisUpdate doesn't accept code — immutable after creation,
    // the allocation service branches on it (phase-2-frontend spec §1.1/§7.1).
    { name: 'code', label: 'Code', component: 'select', options: CARGO_COST_BASIS_CODE_OPTIONS, editableOnUpdate: false },
  ],
};
