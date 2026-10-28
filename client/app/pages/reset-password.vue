<script setup lang="ts">
definePageMeta({ access: 'public' })

const route = useRoute()
const auth = useAuthStore()
const dialog = useSystemDialog()
const uid = String(route.query.uid ?? '')
const token = String(route.query.token ?? '')

const form = ref()
const password = ref('')
const errors = ref<string[]>([])
const linkState = ref<'checking' | 'valid' | 'invalid'>('checking')
const invalidMessage = ref('Ссылка для сброса пароля недействительна или устарела.')
const loading = ref(false)

onMounted(async () => {
  if (!uid || !token) {
    linkState.value = 'invalid'
    return
  }
  try {
    await auth.validateResetLink(uid, token)
    linkState.value = 'valid'
  } catch (e) {
    const err = parseApiError(e)
    if (err.code === 'invalid_link') invalidMessage.value = err.detail
    linkState.value = 'invalid'
  }
})

async function submit() {
  const { valid } = await form.value.validate()
  if (!valid) return
  loading.value = true
  try {
    await auth.resetPassword(uid, token, password.value)
    await dialog.show('Пароль изменён. Войдите с новым паролем.')
    await navigateTo('/login')
  } catch (e) {
    const err = parseApiError(e)
    if (err.fields.new_password) errors.value = err.fields.new_password
    else if (err.code === 'invalid_link') {
      invalidMessage.value = err.detail
      linkState.value = 'invalid'
    } else dialog.show(err.detail, 'Ошибка')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <AuthCard title="Новый пароль">
    <v-card-text v-if="linkState === 'checking'" class="text-center">
      <v-progress-circular indeterminate color="primary" />
    </v-card-text>
    <template v-else-if="linkState === 'invalid'">
      <v-card-text>
        <v-alert type="error" variant="tonal">{{ invalidMessage }}</v-alert>
      </v-card-text>
      <v-card-actions class="flex-column ga-2 px-4">
        <v-btn block color="primary" variant="flat" to="/forgot-password">
          Запросить новую ссылку
        </v-btn>
        <v-btn block to="/login">На страницу входа</v-btn>
      </v-card-actions>
    </template>
    <v-form v-else ref="form" @submit.prevent="submit">
      <v-card-text>
        <PasswordField
          v-model="password"
          label="Новый пароль"
          autocomplete="new-password"
          hint="Не короче 8 символов"
          :rules="[rules.required, rules.password]"
          :error-messages="errors"
          @update:model-value="errors = []"
        />
      </v-card-text>
      <v-card-actions class="px-4">
        <v-btn block color="primary" variant="flat" type="submit" :loading="loading">
          Сохранить
        </v-btn>
      </v-card-actions>
    </v-form>
  </AuthCard>
</template>
