interface SystemDialogState {
  open: boolean
  title: string
  text: string
}

let resolveCurrent: (() => void) | undefined

/** Modal window with an «ОК» button for system messages. */
export function useSystemDialog() {
  const state = useState<SystemDialogState>('system-dialog', () => ({
    open: false,
    title: '',
    text: '',
  }))

  function show(text: string, title = 'Сообщение') {
    resolveCurrent?.()
    state.value = { open: true, title, text }
    return new Promise<void>((resolve) => {
      resolveCurrent = resolve
    })
  }

  function close() {
    state.value.open = false
    resolveCurrent?.()
    resolveCurrent = undefined
  }

  return { state, show, close }
}
