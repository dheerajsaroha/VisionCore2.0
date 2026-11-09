/**
 * Password policy, mirroring `validate_password_strength` in
 * `backend/app/core/security.py`.
 *
 * Kept in one place so the reset and change-password forms agree with the
 * server. The server is still the authority -- this only exists so a user is
 * not told "8 characters" and then rejected with 422 four times in a row,
 * which matters because `/auth/reset-password` allows only 3 attempts per
 * 5 minutes.
 */
export const PASSWORD_MIN_LENGTH = 8;

export const PASSWORD_REQUIREMENTS = [
  { id: 'length', label: `At least ${PASSWORD_MIN_LENGTH} characters`, test: (v) => v.length >= PASSWORD_MIN_LENGTH },
  { id: 'upper', label: 'One uppercase letter', test: (v) => /[A-Z]/.test(v) },
  { id: 'lower', label: 'One lowercase letter', test: (v) => /[a-z]/.test(v) },
  { id: 'digit', label: 'One number', test: (v) => /[0-9]/.test(v) },
  { id: 'special', label: 'One special character', test: (v) => /[!@#$%^&*(),.?":{}|<>\-_=+\x5B\]\\/;`~]/.test(v) },
];

export function checkPassword(value) {
  return PASSWORD_REQUIREMENTS.map((r) => ({ ...r, ok: r.test(value) }));
}

export function unmetRequirements(value) {
  return checkPassword(value).filter((r) => !r.ok).map((r) => r.label);
}

export function isPasswordValid(value) {
  return unmetRequirements(value).length === 0;
}
