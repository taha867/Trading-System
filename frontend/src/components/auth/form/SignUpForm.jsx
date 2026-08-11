import { useForm, Controller } from 'react-hook-form';
import { yupResolver } from '@hookform/resolvers/yup';
import toast from 'react-hot-toast';
import { signUpSchema } from '@/validations/authSchemas';
import { FormField, PasswordField } from '@/components/custom';
import { Button } from '@/components/ui/button';
import { TOAST_MESSAGES } from '@/utils/constants';

const AUTH_INPUT_CLASSNAME = 'border-transparent bg-muted/60 focus-visible:bg-background';

// No backend registration endpoint exists yet (Phase 0's single user is seeded, not
// self-registered) — this form validates for real but has nowhere to submit to.
export function SignUpForm() {
  const {
    control,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm({
    resolver: yupResolver(signUpSchema),
    defaultValues: { username: '', password: '', confirmPassword: '' },
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
      <Controller
        name="password"
        control={control}
        render={({ field }) => (
          <PasswordField
            {...field}
            label="Password"
            error={errors.password?.message}
            autoComplete="new-password"
            className={AUTH_INPUT_CLASSNAME}
          />
        )}
      />
      <Controller
        name="confirmPassword"
        control={control}
        render={({ field }) => (
          <PasswordField
            {...field}
            label="Confirm password"
            error={errors.confirmPassword?.message}
            autoComplete="new-password"
            className={AUTH_INPUT_CLASSNAME}
          />
        )}
      />
      <Button type="submit" size="lg" disabled={isSubmitting} className="mt-2 w-full">
        Sign up
      </Button>
    </form>
  );
}
