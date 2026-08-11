import { useForm, Controller } from 'react-hook-form';
import { yupResolver } from '@hookform/resolvers/yup';
import { signInSchema } from '@/validations/authSchemas';
import { useSignIn } from '@/hooks/authHooks/authMutations';
import { FormField, PasswordField } from '@/components/custom';
import { Button } from '@/components/ui/button';

const AUTH_INPUT_CLASSNAME = 'border-transparent bg-muted/60 focus-visible:bg-background';

export function SignInForm() {
  const {
    control,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm({
    resolver: yupResolver(signInSchema),
    defaultValues: { username: '', password: '' },
  });
  const { mutateAsync: signIn } = useSignIn();

  const onSubmit = async (values) => {
    try {
      await signIn(values);
    } catch {
      // fetchClient already toasts the backend's error detail
    }
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
            autoComplete="current-password"
            className={AUTH_INPUT_CLASSNAME}
          />
        )}
      />
      <Button type="submit" size="lg" disabled={isSubmitting} className="mt-2 w-full">
        {isSubmitting ? 'Signing in…' : 'Sign in'}
      </Button>
    </form>
  );
}
