import { Link } from 'react-router-dom';
import { AuthLayout } from '@/components/auth/AuthLayout';
import { ResetPasswordForm } from '@/components/auth/form/ResetPasswordForm';

export function ResetPassword() {
  return (
    <AuthLayout
      title="Reset password"
      description="Choose a new password for your account."
      footer={
        <>
          <Link to="/sign-in" className="font-medium text-primary hover:underline">
            Back to sign in
          </Link>
        </>
      }
    >
      <ResetPasswordForm />
    </AuthLayout>
  );
}
