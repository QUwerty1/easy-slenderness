<script setup lang="ts">
import type { MyRequest } from '~/types/course'

definePageMeta({ middleware: 'course-role', roles: ['user', 'participant'] })

// Просмотр своих заявок
const api = useCourseApi()
const { data: requests, pending } = useAsyncData('requests-my', () =>
  api<MyRequest[]>('requests/my/'),
)
</script>

<template>
  <v-container>
    <div class="d-flex flex-wrap align-center ga-3 mb-4">
      <h1 class="text-h4">Мои заявки</h1>
      <v-spacer />
      <v-btn color="primary" variant="flat" prepend-icon="mdi-plus" to="/my-requests/new">
        Подать заявку на исключение
      </v-btn>
    </div>
    <v-progress-linear v-if="pending" indeterminate />
    <v-alert v-else-if="!requests?.length" type="info" variant="tonal">Заявок пока нет</v-alert>
    <v-card v-else>
      <v-table>
        <thead>
          <tr>
            <th>Курс</th>
            <th>Дата и время подачи</th>
            <th>Статус</th>
            <th>Сумма возврата</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in requests" :key="r.id">
            <td>{{ r.course_name }}</td>
            <td>{{ formatDateTime(r.created_at) }}</td>
            <td>
              <v-chip size="small" :color="requestColor[r.status]">{{ r.status_display }}</v-chip>
            </td>
            <td>{{ r.refund_amount ? formatMoney(r.refund_amount) : '—' }}</td>
          </tr>
        </tbody>
      </v-table>
    </v-card>
    <p class="text-medium-emphasis mt-3">
      Пока заявка на рассмотрении, повторно подать заявку по этому курсу нельзя. После отклонения
      можно подать новую.
    </p>
  </v-container>
</template>
