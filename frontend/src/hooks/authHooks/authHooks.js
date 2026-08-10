import { useAuthContext } from '@/contexts/authContext';

export function useAuth() {
  const { state } = useAuthContext();
  return state; // { user, status }
}
