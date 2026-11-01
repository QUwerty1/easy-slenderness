<script setup lang="ts">
const auth = useAuthStore()

// Navigation panel of the course management module, by role
const items = computed(() => {
  const role = auth.user?.role
  if (role === 'admin')
    return [
      { title: 'Курсы', to: '/courses' },
      { title: 'Управление курсами', to: '/manage' },
      { title: 'Заявки на исключение', to: '/requests' },
    ]
  if (role === 'tutor')
    return [
      { title: 'Курсы', to: '/courses' },
      { title: 'Мои курсы', to: '/my-courses' },
    ]
  return [
    { title: 'Записаться на курс', to: '/courses' },
    { title: 'Мои курсы', to: '/my-courses' },
    { title: 'Мои заявки', to: '/my-requests' },
  ]
})
</script>

<template>
  <v-tabs bg-color="primary" density="compact" slider-color="white">
    <v-tab v-for="item in items" :key="item.to" :to="item.to">{{ item.title }}</v-tab>
  </v-tabs>
</template>
