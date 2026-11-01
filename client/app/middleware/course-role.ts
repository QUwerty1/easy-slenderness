/** Sends the user home when the page is not meant for their role. */
export default defineNuxtRouteMiddleware((to) => {
  const auth = useAuthStore()
  const roles = to.meta.roles
  if (!roles || !auth.user) return
  if (!roles.includes(auth.user.role)) return navigateTo('/')
})
