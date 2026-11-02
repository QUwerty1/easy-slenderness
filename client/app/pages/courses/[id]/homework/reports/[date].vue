<script setup lang="ts">
import type { HomeworkReport } from '~/types/homework'

const route = useRoute()
const auth = useAuthStore()
const api = useCourseApi()
const dialog = useSystemDialog()
const id = Number(route.params.id)
const day = computed(() => String(route.params.date))
const participantId = computed(() => String(route.query.participant_id ?? ''))
const isTutor = computed(() => auth.user?.role === 'tutor')

const {
  data: report,
  error,
  refresh,
} = useAsyncData(
  `homework-report-${id}-${day.value}-${participantId.value}`,
  () =>
    api<HomeworkReport>(
      `courses/${id}/homework/reports/${day.value}/${participantId.value ? `?participant_id=${participantId.value}` : ''}`,
    ),
  { watch: [day, participantId] },
)

const photos = ref<File[]>([])
const waterDrank = ref<boolean | null>(null)
const breathingPractice = ref<boolean | null>(null)
const feeling = ref<'hunger' | 'appetite' | null>(null)
const mealLoading = ref(false)
const participantComment = ref('')
const tutorComment = ref('')
const completed = ref<boolean | null>(null)
const reviewLoading = ref(false)
const editDialog = ref(false)
const editingMeal = ref<number | null>(null)
const editPhotos = ref<File[]>([])
const editWater = ref(false)
const editBreathing = ref(false)
const editFeeling = ref<'hunger' | 'appetite'>('hunger')

watch(
  report,
  (value) => {
    if (!value) return
    participantComment.value = value.participant_comment ?? ''
    tutorComment.value = value.tutor_comment ?? ''
    completed.value = value.is_completed
  },
  { immediate: true },
)

const canEdit = computed(
  () => !isTutor.value && report.value?.available && report.value?.status === 'filling',
)

function dateLabel(value: string) {
  return new Date(`${value}T12:00:00`).toLocaleDateString('ru-RU', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })
}

async function addMeal() {
  if (
    !photos.value.length ||
    waterDrank.value === null ||
    breathingPractice.value === null ||
    !feeling.value
  ) {
    await dialog.show('Прикрепите фотографию и заполните все отметки о приеме пищи.')
    return
  }
  const body = new FormData()
  body.append('water_drank', String(waterDrank.value))
  body.append('breathing_practice', String(breathingPractice.value))
  body.append('feeling', feeling.value)
  for (const photo of photos.value) body.append('photos', photo)
  mealLoading.value = true
  try {
    await api(`courses/${id}/homework/reports/${day.value}/meals/`, {
      method: 'POST',
      body,
    })
    photos.value = []
    waterDrank.value = null
    breathingPractice.value = null
    feeling.value = null
    await refresh()
  } catch (e) {
    await dialog.show(parseApiError(e).detail, 'Не удалось добавить прием пищи')
  } finally {
    mealLoading.value = false
  }
}

async function saveParticipantComment() {
  try {
    await api(`courses/${id}/homework/reports/${day.value}/`, {
      method: 'PATCH',
      body: { participant_comment: participantComment.value },
    })
    await refresh()
    await dialog.show('Комментарий сохранен.')
  } catch (e) {
    await dialog.show(parseApiError(e).detail, 'Не удалось сохранить комментарий')
  }
}

function openMealEditor(meal: NonNullable<HomeworkReport['meals']>[number]) {
  editingMeal.value = meal.id
  editWater.value = meal.water_drank
  editBreathing.value = meal.breathing_practice
  editFeeling.value = meal.feeling
  editPhotos.value = []
  editDialog.value = true
}

async function saveMealEdit() {
  if (!editingMeal.value) return
  const body = new FormData()
  body.append('water_drank', String(editWater.value))
  body.append('breathing_practice', String(editBreathing.value))
  body.append('feeling', editFeeling.value)
  for (const photo of editPhotos.value) body.append('photos', photo)
  try {
    await api(`courses/${id}/homework/meals/${editingMeal.value}/`, {
      method: 'PATCH',
      body,
    })
    editDialog.value = false
    await refresh()
  } catch (e) {
    await dialog.show(parseApiError(e).detail, 'Не удалось изменить прием пищи')
  }
}

async function submitReview() {
  if (completed.value === null) {
    await dialog.show('Выберите результат проверки: выполнено или не выполнено.')
    return
  }
  reviewLoading.value = true
  try {
    await api(`courses/${id}/homework/reports/${report.value?.id}/review/`, {
      method: 'POST',
      body: {
        tutor_comment: tutorComment.value,
        is_completed: completed.value,
      },
    })
    await refresh()
    await dialog.show('Проверка отчета сохранена.')
  } catch (e) {
    await dialog.show(parseApiError(e).detail, 'Не удалось проверить отчет')
  } finally {
    reviewLoading.value = false
  }
}
</script>

<template>
  <v-container>
    <v-btn
      variant="text"
      prepend-icon="mdi-arrow-left"
      :to="`/courses/${id}/homework`"
      class="mb-3"
    >
      К списку отчетов
    </v-btn>

    <v-alert v-if="error" type="error" variant="tonal">{{ parseApiError(error).detail }}</v-alert>
    <template v-else-if="report">
      <h1 class="text-h4 mb-2">Отчет за {{ dateLabel(day) }}</h1>
      <p v-if="report.participant_name" class="text-medium-emphasis mb-4">
        Участник курса: {{ report.participant_name }}
      </p>

      <v-alert v-if="!report.available && report.message" type="info" variant="tonal" class="mb-4">
        {{ report.message }}
      </v-alert>

      <v-alert v-else-if="report.status === 'review'" type="info" variant="tonal" class="mb-4">
        Отчет отправлен тьютору на проверку. Редактирование недоступно.
      </v-alert>

      <v-alert
        v-else-if="report.status === 'reviewed'"
        :type="report.is_completed ? 'success' : 'warning'"
        variant="tonal"
        class="mb-4"
      >
        Отчет проверен: {{ report.is_completed ? 'выполнено' : 'не выполнено' }}.
      </v-alert>

      <template v-if="report.available || report.is_created">
        <v-card class="mb-4" title="Приемы пищи">
          <v-card-text>
            <v-alert v-if="!report.meals?.length" type="info" variant="tonal" class="mb-4">
              Пока не добавлено ни одного приема пищи. Отчет будет создан после сохранения первого.
            </v-alert>

            <v-list v-if="report.meals?.length" lines="three">
              <v-list-item v-for="(meal, index) in report.meals" :key="meal.id">
                <template #title>
                  Прием пищи №{{ index + 1 }}
                  <span v-if="canEdit" class="text-medium-emphasis text-body-2">
                    · нажмите для редактирования
                  </span>
                </template>
                <template #subtitle>
                  Вода: {{ meal.water_drank ? 'да' : 'нет' }} · Дыхательная практика:
                  {{ meal.breathing_practice ? 'да' : 'нет' }} · Ощущение:
                  {{ meal.feeling_display }}
                </template>
                <template #append>
                  <v-btn
                    v-if="canEdit"
                    icon="mdi-pencil"
                    size="small"
                    variant="text"
                    aria-label="Редактировать прием пищи"
                    @click="openMealEditor(meal)"
                  />
                </template>
                <template #default>
                  <div class="d-flex flex-wrap ga-2 mt-2">
                    <a
                      v-for="photo in meal.photos"
                      :key="photo.id"
                      :href="photo.url"
                      target="_blank"
                      rel="noreferrer"
                    >
                      <v-img :src="photo.url" width="112" height="90" cover class="rounded" />
                    </a>
                  </div>
                </template>
              </v-list-item>
            </v-list>

            <v-divider v-if="canEdit" class="my-4" />
            <template v-if="canEdit">
              <h3 class="text-h6 mb-3">Добавить прием пищи</h3>
              <v-file-input
                v-model="photos"
                label="Фотографии блюд"
                accept="image/*"
                multiple
                prepend-icon="mdi-camera"
                show-size
                chips
              />
              <v-row>
                <v-col cols="12" md="6">
                  <v-radio-group v-model="waterDrank" label="Выпит стакан воды?">
                    <v-radio label="Да" :value="true" />
                    <v-radio label="Нет" :value="false" />
                  </v-radio-group>
                </v-col>
                <v-col cols="12" md="6">
                  <v-radio-group
                    v-model="breathingPractice"
                    label="Выполнена дыхательная практика?"
                  >
                    <v-radio label="Да" :value="true" />
                    <v-radio label="Нет" :value="false" />
                  </v-radio-group>
                </v-col>
                <v-col cols="12">
                  <v-radio-group v-model="feeling" label="Ощущение перед приемом пищи">
                    <v-radio label="Голод" value="hunger" />
                    <v-radio label="Аппетит" value="appetite" />
                  </v-radio-group>
                </v-col>
              </v-row>
              <v-btn color="primary" :loading="mealLoading" @click="addMeal">
                Сохранить прием пищи
              </v-btn>
            </template>
          </v-card-text>
        </v-card>

        <v-card v-if="!isTutor" class="mb-4" title="Комментарий тьютору">
          <v-card-text>
            <v-textarea
              v-model="participantComment"
              label="Вопрос или уточнение по домашнему заданию"
              rows="3"
              :disabled="!canEdit || !report.meals?.length"
            />
            <v-btn
              color="primary"
              variant="tonal"
              :disabled="!canEdit || !report.meals?.length"
              @click="saveParticipantComment"
            >
              Сохранить комментарий
            </v-btn>
          </v-card-text>
        </v-card>

        <v-card
          v-if="report.tutor_comment || report.is_completed !== null"
          class="mb-4"
          title="Результат проверки"
        >
          <v-card-text>
            <p class="mb-2">
              <b>Оценка:</b>
              {{ report.is_completed ? 'Выполнено' : 'Не выполнено' }}
            </p>
            <p><b>Комментарий тьютора:</b> {{ report.tutor_comment || 'Без комментария' }}</p>
          </v-card-text>
        </v-card>

        <v-card v-if="isTutor && report.status === 'review'" title="Проверка отчета">
          <v-card-text>
            <v-radio-group v-model="completed" label="Результат проверки">
              <v-radio label="Выполнено" :value="true" />
              <v-radio label="Не выполнено" :value="false" />
            </v-radio-group>
            <v-textarea v-model="tutorComment" label="Комментарий тьютора" rows="3" />
            <v-btn color="primary" :loading="reviewLoading" @click="submitReview">
              Подтвердить проверку
            </v-btn>
          </v-card-text>
        </v-card>
      </template>
    </template>
  </v-container>

  <v-dialog v-model="editDialog" max-width="600">
    <v-card title="Редактирование приема пищи">
      <v-card-text>
        <v-file-input
          v-model="editPhotos"
          label="Новые фотографии (если нужно заменить старые)"
          accept="image/*"
          multiple
          chips
        />
        <v-radio-group v-model="editWater" label="Выпит стакан воды?">
          <v-radio label="Да" :value="true" />
          <v-radio label="Нет" :value="false" />
        </v-radio-group>
        <v-radio-group v-model="editBreathing" label="Выполнена дыхательная практика?">
          <v-radio label="Да" :value="true" />
          <v-radio label="Нет" :value="false" />
        </v-radio-group>
        <v-radio-group v-model="editFeeling" label="Ощущение перед приемом пищи">
          <v-radio label="Голод" value="hunger" />
          <v-radio label="Аппетит" value="appetite" />
        </v-radio-group>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="editDialog = false">Отмена</v-btn>
        <v-btn color="primary" @click="saveMealEdit">Сохранить</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
