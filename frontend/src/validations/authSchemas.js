import { object, string, ref } from 'yup';
import { usernameField, passwordField } from '@/validations/commonSchemas';

export const signInSchema = object({
  username: usernameField,
  password: string().required('Password is required'),
});

// Backend has no /auth/register endpoint yet — this schema only backs SignUpForm's
// inline validation, per the Phase 0 frontend spec's "stub, not skipped" decision.
export const signUpSchema = object({
  username: usernameField,
  password: passwordField,
  confirmPassword: string()
    .oneOf([ref('password')], 'Passwords must match')
    .required('Please confirm your password'),
});

export const forgotPasswordSchema = object({
  username: usernameField,
});

export const resetPasswordSchema = object({
  password: passwordField,
  confirmPassword: string()
    .oneOf([ref('password')], 'Passwords must match')
    .required('Please confirm your password'),
});
