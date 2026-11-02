<script setup lang="ts">
import type { HomeworkList, HomeworkListParticipant } from '~/types/homework'

const route = useRoute()
const api = useCourseApi()
const id = Number(route.params.id)

const { data, error } = useAsyncData(`homework-list-${id}`, () =>
  api<HomeworkList>(`courses/${id}/homework/reports/`),
)

const statusColor = (status: string) => {
  const colors: Record<string, string> = {
    filling: 'info',
    review: 'warning',
    reviewed: 'success',
    unavailable: 'grey',
    not_completed: 'error',
  }
  return colors[status] ?? 'grey'
}

function openDay(day: string, participantId?: number) {
  const query = participantId ? `?participant_id=${participantId}` : ''
  return navigateTo(`/courses/${id}/homework/reports/${day}${query}`)
}

function formatDay(day: string) {
  return new Date(`${day}T12:00:00`).toLocaleDateString('ru-RU', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })
}

function tutorCellColor(cell: NonNullable<HomeworkListParticipant['cells'][number]>) {
  // Не выполнено — всегда красный цвет.
  if (
    cell.status === 'not_completed' ||
    (cell.status === 'reviewed' && cell.is_completed === false)
  ) {
    return 'error'
  }

  // Проверенное и выполненное задание — зелёный.
  if (cell.status === 'reviewed' && cell.is_completed === true) {
    return 'success'
  }

  // Отчёт ожидает проверки.
  return statusColor(cell.status)
}

function tutorCellText(cell: NonNullable<HomeworkListParticipant['cells'][number]>) {
  const meals = `${cell.meal_count} приёмов`

  if (cell.status === 'reviewed') {
    return `${meals} · ${cell.is_completed ? 'Выполнено' : 'Не выполнено'}`
  }

  if (cell.status === 'not_completed') {
    return `${meals} · Не выполнено`
  }

  return `${meals} · ${cell.status_display}`
}
</script>

<template>
  <v-container>
    <v-btn variant="text" prepend-icon="mdi-arrow-left" :to="`/courses/${id}/view`" class="mb-3">
      К странице курса
    </v-btn>
    <h1 class="text-h4 mb-4">Домашние задания</h1>

    <v-alert v-if="error" type="error" variant="tonal" class="mb-4">
      {{ parseApiError(error).detail }}
    </v-alert>

    <template v-if="data && data.mode === 'participant'">
      <p class="text-medium-emphasis mb-4">
        Ежедневные отчеты о приемах пищи за курс «{{ data.course_name }}». Выберите дату, чтобы
        заполнить отчет или посмотреть его результат.
      </p>

      <v-card>
        <v-list lines="two">
          <v-list-item
            v-for="day in data.days"
            :key="day.date"
            :title="formatDay(day.date)"
            :subtitle="day.is_created ? `${day.meal_count} прием(ов) пищи` : day.status_display"
            :disabled="day.status === 'not_completed'"
            @click="openDay(day.date)"
          >
            <template #prepend>
              <v-avatar color="primary" variant="tonal">
                <v-icon icon="mdi-calendar" />
              </v-avatar>
            </template>
            <template #append>
              <div class="d-flex align-center ga-2">
                <v-chip size="small" :color="statusColor(day.status)" variant="tonal">
                  {{ day.status_display }}
                </v-chip>
                <v-chip
                  v-if="day.is_completed !== null"
                  size="small"
                  :color="day.is_completed ? 'success' : 'error'"
                  variant="outlined"
                >
                  {{ day.is_completed ? 'Выполнено' : 'Не выполнено' }}
                </v-chip>
                <v-icon v-if="day.status !== 'not_completed'" icon="mdi-chevron-right" />
              </div>
            </template>
          </v-list-item>
        </v-list>
      </v-card>
    </template>

    <template v-else-if="data && data.mode === 'tutor'">
      <p class="text-medium-emphasis mb-4">
        Отчеты участников курса «{{ data.course_name }}». Нажмите на отчет со статусом
        «Проверяется», чтобы открыть его и выполнить проверку.
      </p>
      <v-table density="comfortable" class="border rounded tutor-table">
        <thead>
          <tr>
            <th class="text-left">Участник курса</th>
            <th v-for="day in data.dates" :key="day" class="text-center">
              {{ formatDay(day) }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="participant in data.participants" :key="participant.participant_id">
            <td class="font-weight-medium">{{ participant.participant_name }}</td>
            <td
              v-for="cell in participant.cells"
              :key="cell?.date ?? `${participant.participant_id}-empty`"
              class="text-center"
            >
              <v-btn
                v-if="cell"
                size="small"
                variant="tonal"
                :color="tutorCellColor(cell)"
                :disabled="!cell.report_id"
                @click="cell.report_id && openDay(cell.date, participant.participant_id)"
              >
                {{ tutorCellText(cell) }}
              </v-btn>

              <v-btn v-else size="small" variant="tonal" color="error" disabled>
                0 приёмов · Не выполнено
              </v-btn>
            </td>
          </tr>
        </tbody>
      </v-table>
    </template>
  </v-container>
</template>
<style scoped>
.tutor-table :deep(th:first-child),
.tutor-table :deep(td:first-child) {
  position: sticky;
  left: 0;
  min-width: 200px;
  background-color: white;
}

/* Заголовок первого столбца */
.tutor-table :deep(thead th:first-child) {
  z-index: 3;
}

/* Ячейки участников */
.tutor-table :deep(tbody td:first-child) {
  z-index: 2;
}
</style>
