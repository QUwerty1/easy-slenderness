<script setup lang="ts">
import type { RequestListItem, RequestStatus } from '~/types/course'

definePageMeta({ middleware: 'course-role', roles: ['admin'] })

// Просмотр списка заявок на исключение (зарегистрированные — первыми)
const api = useCourseApi()
const status = ref<RequestStatus | null>(null)
const statuses = [
  { title: 'Зарегистрированные', value: 'registered' },
  { title: 'Выполненные', value: 'done' },
  { title: 'Отклонённые', value: 'rejected' },
]
const { data: requests, pending } = useAsyncData(
  'requests-all',
  () =>
    api<RequestListItem[]>('requests/', { query: status.value ? { status: status.value } : {} }),
  { watch: [status] },
)
</script>

<template>
  <v-container>
    <div class="d-flex flex-wrap align-center ga-3 mb-4">
      <h1 class="text-h4">Заявки на исключение</h1>
      <v-spacer />
      <v-select
        v-model="status"
        :items="statuses"
        label="Статус"
        clearable
        density="compact"
        hide-details
        max-width="260"
      />
    </div>
    <v-progress-linear v-if="pending" indeterminate />
    <v-card v-else>
      <v-table>
        <thead>
          <tr>
            <th>Участник</th>
            <th>Курс</th>
            <th>Основание</th>
            <th>Дата и время подачи</th>
            <th>Статус</th>
            <th />
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in requests" :key="r.id">
            <td>{{ r.full_name }}</td>
            <td>{{ r.course_name }}</td>
            <td>{{ r.basis_display }}</td>
            <td>{{ formatDateTime(r.created_at) }}</td>
            <td>
              <v-chip size="small" :color="requestColor[r.status]">{{ r.status_display }}</v-chip>
            </td>
            <td class="text-right">
              <v-btn
                size="small"
                :color="r.status === 'registered' ? 'primary' : undefined"
                :variant="r.status === 'registered' ? 'flat' : 'tonal'"
                :to="`/requests/${r.id}`"
              >
                {{ r.status === 'registered' ? 'Обработать' : 'Открыть' }}
              </v-btn>
            </td>
          </tr>
          <tr v-if="!requests?.length">
            <td colspan="6" class="text-medium-emphasis">Заявок нет</td>
          </tr>
        </tbody>
      </v-table>
    </v-card>
  </v-container>
</template>
