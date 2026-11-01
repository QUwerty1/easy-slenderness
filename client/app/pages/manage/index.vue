<script setup lang="ts">
import type { Course, CourseState } from '~/types/course'

definePageMeta({ middleware: 'course-role', roles: ['admin'] })

// Получить список всех курсов (с фильтром по состоянию)
const api = useCourseApi()
const state = ref<CourseState | null>(null)
const states = [
  { title: 'Открыт для записи', value: 'open' },
  { title: 'Идёт', value: 'running' },
  { title: 'Архивный', value: 'archived' },
]
const { data: courses, pending } = useAsyncData(
  'courses-all',
  () => api<Course[]>('courses/', { query: state.value ? { state: state.value } : {} }),
  { watch: [state] },
)
</script>

<template>
  <v-container>
    <div class="d-flex flex-wrap align-center ga-3 mb-4">
      <h1 class="text-h4">Управление курсами</h1>
      <v-spacer />
      <v-select
        v-model="state"
        :items="states"
        label="Состояние"
        clearable
        density="compact"
        hide-details
        max-width="240"
      />
      <v-btn color="primary" variant="flat" prepend-icon="mdi-plus" to="/manage/new">
        Создать курс
      </v-btn>
    </div>
    <v-progress-linear v-if="pending" indeterminate />
    <v-card v-else>
      <v-table>
        <thead>
          <tr>
            <th>Название</th>
            <th>Статус</th>
            <th>Цена</th>
            <th>Начало</th>
            <th>Окончание</th>
            <th>Состояние</th>
            <th />
          </tr>
        </thead>
        <tbody>
          <tr v-for="course in courses" :key="course.id">
            <td>{{ course.name }}</td>
            <td>{{ course.status_display }}</td>
            <td>{{ course.status === 'paid' ? formatMoney(course.price) : 'Бесплатно' }}</td>
            <td>{{ formatDateTime(course.start_at) }}</td>
            <td>{{ formatDateTime(course.end_at) }}</td>
            <td>
              <v-chip size="small" :color="stateColor[course.state]">
                {{ course.state_display }}
              </v-chip>
            </td>
            <td class="text-right text-no-wrap">
              <v-btn
                size="small"
                variant="text"
                :disabled="!course.can_edit"
                :to="`/manage/${course.id}/edit`"
              >
                Редактировать
              </v-btn>
              <v-btn size="small" variant="text" :to="`/courses/${course.id}/view`">
                Открыть курс
              </v-btn>
              <v-btn size="small" variant="tonal" :to="`/manage/${course.id}/participants`">
                Участники
              </v-btn>
            </td>
          </tr>
          <tr v-if="!courses?.length">
            <td colspan="7" class="text-medium-emphasis">Курсов нет</td>
          </tr>
        </tbody>
      </v-table>
    </v-card>
  </v-container>
</template>
