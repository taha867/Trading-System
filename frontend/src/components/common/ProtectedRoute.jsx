import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '@/hooks/authHooks/authHooks';

export function ProtectedRoute() {
  const { status } = useAuth();
  const location = useLocation();

  // Hydration hasn't dispatched a real status yet — wait rather than bounce a
  // genuinely logged-in user to /sign-in on first paint.
  if (status === 'idle') return null;

  if (status !== 'authenticated') {
    return <Navigate to="/sign-in" state={{ from: location }} replace />;
  }

  return <Outlet />;
}
