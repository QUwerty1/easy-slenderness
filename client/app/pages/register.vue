<script setup lang="ts">
definePageMeta({ access: 'guest' })

const auth = useAuthStore()
const dialog = useSystemDialog()
const form = ref()
const data = reactive({
  full_name: '',
  phone: '',
  email: '',
  password: '',
  pd_consent: false,
})
const errors = ref<Record<string, string[]>>({})
const existsOpen = ref(false)
const loading = ref(false)

function clearError(field: string) {
  errors.value[field] = []
}

async function submit() {
  const { valid } = await form.value.validate()
  if (!valid) return
  loading.value = true
  try {
    await auth.register({ ...data })
    await navigateTo('/')
  } catch (e) {
    const err = parseApiError(e)
    if (err.code === 'already_registered') existsOpen.value = true
    else if (Object.keys(err.fields).length) errors.value = err.fields
    else dialog.show(err.detail, 'Ошибка')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <AuthCard title="Регистрация">
    <v-form ref="form" @submit.prevent="submit">
      <v-card-text>
        <v-text-field
          v-model="data.full_name"
          label="ФИО"
          autocomplete="name"
          :rules="[rules.required]"
          :error-messages="errors.full_name"
          @update:model-value="clearError('full_name')"
        />
        <v-text-field
          v-model="data.phone"
          label="Телефон"
          type="tel"
          placeholder="+7 900 123-45-67"
          autocomplete="tel"
          :rules="[rules.required, rules.phone]"
          :error-messages="errors.phone"
          @update:model-value="clearError('phone')"
        />
        <v-text-field
          v-model="data.email"
          label="Email"
          type="email"
          autocomplete="email"
          :rules="[rules.required, rules.email]"
          :error-messages="errors.email"
          @update:model-value="clearError('email')"
        />
        <PasswordField
          v-model="data.password"
          label="Пароль"
          autocomplete="new-password"
          hint="Не короче 8 символов"
          :rules="[rules.required, rules.password]"
          :error-messages="errors.password"
          @update:model-value="clearError('password')"
        />
        <v-checkbox
          v-model="data.pd_consent"
          hide-details="auto"
          :error-messages="errors.pd_consent"
          label="Я даю согласие на обработку персональных данных в соответствии с 152-ФЗ"
        />
      </v-card-text>
      <v-card-actions class="flex-column ga-2 px-4">
        <v-btn
          block
          color="primary"
          variant="flat"
          type="submit"
          :disabled="!data.pd_consent"
          :loading="loading"
        >
          Зарегистрироваться
        </v-btn>
        <v-btn block to="/login">Отмена</v-btn>
      </v-card-actions>
    </v-form>
    <AlreadyRegisteredDialog v-model="existsOpen" />
  </AuthCard>
</template>
