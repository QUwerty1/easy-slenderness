<script setup lang="ts">
const open = defineModel<boolean>({ required: true })

const auth = useAuthStore()
const dialog = useSystemDialog()
const form = ref()
const password = ref('')
const errors = ref<string[]>([])
const reasons = ref<string[]>([])
const loading = ref(false)

watch(open, (value) => {
  if (!value) return
  password.value = ''
  errors.value = []
  reasons.value = []
})

async function submit() {
  const { valid } = await form.value.validate()
  if (!valid) return
  loading.value = true
  try {
    await auth.deleteAccount(password.value)
    open.value = false
    await navigateTo('/login')
    dialog.show('Учётная запись удалена.')
  } catch (e) {
    const err = parseApiError(e)
    if (err.reasons) reasons.value = err.reasons
    else if (err.fields.password) errors.value = err.fields.password
    else dialog.show(err.detail, 'Ошибка')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <v-dialog v-model="open" max-width="480" persistent>
    <v-card title="Удаление учётной записи">
      <v-form ref="form" @submit.prevent="submit">
        <v-card-text>
          <v-alert type="warning" variant="tonal" class="mb-4">
            Удаление необратимо. Вы потеряете доступ к курсам и материалам, все сеансы будут
            завершены, а персональные данные будут уничтожены или обезличены.
          </v-alert>
          <v-alert v-if="reasons.length" type="error" variant="tonal" class="mb-4">
            <div class="mb-1">Учётную запись нельзя удалить:</div>
            <ul class="pl-4">
              <li v-for="reason in reasons" :key="reason">{{ reason }}</li>
            </ul>
          </v-alert>
          <PasswordField
            v-model="password"
            label="Пароль"
            autocomplete="current-password"
            :rules="[rules.required]"
            :error-messages="errors"
            @update:model-value="errors = []"
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn :disabled="loading" @click="open = false">Отмена</v-btn>
          <v-btn color="error" variant="flat" type="submit" :loading="loading">Удалить</v-btn>
        </v-card-actions>
      </v-form>
    </v-card>
  </v-dialog>
</template>
