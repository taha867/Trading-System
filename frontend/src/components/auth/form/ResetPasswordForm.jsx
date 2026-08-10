import { useForm, Controller } from 'react-hook-form';
import { yupResolver } from '@hookform/resolvers/yup';
import toast from 'react-hot-toast';
import { resetPasswordSchema } from '@/validations/authSchemas';
import { FormField } from '@/components/custom';
import { Button } from '@/components/ui/button';
import { TOAST_MESSAGES } from '@/utils/constants';

// No password-reset flow exists on the backend yet — validates for real, submits nowhere.
export function ResetPasswordForm() {
  const {
    control,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm({
    resolver: yupResolver(resetPasswordSchema),
    defaultValues: { password: '', confirmPassword: '' },
  });

  const onSubmit = () => {
    toast(TOAST_MESSAGES.NOT_AVAILABLE_YET);
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4">
      <Controller
        name="password"
        control={control}
        render={({ field }) => (
          <FormField
            {...field}
            type="password"
            label="New password"
            error={errors.password?.message}
            autoComplete="new-password"
          />
        )}
      />
      <Controller
        name="confirmPassword"
        control={control}
        render={({ field }) => (
          <FormField
            {...field}
            type="password"
            label="Confirm new password"
            error={errors.confirmPassword?.message}
            autoComplete="new-password"
          />
        )}
      />
      <Button type="submit" size="lg" disabled={isSubmitting} className="mt-2 w-full">
        Reset password
      </Button>
    </form>
  );
}
