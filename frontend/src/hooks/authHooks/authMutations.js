import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import * as authService from '@/services/authService';
import { useAuthContext } from '@/contexts/authContext';
import { storeToken, removeTokens, getRefreshToken } from '@/utils/tokenUtils';
import { authKeys } from '@/utils/queryKeys';

export function useSignIn() {
  const { dispatch } = useAuthContext();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: authService.signIn,
    onMutate: () => {
      dispatch({ type: 'AUTHENTICATING' });
    },
    onSuccess: async (tokens) => {
      storeToken(tokens);
      const user = await authService.fetchCurrentUser();
      queryClient.setQueryData(authKeys.me(), user);
      dispatch({ type: 'AUTHENTICATED', payload: { user } });
      navigate('/settings', { replace: true });
    },
    onError: () => {
      dispatch({ type: 'UNAUTHENTICATED' });
    },
  });
}

// Client-side-only — Phase 0's backend has no logout/token-revocation endpoint.
export function useSignOut() {
  const { dispatch } = useAuthContext();
  const navigate = useNavigate();

  return function signOut() {
    removeTokens();
    dispatch({ type: 'UNAUTHENTICATED' });
    navigate('/sign-in', { replace: true });
  };
}

export function useRefreshToken() {
  const { dispatch } = useAuthContext();

  return useMutation({
    mutationFn: () => authService.refreshToken(getRefreshToken()),
    onSuccess: (tokens) => storeToken(tokens),
    onError: () => dispatch({ type: 'UNAUTHENTICATED' }),
  });
}
