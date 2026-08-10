export const initialAuthState = {
  user: null,
  status: 'idle', // 'idle' | 'authenticating' | 'authenticated' | 'unauthenticated'
};

export function authReducer(state, action) {
  switch (action.type) {
    case 'AUTHENTICATING':
      return { ...state, status: 'authenticating' };
    case 'AUTHENTICATED':
      return { user: action.payload.user, status: 'authenticated' };
    case 'UNAUTHENTICATED':
      return { user: null, status: 'unauthenticated' };
    default:
      return state;
  }
}
