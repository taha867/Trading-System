import { object, string, array, number } from 'yup';
import { PARTY_ROLE } from '@/utils/constants';

export const partyCreateSchema = object({
  name: string().required('Name is required').max(120),
  contact: string().max(64).nullable().default(null),
  address: string().max(255).nullable().default(null),
  roles: array().of(string().oneOf(Object.values(PARTY_ROLE))).min(1, 'Select at least one role').required(),
  opening_balance: number().typeError('Opening balance must be a number').default(0),
});

// opening_balance is write-once on the backend — .omit(), same reasoning as
// ItemUpdate/ExchangeRateUpdate: removed entirely, not merely made optional.
export const partyUpdateSchema = partyCreateSchema.omit(['opening_balance']).partial();
