import { Link } from 'react-router-dom';
import { AuthLayout } from '@/components/auth/AuthLayout';
import { SignInForm } from '@/components/auth/form/SignInForm';

export function SignIn() {
  return (
    <AuthLayout
      title="Welcome back"
      description="Sign in to pick up where you left off."
      footer={
        <>
          Forgot your password?{' '}
          <Link to="/forgot-password" className="font-medium text-primary hover:underline">
            Reset it
          </Link>
        </>
      }
    >
      <SignInForm />
    </AuthLayout>
  );
}
