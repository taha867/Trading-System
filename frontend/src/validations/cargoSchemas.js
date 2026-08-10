import { object, string, number, array } from 'yup';
import { CARGO_COST_BASIS_CODE } from '@/utils/constants';

export const cargoModeCreateSchema = object({
  name: string().required('Name is required').max(64),
});
export const cargoModeUpdateSchema = cargoModeCreateSchema.partial();

export const cargoCostBasisCreateSchema = object({
  name: string().required('Name is required').max(64),
  code: string()
    .oneOf(Object.values(CARGO_COST_BASIS_CODE), 'Select a cost basis code')
    .required('Select a cost basis code'),
});
// code is immutable after creation (backend CargoCostBasisUpdate omits it entirely) —
// .omit(), same reasoning as ItemUpdate/PartyUpdate in the phase-1 spec.
export const cargoCostBasisUpdateSchema = cargoCostBasisCreateSchema.omit(['code']).partial();

// line_basis_values is deliberately NOT modeled here — whether a positive figure is
// required per line depends on the looked-up CargoCostBasis.code, not on a form value
// Yup can see, so that rule is validated in CargoShipmentForm itself (phase-2-frontend
// spec §2 decision 6), mirroring PurchaseOrderForm's exchange-rate-gate precedent.
export const cargoShipmentCreateSchema = object({
  cargo_agent_id: number().typeError('Select a cargo agent').required('Select a cargo agent'),
  cargo_mode_id: number().typeError('Select a cargo mode').required('Select a cargo mode'),
  cost_basis_id: number().typeError('Select a cost basis').required('Select a cost basis'),
  shipment_date: string().required('Shipment date is required'),
  total_cost_pkr: number()
    .typeError('Total cost must be a number')
    .positive('Total cost must be positive')
    .required('Total cost is required'),
  purchase_order_ids: array().of(number()).min(1, 'Attach at least one purchase order').required(),
});
