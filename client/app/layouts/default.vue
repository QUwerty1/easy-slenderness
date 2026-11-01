<script setup lang="ts">
const auth = useAuthStore()

useIdleLogout()

async function logout() {
  await auth.logout()
  await navigateTo('/login')
}
</script>

<template>
  <v-app-bar color="primary" density="comfortable">
    <v-app-bar-title>
      <NuxtLink to="/" class="text-white text-decoration-none">Легкая стройность</NuxtLink>
    </v-app-bar-title>
    <template v-if="auth.isAuthed" #append>
      <v-menu>
        <template #activator="{ props }">
          <v-btn v-bind="props" prepend-icon="mdi-account-circle" append-icon="mdi-menu-down">
            Учётная запись
          </v-btn>
        </template>
        <v-list density="compact">
          <v-list-item :subtitle="auth.user?.email" :title="auth.user?.full_name" />
          <v-divider />
          <v-list-item prepend-icon="mdi-account" title="Профиль" to="/account" />
          <v-list-item prepend-icon="mdi-logout" title="Выйти" @click="logout" />
        </v-list>
      </v-menu>
    </template>
    <template v-if="auth.isAuthed" #extension>
      <CourseNav />
    </template>
  </v-app-bar>
  <v-main>
    <slot />
  </v-main>
</template>
