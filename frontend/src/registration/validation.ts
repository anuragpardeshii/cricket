export interface RegistrationValues {
  username: string;
  email: string;
  phone: string;
  country_code: string;
  password: string;
  confirmPassword: string;
}

export type RegistrationField = keyof RegistrationValues;
export type RegistrationErrors = Partial<Record<RegistrationField, string>>;
export const MIN_PASSWORD_LENGTH = 7;

const obviousPasswords = new Set([
  'passwordpassword',
  'password123456789',
  '123456789012345',
  'qwertyuiopasdfgh',
]);

export const passwordLength = (password: string): number => Array.from(password).length;

export function validateField(field: RegistrationField, values: RegistrationValues): string | undefined {
  const value = values[field];
  switch (field) {
    case 'username':
      if (!value.trim()) return 'Enter a username.';
      if (!/^[A-Za-z0-9._-]{3,24}$/.test(value)) return 'Use 3–24 letters, numbers, dots, underscores, or hyphens.';
      return undefined;
    case 'email':
      if (!value.trim()) return 'Enter an email address.';
      if (value.length > 254) return 'Use 254 characters or fewer.';
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) return 'Enter a valid email address.';
      return undefined;
    case 'country_code':
      return /^\+[1-9][0-9]{0,3}$/.test(value) ? undefined : 'Select a country code.';
    case 'phone':
      if (!value) return undefined;
      if (!/^[0-9]{10}$/.test(value)) return 'Enter exactly 10 digits.';
      return undefined;
    case 'password': {
      const length = passwordLength(value);
      if (!value) return 'Enter a password.';
      if (length < MIN_PASSWORD_LENGTH) return `Use at least ${MIN_PASSWORD_LENGTH} characters.`;
      if (length > 128) return 'Use 128 characters or fewer.';
      if (obviousPasswords.has(value.toLowerCase()) || new Set(value).size === 1) return 'Choose a less predictable password.';
      return undefined;
    }
    case 'confirmPassword':
      if (!value) return 'Confirm your password.';
      if (value !== values.password) return 'Passwords do not match.';
      return undefined;
  }
}

export function validateRegistration(values: RegistrationValues): RegistrationErrors {
  const fields: RegistrationField[] = ['username', 'email', 'phone', 'country_code', 'password', 'confirmPassword'];
  return Object.fromEntries(fields.map((field) => [field, validateField(field, values)]).filter(([, error]) => Boolean(error))) as RegistrationErrors;
}
