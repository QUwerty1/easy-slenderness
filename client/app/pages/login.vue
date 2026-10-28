<script setup lang="ts">
definePageMeta({ access: 'guest' })

const auth = useAuthStore()
const dialog = useSystemDialog()
const form = ref()
const email = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)
// Password already checked in this session (e.g. after a reload): ask for the code
const twoFactorOpen = ref(auth.stage === 'pre2fa')

async function submit() {
  const { valid } = await form.value.validate()
  if (!valid) return
  loading.value = true
  error.value = ''
  try {
    const next = await auth.login(email.value, password.value)
    if (next === 'home') await navigateTo('/')
    else if (next === '2fa') twoFactorOpen.value = true
    else await navigateTo('/2fa/setup')
  } catch (e) {
    const err = parseApiError(e)
    if (err.code === 'invalid_credentials') error.value = err.detail
    else dialog.show(err.detail, 'Вход невозможен')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <AuthCard title="Вход" subtitle="Легкая стройность">
    <v-form ref="form" @submit.prevent="submit">
      <v-card-text>
        <v-text-field
          v-model="email"
          label="Email"
          type="email"
          autocomplete="email"
          :rules="[rules.required, rules.email]"
          @update:model-value="error = ''"
        />
        <PasswordField
          v-model="password"
          label="Пароль"
          autocomplete="current-password"
          :rules="[rules.required]"
          :error-messages="error"
          @update:model-value="error = ''"
        />
        <div class="text-right">
          <NuxtLink to="/forgot-password" class="text-body-2">Забыли пароль?</NuxtLink>
        </div>
      </v-card-text>
      <v-card-actions class="flex-column ga-2 px-4">
        <v-btn block color="primary" variant="flat" type="submit" :loading="loading">Войти</v-btn>
        <v-btn block to="/register">Регистрация</v-btn>
      </v-card-actions>
    </v-form>
    <TwoFactorDialog v-model="twoFactorOpen" />
  </AuthCard>
</template>
