const UNSAFE_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE'])

function readCookie(name: string) {
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`))
  return match ? decodeURIComponent(match[1]!) : undefined
}

/** $fetch bound to the course module API (/api/): CSRF token, activity tracking. */
export function useCourseApi() {
  const auth = useAuthStore()

  return $fetch.create({
    baseURL: '/api/',
    credentials: 'same-origin',
    onRequest({ options }) {
      if (!UNSAFE_METHODS.has((options.method ?? 'GET').toUpperCase())) return
      const token = readCookie('csrftoken')
      if (!token) return
      const headers = new Headers(options.headers)
      headers.set('X-CSRFToken', token)
      options.headers = headers
    },
    onResponse() {
      auth.touch()
    },
    async onResponseError({ response }) {
      // The server session expired or was terminated from another device
      if (response.status === 403 && auth.stage === 'authed') {
        await auth.refresh()
        if (auth.stage !== 'authed') await navigateTo('/login')
      }
    },
  })
}
