import type { Role } from '~/types/auth'
import type { CourseState, RequestStatus } from '~/types/course'

const dateFormat = new Intl.DateTimeFormat('ru-RU', { dateStyle: 'short' })
const dateTimeFormat = new Intl.DateTimeFormat('ru-RU', { dateStyle: 'short', timeStyle: 'short' })
const moneyFormat = new Intl.NumberFormat('ru-RU', { style: 'currency', currency: 'RUB' })

export const formatDate = (value: string) => dateFormat.format(new Date(value))
export const formatDateTime = (value: string) => dateTimeFormat.format(new Date(value))
export const formatMoney = (value: string | number | null) =>
  value === null ? '—' : moneyFormat.format(Number(value))

export const isLearner = (role?: Role) => role === 'user' || role === 'participant'

export const stateColor: Record<CourseState, string> = {
  open: 'success',
  running: 'info',
  archived: 'grey',
}

export const requestColor: Record<RequestStatus, string> = {
  registered: 'warning',
  done: 'success',
  rejected: 'grey',
}

/** Value for <input type="datetime-local"> in the browser's time zone. */
export function toLocalInput(value: string | Date) {
  const date = new Date(value)
  date.setMinutes(date.getMinutes() - date.getTimezoneOffset())
  return date.toISOString().slice(0, 16)
}
