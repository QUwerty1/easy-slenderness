<script setup lang="ts">
// Return from the payment service: success → «Мои курсы», failure → list of courses
const route = useRoute()
const api = useCourseApi()
const dialog = useSystemDialog()
const courseId = Number(route.query.course)

onMounted(async () => {
  // The service notification may come slightly later than the user returns
  for (let attempt = 0; attempt < 5; attempt++) {
    try {
      const { is_participant } = await api<{ is_participant: boolean }>(
        `courses/${courseId}/enrollment/`,
      )
      if (is_participant) {
        await dialog.show('Оплата подтверждена. Курс добавлен в «Мои курсы».')
        return navigateTo('/my-courses')
      }
    } catch {
      break
    }
    await new Promise((resolve) => setTimeout(resolve, 1000))
  }
  await dialog.show(
    'Оплата не подтверждена, вы не записаны на курс. Если деньги были списаны, обратитесь к администратору.',
    'Ошибка оплаты',
  )
  return navigateTo('/courses')
})
</script>

<template>
  <v-container class="text-center py-12">
    <v-progress-circular indeterminate color="primary" class="mb-4" />
    <p>Проверяем оплату…</p>
  </v-container>
</template>
