import type { FetchError } from 'ofetch'

export interface ApiError {
  status: number
  detail: string
  code?: string
  reasons?: string[]
  fields: Record<string, string[]>
}

const SYSTEM_KEYS = new Set(['detail', 'code', 'reasons'])

/** Split a DRF error response into a system message and per-field errors. */
export function parseApiError(error: unknown): ApiError {
  const fetchError = error as FetchError
  const data = (fetchError?.data ?? {}) as Record<string, unknown>
  const fields: Record<string, string[]> = {}
  for (const [key, value] of Object.entries(data)) {
    if (!SYSTEM_KEYS.has(key) && Array.isArray(value)) fields[key] = value.map(String)
  }
  const nonField = fields.non_field_errors?.[0]
  return {
    status: fetchError?.status ?? fetchError?.statusCode ?? 0,
    detail:
      (typeof data.detail === 'string' && data.detail) ||
      nonField ||
      (fetchError?.status ? 'Не удалось выполнить запрос' : 'Сервер недоступен. Попробуйте позже.'),
    code: typeof data.code === 'string' ? data.code : undefined,
    reasons: Array.isArray(data.reasons) ? data.reasons.map(String) : undefined,
    fields,
  }
}
