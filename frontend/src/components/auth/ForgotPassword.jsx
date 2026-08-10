import { Link } from 'react-router-dom';
import { AuthLayout } from '@/components/auth/AuthLayout';
import { ForgotPasswordForm } from '@/components/auth/form/ForgotPasswordForm';

export function ForgotPassword() {
  return (
    <AuthLayout
      title="Forgot password"
      description="Enter your username and we'll help you get back in."
      footer={
        <>
          Remembered it after all?{' '}
          <Link to="/sign-in" className="font-medium text-primary hover:underline">
            Back to sign in
          </Link>
        </>
      }
    >
      <ForgotPasswordForm />
    </AuthLayout>
  );
}
