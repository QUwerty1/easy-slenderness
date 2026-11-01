<script setup lang="ts">
import type { Course, EnrollResult } from '~/types/course'

definePageMeta({ middleware: 'course-role', roles: ['user', 'participant'] })

// Форма согласия перед оплатой платного курса
const route = useRoute()
const api = useCourseApi()
const dialog = useSystemDialog()
const id = Number(route.params.id)
const { data: course } = useAsyncData(`course-${id}`, () => api<Course>(`courses/${id}/`))

const consents = reactive({ offer: false, refund_policy: false, pd: false })
const error = ref('')
const loading = ref(false)

async function toPayment() {
  if (!consents.offer || !consents.refund_policy || !consents.pd) {
    error.value = 'Для оплаты нужно отметить все три согласия'
    return
  }
  loading.value = true
  try {
    const result = await api<EnrollResult>(`courses/${id}/enroll/`, {
      method: 'POST',
      body: consents,
    })
    if (result.payment_url) window.location.href = result.payment_url
  } catch (e) {
    await dialog.show(parseApiError(e).detail, 'Запись невозможна')
    await navigateTo('/courses')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <v-container max-width="640">
    <v-card
      title="Согласие с условиями"
      :subtitle="course ? `Курс «${course.name}», ${formatMoney(course.price)}` : ''"
    >
      <v-card-text>
        <v-checkbox v-model="consents.offer" label="Принимаю договор оферты" hide-details />
        <v-checkbox
          v-model="consents.refund_policy"
          label="Ознакомлен(а) с политикой возврата средств"
          hide-details
        />
        <v-checkbox
          v-model="consents.pd"
          label="Даю согласие на обработку персональных данных"
          hide-details
        />
        <v-alert v-if="error" type="error" variant="tonal" density="compact" class="mt-3">
          {{ error }}
        </v-alert>
      </v-card-text>
      <v-card-actions class="px-4 pb-4">
        <v-btn :to="`/courses/${id}`">Отмена</v-btn>
        <v-spacer />
        <v-btn color="primary" variant="flat" :loading="loading" @click="toPayment">
          Перейти к оплате
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-container>
</template>
