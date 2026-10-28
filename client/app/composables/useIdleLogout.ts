const CHECK_INTERVAL_MS = 15 * 1000

/**
 * Opens the login page once the server session has expired from inactivity.
 * Activity is the last API request, the same thing the server counts.
 */
export function useIdleLogout() {
  const auth = useAuthStore()
  const dialog = useSystemDialog()
  let timer: ReturnType<typeof setInterval> | undefined

  onMounted(() => {
    timer = setInterval(async () => {
      if (!auth.isAuthed || Date.now() - auth.lastActivity < SESSION_IDLE_MS) return
      await auth.logout().catch(() => {})
      await navigateTo('/login')
      dialog.show('Сеанс завершён после 30 минут бездействия. Войдите снова.')
    }, CHECK_INTERVAL_MS)
  })

  onBeforeUnmount(() => clearInterval(timer))
}
