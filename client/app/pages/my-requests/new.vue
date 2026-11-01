<script setup lang="ts">
import type { MyRequest, Refusable } from '~/types/course'

definePageMeta({ middleware: 'course-role', roles: ['user', 'participant'] })

// Форма заявки на исключение из курса
const api = useCourseApi()
const dialog = useSystemDialog()
const { data: items, pending } = useAsyncData('requests-refusable', () =>
  api<Refusable[]>('requests/refusable/'),
)
const participantId = ref<number>()
const reason = ref('')
const policyAck = ref(false)
const errors = ref<Record<string, string[]>>({})
const loading = ref(false)

watch(
  items,
  (list) => {
    if (list?.length && participantId.value === undefined) participantId.value = list[0]!.id
  },
  { immediate: true },
)

const selected = computed(() => items.value?.find((item) => item.id === participantId.value))
const isPaid = computed(() => selected.value?.course.status === 'paid')

async function submit() {
  if (!selected.value) return
  loading.value = true
  errors.value = {}
  try {
    const result = await api<MyRequest>('requests/my/', {
      method: 'POST',
      body: {
        participant_id: selected.value.id,
        reason: reason.value,
        policy_ack: policyAck.value,
      },
    })
    await dialog.show(
      result.status === 'done'
        ? 'Заявка выполнена: вы исключены из бесплатного курса.'
        : 'Заявка зарегистрирована и передана администратору.',
    )
    await navigateTo('/my-requests')
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
  <v-container max-width="640">
    <v-btn variant="text" prepend-icon="mdi-arrow-left" to="/my-requests" class="mb-2">
      Мои заявки
    </v-btn>
    <v-card title="Заявка на исключение из курса">
      <v-progress-linear v-if="pending" indeterminate />
      <v-card-text v-else-if="!items?.length">
        Нет курсов, по которым можно подать заявку: вы не участвуете в курсах, курсы уже архивные
        или по ним уже есть заявки на рассмотрении.
      </v-card-text>
      <template v-else>
        <v-card-text>
          <v-select
            v-model="participantId"
            label="Курс"
            :items="items"
            item-title="course.name"
            item-value="id"
          />
          <p v-if="isPaid" class="mb-3">
            <b>Оплаченная сумма:</b> {{ formatMoney(selected!.paid_amount) }}
          </p>
          <v-alert v-else type="info" variant="tonal" density="compact" class="mb-3">
            Курс бесплатный: вы будете исключены сразу после отправки заявки.
          </v-alert>
          <v-textarea v-model="reason" label="Причина отказа (по желанию)" rows="3" />
          <v-checkbox
            v-if="isPaid"
            v-model="policyAck"
            label="Ознакомлен(а) с политикой возврата средств"
            :error-messages="errors.policy_ack"
            @update:model-value="errors.policy_ack = []"
          />
        </v-card-text>
        <v-card-actions class="px-4 pb-4">
          <v-btn to="/my-requests">Отмена</v-btn>
          <v-spacer />
          <v-btn color="primary" variant="flat" :loading="loading" @click="submit">
            Отправить заявку
          </v-btn>
        </v-card-actions>
      </template>
    </v-card>
  </v-container>
</template>
