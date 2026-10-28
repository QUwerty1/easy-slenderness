<script setup lang="ts">
definePageMeta({ access: 'guest' })

const auth = useAuthStore()
const dialog = useSystemDialog()
const form = ref()
const email = ref('')
const loading = ref(false)

async function submit() {
  const { valid } = await form.value.validate()
  if (!valid) return
  loading.value = true
  try {
    await dialog.show(await auth.requestPasswordReset(email.value), 'Восстановление пароля')
    await navigateTo('/login')
  } catch (e) {
    dialog.show(parseApiError(e).detail, 'Ошибка')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <AuthCard
    title="Восстановление пароля"
    subtitle="Укажите email — мы отправим ссылку для сброса пароля"
  >
    <v-form ref="form" @submit.prevent="submit">
      <v-card-text>
        <v-text-field
          v-model="email"
          label="Email"
          type="email"
          autocomplete="email"
          :rules="[rules.required, rules.email]"
        />
      </v-card-text>
      <v-card-actions class="flex-column ga-2 px-4">
        <v-btn block color="primary" variant="flat" type="submit" :loading="loading">
          Отправить ссылку
        </v-btn>
        <v-btn block to="/login">Отмена</v-btn>
      </v-card-actions>
    </v-form>
  </AuthCard>
</template>
