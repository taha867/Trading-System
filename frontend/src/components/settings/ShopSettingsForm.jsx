import { useEffect } from 'react';
import { useForm, Controller } from 'react-hook-form';
import { yupResolver } from '@hookform/resolvers/yup';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { FormField } from '@/components/custom';
import { settingUpdateSchema } from '@/validations/settingsSchemas';
import { useSetting } from '@/hooks/settingsHooks/settingsQueries';
import { useUpdateSetting } from '@/hooks/settingsHooks/settingsMutations';

export function ShopSettingsForm() {
  const { data } = useSetting();
  const updateMutation = useUpdateSetting();

  const {
    control,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm({
    resolver: yupResolver(settingUpdateSchema, {}, { raw: true }),
    defaultValues: { shop_name: '' },
  });

  // Settings has exactly one row, always already loaded by the time this
  // effect can run more than once — a simple sync-on-fetch is enough, no
  // open/mode/row-style reset-key dance needed the way CrudDrawer's does.
  useEffect(() => {
    if (data) reset({ shop_name: data.shop_name ?? '' });
  }, [data, reset]);

  const onSubmit = async (values) => {
    await updateMutation.mutateAsync({ shop_name: values.shop_name || null });
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Shop</CardTitle>
        <CardDescription>
          Shown at the top of the Stock List image you share with clients.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4 sm:max-w-sm">
          <Controller
            name="shop_name"
            control={control}
            render={({ field }) => (
              <FormField {...field} label="Shop name" placeholder="Your shop name" error={errors.shop_name?.message} />
            )}
          />
          <Button type="submit" disabled={isSubmitting} className="self-start">
            {isSubmitting ? 'Saving…' : 'Save'}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
