<script setup lang="ts">
const auth = useAuthStore()
const dialog = useSystemDialog()

const tab = ref('profile')
const form = ref()
const data = reactive({
  full_name: auth.user?.full_name ?? '',
  phone: auth.user?.phone ?? '',
  email: auth.user?.email ?? '',
  current_password: '',
})
const errors = ref<Record<string, string[]>>({})
const loading = ref(false)
const passwordOpen = ref(false)
const deleteOpen = ref(false)

function clearError(field: string) {
  errors.value[field] = []
}

async function save() {
  const { valid } = await form.value.validate()
  if (!valid) return
  loading.value = true
  try {
    await auth.updateProfile({ ...data })
    data.current_password = ''
    form.value.resetValidation()
    dialog.show('Данные сохранены.')
  } catch (e) {
    const err = parseApiError(e)
    if (Object.keys(err.fields).length) errors.value = err.fields
    else dialog.show(err.detail, 'Ошибка')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <v-container max-width="720">
    <h1 class="text-h4 mb-4">Учётная запись</h1>
    <v-card>
      <v-tabs v-model="tab" color="primary">
        <v-tab value="profile">Личные данные</v-tab>
        <v-tab value="security">Безопасность</v-tab>
      </v-tabs>
      <v-divider />
      <v-tabs-window v-model="tab">
        <v-tabs-window-item value="profile">
          <v-form ref="form" @submit.prevent="save">
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
                v-model="data.current_password"
                label="Текущий пароль"
                autocomplete="current-password"
                hint="Нужен для подтверждения изменений"
                :rules="[rules.required]"
                :error-messages="errors.current_password"
                @update:model-value="clearError('current_password')"
              />
            </v-card-text>
            <v-card-actions class="px-4 pb-4">
              <v-spacer />
              <v-btn color="primary" variant="flat" type="submit" :loading="loading">
                Сохранить
              </v-btn>
            </v-card-actions>
          </v-form>
        </v-tabs-window-item>

        <v-tabs-window-item value="security">
          <v-list lines="two">
            <v-list-item
              prepend-icon="mdi-two-factor-authentication"
              title="Двухфакторная аутентификация"
            >
              <template #subtitle>
                <span v-if="auth.user?.totp_enabled">Включена</span>
                <span v-else>Выключена</span>
                <span v-if="auth.user?.requires_2fa"> · обязательна для вашей роли</span>
              </template>
              <template #append>
                <v-btn
                  v-if="!auth.user?.totp_enabled"
                  color="primary"
                  variant="tonal"
                  to="/2fa/setup"
                >
                  Включить 2FA
                </v-btn>
                <v-chip v-else color="success" variant="tonal" prepend-icon="mdi-check">
                  Включена
                </v-chip>
              </template>
            </v-list-item>
            <v-list-item
              prepend-icon="mdi-lock-reset"
              title="Пароль"
              subtitle="Остальные сеансы будут завершены"
            >
              <template #append>
                <v-btn variant="tonal" @click="passwordOpen = true">Изменить пароль</v-btn>
              </template>
            </v-list-item>
            <v-list-item
              prepend-icon="mdi-account-remove"
              title="Удаление учётной записи"
              subtitle="Действие необратимо"
            >
              <template #append>
                <v-btn color="error" variant="tonal" @click="deleteOpen = true">
                  Удалить учётную запись
                </v-btn>
              </template>
            </v-list-item>
          </v-list>
        </v-tabs-window-item>
      </v-tabs-window>
    </v-card>
    <ChangePasswordDialog v-model="passwordOpen" />
    <DeleteAccountDialog v-model="deleteOpen" />
  </v-container>
</template>
