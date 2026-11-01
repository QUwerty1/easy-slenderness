<script setup lang="ts">
import type { RequestDetail } from '~/types/course'

definePageMeta({ middleware: 'course-role', roles: ['admin'] })

// Форма обработки заявки на возврат средств
const route = useRoute()
const api = useCourseApi()
const dialog = useSystemDialog()
const id = Number(route.params.id)
const { data: req, error } = useAsyncData(`request-${id}`, () =>
  api<RequestDetail>(`requests/${id}/`),
)

const fpr = ref('')
const fprErrors = ref<string[]>([])
const busy = ref<'' | 'refund' | 'close' | 'reject'>('')

watch(
  req,
  (value) => {
    if (value && fpr.value === '') fpr.value = value.refund?.fpr ?? (value.before_start ? '0' : '')
  },
  { immediate: true },
)

const open = computed(() => req.value?.status === 'registered')
const offline = computed(() => req.value?.payment?.method === 'offline')
const refunded = computed(() => !!req.value?.refund)
const violator = computed(() => req.value?.basis === 'violation' || !req.value?.participant_active)
const refundSum = computed(() => {
  const paid = Number(req.value?.payment?.amount ?? 0)
  const value = Number(fpr.value)
  if (fpr.value === '' || Number.isNaN(value) || value < 0 || value > paid) return null
  return paid - value
})

async function act(action: 'refund' | 'close' | 'reject') {
  if (action === 'refund' && refundSum.value === null) {
    fprErrors.value = ['Введите ФПР от нуля до оплаченной суммы']
    return
  }
  busy.value = action
  try {
    req.value = await api<RequestDetail>(`requests/${id}/${action}/`, {
      method: 'POST',
      body: action === 'refund' ? { fpr: fpr.value } : undefined,
    })
    if (action === 'refund') {
      dialog.show(
        offline.value
          ? `Отмечено: ${formatMoney(req.value.refund!.amount)} возвращено вне системы.`
          : `Платёжный сервис подтвердил возврат ${formatMoney(req.value.refund!.amount)}.`,
      )
    } else {
      await dialog.show(
        action === 'close'
          ? 'Заявка закрыта как выполненная.'
          : 'Заявка отклонена, участник остаётся в курсе.',
      )
      await navigateTo('/requests')
    }
  } catch (e) {
    const err = parseApiError(e)
    if (err.fields.fpr) fprErrors.value = err.fields.fpr
    else dialog.show(err.detail, 'Ошибка')
  } finally {
    busy.value = ''
  }
}
</script>

<template>
  <v-container>
    <v-btn variant="text" prepend-icon="mdi-arrow-left" to="/requests" class="mb-2">
      Заявки на исключение
    </v-btn>
    <v-alert v-if="error" type="error" variant="tonal">{{ parseApiError(error).detail }}</v-alert>
    <template v-else-if="req">
      <h1 class="text-h4 mb-4">
        {{ open ? 'Обработка заявки' : 'Заявка' }}
        <v-chip :color="requestColor[req.status]">{{ req.status_display }}</v-chip>
      </h1>
      <v-row>
        <v-col cols="12" md="6" lg="3">
          <v-card title="Участник" height="100%">
            <v-card-text>
              <div>{{ req.full_name }}</div>
              <div>{{ req.phone }}</div>
              <div>{{ req.email }}</div>
            </v-card-text>
          </v-card>
        </v-col>
        <v-col cols="12" md="6" lg="3">
          <v-card title="Заявка" height="100%">
            <v-card-text>
              <div>Основание: {{ req.basis_display }}</div>
              <div>Причина: {{ req.reason || '—' }}</div>
              <div>Подана: {{ formatDateTime(req.created_at) }}</div>
            </v-card-text>
          </v-card>
        </v-col>
        <v-col cols="12" md="6" lg="3">
          <v-card title="Данные курса" height="100%">
            <v-card-text>
              <div>{{ req.course.name }}</div>
              <div>{{ formatDate(req.course.start_at) }} – {{ formatDate(req.course.end_at) }}</div>
              <div>Пройдено на дату подачи заявки: {{ req.passed_percent }}%</div>
            </v-card-text>
          </v-card>
        </v-col>
        <v-col cols="12" md="6" lg="3">
          <v-card title="Данные об оплате" height="100%">
            <v-card-text v-if="req.payment">
              <div>Способ: {{ req.payment.method_display.toLowerCase() }}</div>
              <div>Сумма: {{ formatMoney(req.payment.amount) }}</div>
              <div>
                Дата:
                {{
                  offline ? formatDate(req.payment.paid_at) : formatDateTime(req.payment.paid_at)
                }}
              </div>
              <div v-if="req.payment.transaction_id">
                ID платежа: {{ req.payment.transaction_id }}
              </div>
            </v-card-text>
            <v-card-text v-else>Курс бесплатный — возврат не нужен</v-card-text>
          </v-card>
        </v-col>
      </v-row>

      <v-card v-if="open && req.payment" class="mt-4">
        <v-card-text>
          <v-text-field
            v-model="fpr"
            type="number"
            min="0"
            :max="req.payment.amount"
            label="ФПР, ₽"
            :hint="req.before_start ? 'Заявка подана до старта курса — ФПР равны нулю' : ''"
            persistent-hint
            :disabled="refunded || req.before_start"
            :error-messages="fprErrors"
            max-width="280"
            @update:model-value="fprErrors = []"
          />
          <p class="mt-3">
            Сумма возврата: <b>{{ refundSum === null ? '—' : formatMoney(refundSum) }}</b>
          </p>
          <v-alert
            v-if="!violator && !refunded"
            type="info"
            variant="tonal"
            density="compact"
            class="mt-3"
          >
            Перед возвратом свяжитесь с участником ({{ req.phone }}, {{ req.email }}), назовите
            сумму и получите подтверждение исключения. Если участник отказывается — отклоните
            заявку.
          </v-alert>
          <v-alert
            v-if="offline && !refunded"
            type="info"
            variant="tonal"
            density="compact"
            class="mt-3"
          >
            Курс оплачен вне системы: верните участнику рассчитанную сумму самостоятельно, затем
            нажмите «Средства возвращены». До этого заявку закрыть нельзя.
          </v-alert>
          <v-alert v-if="refunded" type="success" variant="tonal" density="compact" class="mt-3">
            {{
              offline
                ? 'Возврат отмечен: сумма возвращена администратором вне системы.'
                : 'Платёжный сервис подтвердил возврат на счёт, с которого был оплачен курс.'
            }}
            Теперь заявку можно только закрыть.
          </v-alert>
        </v-card-text>
        <v-card-actions class="px-4 pb-4 flex-wrap ga-2">
          <v-btn
            color="primary"
            variant="flat"
            :disabled="refunded || !!busy"
            :loading="busy === 'refund'"
            @click="act('refund')"
          >
            {{ offline ? 'Средства возвращены' : 'Вернуть средства' }}
          </v-btn>
          <v-btn
            color="primary"
            variant="flat"
            :disabled="!refunded || !!busy"
            :loading="busy === 'close'"
            @click="act('close')"
          >
            Закрыть заявку
          </v-btn>
          <v-btn
            v-if="req.can_reject"
            color="error"
            variant="tonal"
            :disabled="!!busy"
            :loading="busy === 'reject'"
            @click="act('reject')"
          >
            Отклонить заявку
          </v-btn>
          <v-spacer />
          <v-btn to="/requests">Отмена</v-btn>
        </v-card-actions>
      </v-card>

      <v-card v-else-if="!open" class="mt-4" title="Результат">
        <v-card-text>
          <template v-if="req.status === 'rejected'">
            Заявка отклонена: участник отказался от исключения и остался в курсе. Возврат не
            выполнялся.
          </template>
          <template v-else-if="req.refund">
            <div>ФПР: {{ formatMoney(req.refund.fpr) }}</div>
            <div>
              Сумма возврата: <b>{{ formatMoney(req.refund.amount) }}</b>
            </div>
            <div>Дата возврата: {{ formatDateTime(req.refund.refunded_at) }}</div>
            <div>Способ возврата: {{ offline ? 'вне системы' : 'через платёжный сервис' }}</div>
            <div>Участник исключён из курса.</div>
          </template>
          <template v-else>
            Курс бесплатный: участник исключён автоматически сразу после подачи заявки, возврат не
            требуется.
          </template>
          <div class="text-medium-emphasis mt-2">Заявка закрыта, изменить её нельзя.</div>
        </v-card-text>
      </v-card>
    </template>
  </v-container>
</template>
