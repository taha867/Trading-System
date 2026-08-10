import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '@/hooks/authHooks/authHooks';

export function AuthRouteProtection() {
  const { status } = useAuth();

  if (status === 'idle') return null;

  if (status === 'authenticated') {
    return <Navigate to="/settings" replace />;
  }

  // 'unauthenticated' or 'authenticating' — stay on the auth route, the form
  // itself shows its own submitting state.
  return <Outlet />;
}
