<script setup lang="ts">
import type { Course } from '~/types/course'

definePageMeta({ middleware: 'course-role', roles: ['user', 'participant', 'tutor'] })

// Получить список моих курсов (тьютору — все курсы платформы)
const auth = useAuthStore()
const api = useCourseApi()
const { data: courses, pending } = useAsyncData('courses-my', () => api<Course[]>('courses/my/'))
</script>

<template>
  <v-container>
    <h1 class="text-h4 mb-1">Мои курсы</h1>
    <p v-if="auth.user?.role === 'tutor'" class="text-medium-emphasis mb-4">
      Тьютор работает со всеми курсами платформы.
    </p>
    <v-progress-linear v-if="pending" indeterminate />
    <v-alert v-else-if="!courses?.length" type="info" variant="tonal" class="mt-3">
      Моих курсов пока нет
    </v-alert>
    <v-card v-else class="mt-3">
      <v-table>
        <thead>
          <tr>
            <th>Курс</th>
            <th>Даты</th>
            <th>Состояние</th>
            <th />
          </tr>
        </thead>
        <tbody>
          <tr v-for="course in courses" :key="course.id">
            <td>{{ course.name }}</td>
            <td>{{ formatDate(course.start_at) }} – {{ formatDate(course.end_at) }}</td>
            <td>
              <v-chip size="small" :color="stateColor[course.state]">
                {{ course.state_display }}
              </v-chip>
            </td>
            <td class="text-right">
              <v-btn size="small" color="primary" variant="flat" :to="`/courses/${course.id}/view`">
                Открыть курс
              </v-btn>
              <v-btn
                size="small"
                variant="tonal"
                class="ml-2"
                :to="`/courses/${course.id}/participants`"
              >
                Участники
              </v-btn>
            </td>
          </tr>
        </tbody>
      </v-table>
    </v-card>
  </v-container>
</template>
