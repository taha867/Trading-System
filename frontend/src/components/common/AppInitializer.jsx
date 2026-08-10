import { use, useEffect } from 'react';
import { useAuthContext } from '@/contexts/authContext';

// Reads the auth hydration promise via `use()` (CLAUDE.md §3.6) instead of a
// useEffect+useState combo — the promise suspends this component under the
// Suspense boundary in main.jsx until hydration resolves.
export function AppInitializer({ children }) {
  const { hydrationPromise, dispatch, state } = useAuthContext();
  const hydratedUser = use(hydrationPromise);

  useEffect(() => {
    if (state.status === 'idle') {
      dispatch(
        hydratedUser
          ? { type: 'AUTHENTICATED', payload: { user: hydratedUser } }
          : { type: 'UNAUTHENTICATED' },
      );
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hydratedUser, state.status]);

  return children;
}
