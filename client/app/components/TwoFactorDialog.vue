<script setup lang="ts">
const open = defineModel<boolean>({ required: true })

const auth = useAuthStore()
const dialog = useSystemDialog()
const code = ref('')
const error = ref('')
const loading = ref(false)

async function submit() {
  if (!code.value.trim()) {
    error.value = 'Введите код'
    return
  }
  loading.value = true
  try {
    await auth.verify2fa(code.value)
    open.value = false
    await navigateTo('/')
  } catch (e) {
    const err = parseApiError(e)
    code.value = ''
    if (err.code === 'locked' || err.status === 403) {
      // Too many wrong codes: back to the login page
      open.value = false
      await auth.refresh()
      dialog.show(err.status === 403 ? 'Сессия истекла. Войдите снова.' : err.detail)
    } else {
      error.value = err.detail
    }
  } finally {
    loading.value = false
  }
}

async function cancel() {
  open.value = false
  await auth.logout()
}
</script>

<template>
  <v-dialog v-model="open" max-width="420" persistent>
    <v-card title="Подтверждение входа">
      <v-form @submit.prevent="submit">
        <v-card-text>
          <p class="mb-4">
            Введите 6-значный код из приложения-аутентификатора или один из резервных кодов.
          </p>
          <v-text-field
            v-model="code"
            label="Код подтверждения"
            autocomplete="one-time-code"
            autofocus
            :error-messages="error"
            @update:model-value="error = ''"
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn :disabled="loading" @click="cancel">Отмена</v-btn>
          <v-btn color="primary" variant="flat" type="submit" :loading="loading">
            Подтвердить
          </v-btn>
        </v-card-actions>
      </v-form>
    </v-card>
  </v-dialog>
</template>
