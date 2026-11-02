<script setup lang="ts">
import type { Course } from '~/types/course'

// Страница курса: меню разделов слева, «Информация о курсе» по умолчанию
const route = useRoute()
const auth = useAuthStore()
const api = useCourseApi()
const id = Number(route.params.id)

const { data: course, error } = useAsyncData(`course-${id}`, () => api<Course>(`courses/${id}/`))
const isAdmin = computed(() => auth.user?.role === 'admin')
const archived = computed(() => course.value?.state === 'archived')
const back = computed(() =>
  isAdmin.value
    ? { to: '/manage', title: 'Управление курсами' }
    : { to: '/my-courses', title: 'Мои курсы' },
)
</script>

<template>
  <v-container>
    <v-btn variant="text" prepend-icon="mdi-arrow-left" :to="back.to" class="mb-2">
      {{ back.title }}
    </v-btn>
    <v-alert v-if="error" type="error" variant="tonal">{{ parseApiError(error).detail }}</v-alert>
    <template v-else-if="course">
      <h1 class="text-h4 mb-3">{{ course.name }}</h1>
      <v-alert v-if="archived" type="info" variant="tonal" class="mb-4">
        Архивный курс — режим «только чтение». Редактирование, изменение состава участников и
        сообщения в чат недоступны.
      </v-alert>
      <v-row>
        <v-col cols="12" md="3">
          <v-card>
            <v-list color="primary" nav>
              <v-list-item active prepend-icon="mdi-information" title="Информация о курсе" />
              <v-list-item
                v-if="!isAdmin"
                prepend-icon="mdi-notebook-edit"
                title="Домашние задания"
                :to="`/courses/${id}/homework`"
              />
            </v-list>
          </v-card>
        </v-col>
        <v-col cols="12" md="9">
          <v-card title="Информация о курсе">
            <v-card-text>
              <p class="mb-2"><b>Статус:</b> {{ course.status_display }}</p>
              <p class="mb-2">
                <b>Цена:</b>
                {{ course.status === 'paid' ? formatMoney(course.price) : 'Бесплатно' }}
              </p>
              <p class="mb-2"><b>Начало:</b> {{ formatDateTime(course.start_at) }}</p>
              <p class="mb-2"><b>Окончание:</b> {{ formatDateTime(course.end_at) }}</p>
              <p>
                <b>Состояние:</b>
                <v-chip size="small" :color="stateColor[course.state]">
                  {{ course.state_display }}
                </v-chip>
              </p>
            </v-card-text>
            <v-card-actions class="px-4 pb-4">
              <v-btn
                variant="tonal"
                prepend-icon="mdi-account-group"
                :to="isAdmin ? `/manage/${id}/participants` : `/courses/${id}/participants`"
              >
                Участники
              </v-btn>
            </v-card-actions>
          </v-card>
        </v-col>
      </v-row>
    </template>
  </v-container>
</template>
