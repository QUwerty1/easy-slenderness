<script setup lang="ts">
import type { Candidate, Course } from '~/types/course'

definePageMeta({ middleware: 'course-role', roles: ['admin'] })

// Форма ручного зачисления и форма оплаты вне системы
const route = useRoute()
const api = useCourseApi()
const dialog = useSystemDialog()
const id = Number(route.params.id)
const filters = ref({ full_name: '', phone: '', email: '' })
const query = computed(() =>
  Object.fromEntries(Object.entries(filters.value).filter(([, value]) => value)),
)

const { data: course } = useAsyncData(`course-${id}`, () => api<Course>(`courses/${id}/`))
const { data: users } = useAsyncData(
  `candidates-${id}`,
  () => api<Candidate[]>(`courses/${id}/candidates/`, { query: query.value }),
  { watch: [query] },
)

const today = toLocalInput(new Date()).slice(0, 10)
const selected = ref<Candidate | null>(null)
const payment = reactive({ amount: '', paid_on: today })
const errors = ref<Record<string, string[]>>({})
const form = ref()
const loading = ref(false)

function choose(user: Candidate) {
  selected.value = user
  payment.amount = course.value?.price ?? ''
  payment.paid_on = today
  errors.value = {}
}

async function enroll() {
  const { valid } = await form.value.validate()
  if (!valid || !selected.value) return
  loading.value = true
  try {
    await api(`courses/${id}/manual-enroll/`, {
      method: 'POST',
      body: { user_id: selected.value.id, ...payment },
    })
    selected.value = null
    await dialog.show('Участник зачислен вручную, оплата вне системы сохранена.')
    await navigateTo(`/manage/${id}/participants`)
  } catch (e) {
    const err = parseApiError(e)
    if (Object.keys(err.fields).length) errors.value = err.fields
    else dialog.show(err.detail, 'Зачисление невозможно')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <v-container>
    <v-btn
      variant="text"
      prepend-icon="mdi-arrow-left"
      :to="`/manage/${id}/participants`"
      class="mb-2"
    >
      Управление участниками
    </v-btn>
    <h1 class="text-h4">Ручное зачисление</h1>
    <p class="text-medium-emphasis mb-4">
      Курс «{{ course?.name }}». Ручное зачисление выполняется при оплате вне системы: выберите
      пользователя и введите сумму и дату оплаты. В списке — все пользователи, кроме тьюторов и
      администраторов.
    </p>
    <ParticipantFilters v-model="filters" />
    <v-card>
      <v-table>
        <thead>
          <tr>
            <th>ФИО</th>
            <th>Телефон</th>
            <th>Email</th>
            <th />
          </tr>
        </thead>
        <tbody>
          <tr v-for="u in users" :key="u.id">
            <td>{{ u.full_name }}</td>
            <td>{{ u.phone }}</td>
            <td>{{ u.email }}</td>
            <td class="text-right">
              <span v-if="u.is_participant" class="text-medium-emphasis">Уже участник</span>
              <v-btn v-else size="small" color="primary" variant="flat" @click="choose(u)">
                Зачислить
              </v-btn>
            </td>
          </tr>
          <tr v-if="!users?.length">
            <td colspan="4" class="text-medium-emphasis">Пользователи не найдены</td>
          </tr>
        </tbody>
      </v-table>
    </v-card>

    <v-dialog :model-value="!!selected" max-width="480" @update:model-value="selected = null">
      <v-card v-if="selected" title="Оплата вне системы">
        <v-form ref="form" @submit.prevent="enroll">
          <v-card-text>
            <p class="mb-1"><b>Пользователь:</b> {{ selected.full_name }}</p>
            <p class="mb-1">
              <b>Курс:</b> {{ course?.name }}, цена {{ formatMoney(course?.price ?? null) }}
            </p>
            <p class="mb-4">
              <b>Способ оплаты:</b> вне системы
              <span class="text-medium-emphasis">(устанавливается автоматически)</span>
            </p>
            <v-text-field
              v-model="payment.amount"
              label="Сумма оплаты, ₽"
              type="number"
              :rules="[(v: string) => Number(v) > 0 || 'Сумма оплаты должна быть больше нуля']"
              :error-messages="errors.amount"
            />
            <v-text-field
              v-model="payment.paid_on"
              label="Дата оплаты"
              type="date"
              :max="today"
              :rules="[
                rules.required,
                (v: string) => v <= today || 'Дата оплаты не может быть позже текущей даты',
              ]"
              :error-messages="errors.paid_on"
            />
          </v-card-text>
          <v-card-actions>
            <v-spacer />
            <v-btn :disabled="loading" @click="selected = null">Отмена</v-btn>
            <v-btn color="primary" variant="flat" type="submit" :loading="loading">Зачислить</v-btn>
          </v-card-actions>
        </v-form>
      </v-card>
    </v-dialog>
  </v-container>
</template>
