<script setup lang="ts">
// Imitation of the payment service page (PAYMENT_GATEWAY = "fake" on the backend).
// Not a part of the module: with YooKassa the user pays on the service's own page.
const route = useRoute()
const api = useCourseApi()
const order = String(route.query.order ?? '')
const amount = String(route.query.amount ?? '')
const description = String(route.query.description ?? '')
const returnUrl = String(route.query.return ?? '/courses')
const loading = ref(false)

async function finish(success: boolean) {
  loading.value = true
  try {
    await api('payments/fake/', { method: 'POST', body: { order_id: order, success, amount } })
  } finally {
    window.location.href = returnUrl
  }
}
</script>

<template>
  <v-container max-width="520">
    <v-card title="Платёжный сервис" subtitle="Тестовая страница оплаты">
      <v-card-text>
        <v-alert type="warning" variant="tonal" density="compact" class="mb-4">
          Это внешняя страница, не часть модуля. Здесь она имитирует оплату.
        </v-alert>
        <p class="mb-1">{{ description }}</p>
        <p class="text-h5 mb-1">{{ formatMoney(amount) }}</p>
        <p class="text-medium-emphasis mb-4">Заказ {{ order }}</p>
        <v-text-field label="Номер карты" placeholder="Данные вводятся на странице сервиса" />
        <v-text-field label="Email для чека" type="email" />
      </v-card-text>
      <v-card-actions class="px-4 pb-4">
        <v-btn color="error" variant="tonal" :disabled="loading" @click="finish(false)">
          Имитировать ошибку оплаты
        </v-btn>
        <v-spacer />
        <v-btn color="primary" variant="flat" :loading="loading" @click="finish(true)">
          Оплатить
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-container>
</template>
