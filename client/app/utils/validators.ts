export const PASSWORD_MIN_LENGTH = 8

// Mirrors the server-side normalization: Russian numbers, +7 / 8 prefix optional
export function normalizePhone(value: string): string | null {
  let digits = value.replace(/\D/g, '')
  if (digits.length === 11 && (digits[0] === '7' || digits[0] === '8')) digits = digits.slice(1)
  return digits.length === 10 && digits[0] === '9' ? `+7${digits}` : null
}

export const rules = {
  required: (v: unknown) =>
    (v !== null && v !== undefined && String(v).trim() !== '') || 'Обязательное поле',
  email: (v: string) => !v || /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v) || 'Некорректный email',
  phone: (v: string) =>
    !v || normalizePhone(v) !== null || 'Введите номер в формате +7 XXX XXX-XX-XX',
  password: (v: string) =>
    !v ||
    v.length >= PASSWORD_MIN_LENGTH ||
    `Пароль должен быть не короче ${PASSWORD_MIN_LENGTH} символов`,
}
