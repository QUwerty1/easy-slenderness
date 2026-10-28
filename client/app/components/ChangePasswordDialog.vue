<script setup lang="ts">
const open = defineModel<boolean>({ required: true })

const auth = useAuthStore()
const dialog = useSystemDialog()
const form = ref()
const currentPassword = ref('')
const newPassword = ref('')
const errors = ref<Record<string, string[]>>({})
const loading = ref(false)

watch(open, (value) => {
  if (!value) return
  currentPassword.value = ''
  newPassword.value = ''
  errors.value = {}
})

async function submit() {
  const { valid } = await form.value.validate()
  if (!valid) return
  loading.value = true
  try {
    await auth.changePassword(currentPassword.value, newPassword.value)
    open.value = false
    dialog.show('Пароль изменён. Сеансы на других устройствах завершены.')
  } catch (e) {
    const err = parseApiError(e)
    errors.value = err.fields
    if (!Object.keys(err.fields).length) dialog.show(err.detail, 'Ошибка')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <v-dialog v-model="open" max-width="440" persistent>
    <v-card title="Изменение пароля">
      <v-form ref="form" @submit.prevent="submit">
        <v-card-text>
          <PasswordField
            v-model="currentPassword"
            label="Текущий пароль"
            autocomplete="current-password"
            :rules="[rules.required]"
            :error-messages="errors.current_password"
            @update:model-value="errors.current_password = []"
          />
          <PasswordField
            v-model="newPassword"
            label="Новый пароль"
            autocomplete="new-password"
            :rules="[rules.required, rules.password]"
            :error-messages="errors.new_password"
            @update:model-value="errors.new_password = []"
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn :disabled="loading" @click="open = false">Отмена</v-btn>
          <v-btn color="primary" variant="flat" type="submit" :loading="loading">Сохранить</v-btn>
        </v-card-actions>
      </v-form>
    </v-card>
  </v-dialog>
</template>
