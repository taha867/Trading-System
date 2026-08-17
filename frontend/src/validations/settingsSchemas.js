import { object, string } from 'yup';

export const settingUpdateSchema = object({
  shop_name: string().max(120).nullable().default(null),
});
