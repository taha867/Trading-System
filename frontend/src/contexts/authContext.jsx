import { createContext, useContext, useReducer, useState } from 'react';
import { authReducer, initialAuthState } from '@/reducers/authReducer';
import { hasValidRefreshToken } from '@/utils/tokenUtils';
import { fetchCurrentUser } from '@/services/authService';

const AuthContext = createContext(null);

async function hydrateAuth() {
  if (!hasValidRefreshToken()) return null;
  try {
    return await fetchCurrentUser();
  } catch {
    return null;
  }
}

export function AuthProvider({ children }) {
  const [state, dispatch] = useReducer(authReducer, initialAuthState);
  // Lazy useState initializer runs exactly once on mount — the idiomatic way to
  // create a stable "compute once" value without reading a ref during render.
  const [hydrationPromise] = useState(() => hydrateAuth());

  const value = { state, dispatch, hydrationPromise };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components -- colocating the provider with its context-accessor hook is deliberate here.
export function useAuthContext() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuthContext must be used within an AuthProvider');
  }
  return context;
}
