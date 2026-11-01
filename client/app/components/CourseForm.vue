<script setup lang="ts">
import type { Course, CoursePayload, CourseStatus } from '~/types/course'

// Форма курса: создание (course не задан) и редактирование
const props = defineProps<{ course?: Course }>()

const api = useCourseApi()
const dialog = useSystemDialog()
const form = ref()
const data = reactive({
  name: props.course?.name ?? '',
  status: (props.course?.status ?? 'paid') as CourseStatus,
  start_at: toLocalInput(props.course?.start_at ?? new Date(Date.now() + 7 * 864e5)),
  price: props.course?.price ?? '',
})
const errors = ref<Record<string, string[]>>({})
const loading = ref(false)

const isPaid = computed(() => data.status === 'paid')
const endAt = computed(() => {
  const start = new Date(data.start_at)
  if (Number.isNaN(start.getTime())) return ''
  const weeks = isPaid.value ? 4 : 1
  return formatDateTime(new Date(start.getTime() + weeks * 7 * 864e5).toISOString())
})
const priceRules = [
  (v: string) =>
    !isPaid.value || Number(v) > 0 || 'Для платного курса цена должна быть больше нуля',
]

function clearError(field: string) {
  errors.value[field] = []
}

async function save() {
  const { valid } = await form.value.validate()
  if (!valid) return
  loading.value = true
  const body: CoursePayload = {
    name: data.name,
    start_at: new Date(data.start_at).toISOString(),
    price: isPaid.value ? String(data.price) : null,
  }
  try {
    if (props.course) {
      await api(`courses/${props.course.id}/`, { method: 'PATCH', body })
      await dialog.show('Курс сохранён.')
    } else {
      await api('courses/', { method: 'POST', body: { ...body, status: data.status } })
      await dialog.show('Курс создан и открыт для записи.')
    }
    await navigateTo('/manage')
  } catch (e) {
    const err = parseApiError(e)
    if (Object.keys(err.fields).length) errors.value = err.fields
    else dialog.show(err.detail, 'Ошибка')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <v-form ref="form" @submit.prevent="save">
    <v-card-text>
      <v-text-field
        v-model="data.name"
        label="Название"
        :rules="[rules.required]"
        :error-messages="errors.name"
        @update:model-value="clearError('name')"
      />
      <v-text-field
        v-model="data.start_at"
        label="Время начала"
        type="datetime-local"
        :rules="[rules.required]"
        :error-messages="errors.start_at"
        @update:model-value="clearError('start_at')"
      />
      <div class="mb-2">
        <div class="text-body-2 text-medium-emphasis">Статус</div>
        <v-radio-group v-if="!course" v-model="data.status" inline hide-details>
          <v-radio label="Платный" value="paid" />
          <v-radio label="Бесплатный" value="free" />
        </v-radio-group>
        <div v-else>
          {{ course.status_display }}
          <span class="text-medium-emphasis">(задаётся при создании)</span>
        </div>
      </div>
      <v-text-field
        v-model="data.price"
        label="Цена, ₽"
        type="number"
        min="0"
        :disabled="!isPaid"
        :rules="priceRules"
        :error-messages="errors.price"
        @update:model-value="clearError('price')"
      />
      <p v-if="endAt" class="text-medium-emphasis">
        Время окончания рассчитывается автоматически: {{ endAt }}
      </p>
    </v-card-text>
    <v-card-actions class="px-4 pb-4">
      <v-btn to="/manage">Отмена</v-btn>
      <v-spacer />
      <v-btn color="primary" variant="flat" type="submit" :loading="loading">Сохранить</v-btn>
    </v-card-actions>
  </v-form>
</template>
