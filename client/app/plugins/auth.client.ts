// Loads the session state (and the CSRF cookie) before the first navigation
export default defineNuxtPlugin(async () => {
  await useAuthStore().refresh()
})
