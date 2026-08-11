import { useForm, Controller } from 'react-hook-form';
import { yupResolver } from '@hookform/resolvers/yup';
import toast from 'react-hot-toast';
import { forgotPasswordSchema } from '@/validations/authSchemas';
import { FormField } from '@/components/custom';
import { Button } from '@/components/ui/button';
import { TOAST_MESSAGES } from '@/utils/constants';

const AUTH_INPUT_CLASSNAME = 'border-transparent bg-muted/60 focus-visible:bg-background';

// No password-reset flow exists on the backend yet — validates for real, submits nowhere.
export function ForgotPasswordForm() {
  const {
    control,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm({
    resolver: yupResolver(forgotPasswordSchema),
    defaultValues: { username: '' },
  });

  const onSubmit = () => {
    toast(TOAST_MESSAGES.NOT_AVAILABLE_YET);
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4">
      <Controller
        name="username"
        control={control}
        render={({ field }) => (
          <FormField
            {...field}
            label="Username"
            error={errors.username?.message}
            autoComplete="username"
            className={AUTH_INPUT_CLASSNAME}
          />
        )}
      />
      <Button type="submit" size="lg" disabled={isSubmitting} className="mt-2 w-full">
        Send reset instructions
      </Button>
    </form>
  );
}
