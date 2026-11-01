<script setup lang="ts">
import type { Course } from '~/types/course'

// Получить список курсов: курсы, открытые для записи
const auth = useAuthStore()
const api = useCourseApi()
const { data: courses, pending } = useAsyncData('courses-available', () =>
  api<Course[]>('courses/available/'),
)
const title = computed(() =>
  isLearner(auth.user?.role) ? 'Записаться на курс' : 'Курсы, доступные для записи',
)
</script>

<template>
  <v-container>
    <h1 class="text-h4 mb-4">{{ title }}</h1>
    <v-progress-linear v-if="pending" indeterminate />
    <v-alert v-else-if="!courses?.length" type="info" variant="tonal">
      Доступных курсов пока нет
    </v-alert>
    <v-card v-else>
      <v-table>
        <thead>
          <tr>
            <th>Название</th>
            <th>Даты проведения</th>
            <th>Статус</th>
            <th>Цена</th>
            <th />
          </tr>
        </thead>
        <tbody>
          <tr v-for="course in courses" :key="course.id">
            <td>{{ course.name }}</td>
            <td>{{ formatDate(course.start_at) }} – {{ formatDate(course.end_at) }}</td>
            <td>{{ course.status_display }}</td>
            <td>{{ course.status === 'paid' ? formatMoney(course.price) : 'Бесплатно' }}</td>
            <td class="text-right">
              <v-btn size="small" variant="tonal" :to="`/courses/${course.id}`">Подробнее</v-btn>
            </td>
          </tr>
        </tbody>
      </v-table>
    </v-card>
  </v-container>
</template>
