<script setup lang="ts">
import type { AdminParticipant, Course } from '~/types/course'

definePageMeta({ middleware: 'course-role', roles: ['admin'] })

// Управление участниками курса: список с контактами, ручное зачисление, исключение
const route = useRoute()
const api = useCourseApi()
const dialog = useSystemDialog()
const id = Number(route.params.id)
const filters = ref({ full_name: '', phone: '', email: '', status: '' })
const query = computed(() =>
  Object.fromEntries(Object.entries(filters.value).filter(([, value]) => value)),
)

const { data: course } = useAsyncData(`course-${id}`, () => api<Course>(`courses/${id}/`))
const { data: participants, refresh } = useAsyncData(
  `participants-admin-${id}`,
  () => api<AdminParticipant[]>(`courses/${id}/participants/`, { query: query.value }),
  { watch: [query] },
)

const canAdd = computed(() => course.value?.state === 'open' && course.value.status === 'paid')
const addHint = computed(() => {
  if (!course.value) return ''
  if (course.value.state === 'archived') return 'Архивный курс: состав не меняется'
  if (course.value.state !== 'open') return 'Курс уже начался: зачисление закрыто'
  if (course.value.status !== 'paid') return 'Ручное зачисление доступно только на платный курс'
  return ''
})

// Форма исключения
const excluding = ref<AdminParticipant | null>(null)
const loading = ref(false)

async function exclude() {
  if (!excluding.value) return
  loading.value = true
  try {
    const result = await api<AdminParticipant & { request_created: boolean }>(
      `participants/${excluding.value.id}/exclude/`,
      { method: 'POST' },
    )
    excluding.value = null
    await refresh()
    dialog.show(
      result.request_created
        ? 'Участник исключён. Заявка на возврат средств зарегистрирована автоматически.'
        : 'Участник исключён.',
    )
  } catch (e) {
    dialog.show(parseApiError(e).detail, 'Ошибка')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <v-container>
    <v-btn variant="text" prepend-icon="mdi-arrow-left" to="/manage" class="mb-2">
      Управление курсами
    </v-btn>
    <h1 class="text-h4">Управление участниками</h1>
    <p v-if="course" class="text-medium-emphasis mb-4">
      {{ course.name }} ·
      <v-chip size="small" :color="stateColor[course.state]">{{ course.state_display }}</v-chip>
    </p>
    <div class="d-flex align-center ga-3 mb-4">
      <v-btn
        color="primary"
        variant="flat"
        prepend-icon="mdi-account-plus"
        :disabled="!canAdd"
        :to="`/manage/${id}/enroll`"
      >
        Добавить участника
      </v-btn>
      <span class="text-medium-emphasis">{{ addHint }}</span>
    </div>
    <ParticipantFilters v-model="filters" with-status />
    <v-card>
      <v-table>
        <thead>
          <tr>
            <th>ФИО</th>
            <th>Телефон</th>
            <th>Email</th>
            <th>Дата зачисления</th>
            <th>Способ</th>
            <th>Статус</th>
            <th />
          </tr>
        </thead>
        <tbody>
          <tr v-for="p in participants" :key="p.id">
            <td>{{ p.full_name }}</td>
            <td>{{ p.phone }}</td>
            <td>{{ p.email }}</td>
            <td>{{ formatDate(p.enrolled_at) }}</td>
            <td>{{ p.method_display }}</td>
            <td>
              {{ p.status_display }}
              <span v-if="p.exclusion_reason" class="text-medium-emphasis">
                ({{ p.exclusion_reason_display.toLowerCase() }})
              </span>
            </td>
            <td class="text-right">
              <v-btn
                v-if="p.status === 'active' && course?.state !== 'archived'"
                size="small"
                color="error"
                variant="tonal"
                @click="excluding = p"
              >
                Исключить
              </v-btn>
            </td>
          </tr>
          <tr v-if="!participants?.length">
            <td colspan="7" class="text-medium-emphasis">Участники не найдены</td>
          </tr>
        </tbody>
      </v-table>
    </v-card>

    <v-dialog :model-value="!!excluding" max-width="520" @update:model-value="excluding = null">
      <v-card v-if="excluding" title="Исключение участника">
        <v-card-text>
          <p class="mb-2"><b>Участник:</b> {{ excluding.full_name }}</p>
          <p class="mb-2">
            <b>Курс:</b> {{ course?.name }} ({{ course?.status_display.toLowerCase() }})
          </p>
          <p class="mb-3"><b>Причина:</b> нарушение правил</p>
          <v-alert type="info" variant="tonal" density="compact">
            Форма служит только для исключения нарушителей. По заявке участник исключается при её
            выполнении.
            <template v-if="course?.status === 'paid'">
              {{
                excluding.has_registered_request
                  ? 'По участию уже есть заявка на рассмотрении: новая заявка не создаётся, возврат будет выполнен по ней.'
                  : 'Заявка на возврат средств зарегистрируется автоматически.'
              }}
            </template>
          </v-alert>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn :disabled="loading" @click="excluding = null">Отмена</v-btn>
          <v-btn color="error" variant="flat" :loading="loading" @click="exclude">Исключить</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>
