import { object, string, number } from 'yup';

export const categoryCreateSchema = object({
  name: string().required('Name is required').max(120),
});
export const categoryUpdateSchema = categoryCreateSchema.partial();

export const brandCreateSchema = object({
  name: string().required('Name is required').max(120),
});
export const brandUpdateSchema = brandCreateSchema.partial();

export const modelCreateSchema = object({
  brand_id: number().typeError('Select a brand').required('Select a brand'),
  name: string().required('Name is required').max(120),
});
// ModelUpdate is a genuinely different field set from ModelCreate (adds `priority`,
// which Create doesn't accept at all) — written directly rather than derived via
// .partial(), since .partial() only relaxes required-ness, it can't add a field.
export const modelUpdateSchema = object({
  brand_id: number().typeError('Select a brand'),
  name: string().max(120),
  priority: number().typeError('Priority must be a number').integer('Priority must be a whole number'),
});

export const itemCreateSchema = object({
  category_id: number().typeError('Select a category').required('Select a category'),
  model_id: number().typeError('Select a model').required('Select a model'),
  sku: string().required('SKU is required').max(64),
  variant: string().max(64).nullable().default(null),
});
// ItemUpdate omits sku entirely (immutable) — .omit() rather than .partial() alone,
// same reasoning as ExchangeRateUpdate in the phase-0 spec §8.1.
export const itemUpdateSchema = itemCreateSchema.omit(['sku']).partial();
