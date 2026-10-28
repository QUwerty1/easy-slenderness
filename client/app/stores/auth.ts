// Actions that only call the API are kept inside the store for a single public surface
// oxlint-disable unicorn/consistent-function-scoping
import { defineStore } from 'pinia'
import type {
  LoginNext,
  ProfilePayload,
  RegisterPayload,
  Stage,
  TotpSetup,
  User,
} from '~/types/auth'

/** Server session lifetime without activity (SESSION_COOKIE_AGE on the backend). */
export const SESSION_IDLE_MS = 30 * 60 * 1000

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const stage = ref<Stage>('anon')
  const lastActivity = ref(Date.now())

  const isAuthed = computed(() => stage.value === 'authed')

  function setSession(nextStage: Stage, nextUser: User | null = null) {
    stage.value = nextStage
    user.value = nextUser
  }

  function touch() {
    lastActivity.value = Date.now()
  }

  async function refresh() {
    try {
      const data = await useApi()<{ stage: Stage; user: User | null }>('session/')
      setSession(data.stage, data.user)
    } catch {
      setSession('anon')
    }
  }

  async function register(payload: RegisterPayload) {
    const data = await useApi()<User>('register/', { method: 'POST', body: payload })
    setSession('authed', data)
  }

  async function login(email: string, password: string) {
    const data = await useApi()<{ next: LoginNext; user?: User }>('login/', {
      method: 'POST',
      body: { email, password },
    })
    if (data.next === 'home') setSession('authed', data.user)
    else if (data.next === '2fa') setSession('pre2fa')
    else await refresh()
    return data.next
  }

  async function verify2fa(code: string) {
    const data = await useApi()<User>('login/2fa/', { method: 'POST', body: { code } })
    setSession('authed', data)
  }

  async function logout() {
    try {
      await useApi()('logout/', { method: 'POST' })
    } finally {
      setSession('anon')
    }
  }

  async function updateProfile(payload: ProfilePayload) {
    user.value = await useApi()<User>('me/', { method: 'PATCH', body: payload })
  }

  async function changePassword(currentPassword: string, newPassword: string) {
    await useApi()('me/password/', {
      method: 'POST',
      body: { current_password: currentPassword, new_password: newPassword },
    })
  }

  async function deleteAccount(password: string) {
    await useApi()('me/delete/', { method: 'POST', body: { password } })
    setSession('anon')
  }

  function begin2fa() {
    return useApi()<TotpSetup>('2fa/setup/', { method: 'POST' })
  }

  async function confirm2fa(code: string) {
    const data = await useApi()<{ backup_codes: string[]; user: User }>('2fa/confirm/', {
      method: 'POST',
      body: { code },
    })
    setSession('authed', data.user)
    return data.backup_codes
  }

  async function requestPasswordReset(email: string) {
    const data = await useApi()<{ detail: string }>('password-reset/', {
      method: 'POST',
      body: { email },
    })
    return data.detail
  }

  async function validateResetLink(uid: string, token: string) {
    await useApi()('password-reset/validate/', { method: 'POST', body: { uid, token } })
  }

  async function resetPassword(uid: string, token: string, newPassword: string) {
    await useApi()('password-reset/confirm/', {
      method: 'POST',
      body: { uid, token, new_password: newPassword },
    })
    setSession('anon')
  }

  return {
    user,
    stage,
    lastActivity,
    isAuthed,
    touch,
    refresh,
    register,
    login,
    verify2fa,
    logout,
    updateProfile,
    changePassword,
    deleteAccount,
    begin2fa,
    confirm2fa,
    requestPasswordReset,
    validateResetLink,
    resetPassword,
  }
})
