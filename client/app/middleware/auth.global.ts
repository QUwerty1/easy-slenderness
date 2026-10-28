export default defineNuxtRouteMiddleware((to) => {
  const auth = useAuthStore()
  const access = to.meta.access ?? 'auth'

  // Tutors and admins without 2FA may only finish the 2FA setup wizard
  if (auth.stage === 'setup2fa') {
    return access === 'setup' || access === 'public' ? undefined : navigateTo('/2fa/setup')
  }
  if (access === 'guest' && auth.isAuthed) return navigateTo('/')
  if ((access === 'auth' || access === 'setup') && !auth.isAuthed) return navigateTo('/login')
})
