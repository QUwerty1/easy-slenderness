<script setup lang="ts">
import type { Course, EnrollResult } from '~/types/course'

// Карточка курса: описание и кнопка «Записаться»
const route = useRoute()
const auth = useAuthStore()
const api = useCourseApi()
const dialog = useSystemDialog()
const id = Number(route.params.id)
const loading = ref(false)

const { data: course, error } = useAsyncData(`course-${id}`, () => api<Course>(`courses/${id}/`))
const canEnroll = computed(() => isLearner(auth.user?.role) && course.value?.state === 'open')

async function enroll() {
  if (!course.value) return
  if (course.value.status === 'paid') return navigateTo(`/courses/${id}/consent`)
  loading.value = true
  try {
    await api<EnrollResult>(`courses/${id}/enroll/`, { method: 'POST' })
    await dialog.show('Вы успешно записаны на курс.')
    await navigateTo('/my-courses')
  } catch (e) {
    await dialog.show(parseApiError(e).detail, 'Запись невозможна')
    await navigateTo('/courses')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <v-container max-width="720">
    <v-btn variant="text" prepend-icon="mdi-arrow-left" to="/courses" class="mb-2">
      К списку курсов
    </v-btn>
    <v-alert v-if="error" type="error" variant="tonal">{{ parseApiError(error).detail }}</v-alert>
    <v-card v-else-if="course" :title="course.name">
      <v-card-text>
        <p class="mb-2">
          <b>Даты проведения:</b> {{ formatDateTime(course.start_at) }} –
          {{ formatDateTime(course.end_at) }}
          ({{ course.status === 'paid' ? '4 недели' : '1 неделя' }})
        </p>
        <p class="mb-2"><b>Статус:</b> {{ course.status_display }}</p>
        <p class="mb-2">
          <b>Цена:</b> {{ course.status === 'paid' ? formatMoney(course.price) : 'Бесплатно' }}
        </p>
        <p>
          <b>Состояние:</b>
          <v-chip size="small" :color="stateColor[course.state]">{{ course.state_display }}</v-chip>
        </p>
      </v-card-text>
      <v-card-actions v-if="isLearner(auth.user?.role)" class="px-4 pb-4">
        <v-btn
          color="primary"
          variant="flat"
          :disabled="!canEnroll || course.is_participant"
          :loading="loading"
          @click="enroll"
        >
          Записаться
        </v-btn>
        <span v-if="course.is_participant" class="text-medium-emphasis ml-2">
          Вы уже записаны на этот курс
        </span>
      </v-card-actions>
    </v-card>
  </v-container>
</template>
