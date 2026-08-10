import { string } from 'yup';

export const usernameField = string().required('Username is required').max(64);

export const passwordField = string().required('Password is required').min(8, 'Password must be at least 8 characters');
