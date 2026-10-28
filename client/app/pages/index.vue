<script setup lang="ts">
import type { Role } from '~/types/auth'

const auth = useAuthStore()

interface Section {
  title: string
  text: string
  icon: string
  roles: Role[]
}

// Sections are implemented by other modules; the auth module only filters them by role
const sections: Section[] = [
  {
    title: 'Каталог курсов',
    text: 'Выберите групповой курс и подайте заявку на участие.',
    icon: 'mdi-book-open-variant',
    roles: ['user', 'participant'],
  },
  {
    title: 'Мои курсы',
    text: 'Занятия, материалы и домашние задания ваших курсов.',
    icon: 'mdi-school',
    roles: ['participant'],
  },
  {
    title: 'Мои группы',
    text: 'Участники, расписание встреч и проверка домашних заданий.',
    icon: 'mdi-account-group',
    roles: ['tutor'],
  },
  {
    title: 'Администрирование',
    text: 'Курсы, группы, тьюторы и учётные записи.',
    icon: 'mdi-shield-account',
    roles: ['admin'],
  },
]

const available = computed(() =>
  sections.filter((section) => auth.user && section.roles.includes(auth.user.role)),
)
</script>

<template>
  <v-container>
    <h1 class="text-h4 mb-1">Здравствуйте, {{ auth.user?.full_name }}!</h1>
    <p class="text-medium-emphasis mb-6">Роль: {{ auth.user?.role_display }}</p>
    <v-row>
      <v-col v-for="section in available" :key="section.title" cols="12" sm="6" md="4">
        <v-card
          :prepend-icon="section.icon"
          :title="section.title"
          :text="section.text"
          height="100%"
        >
          <v-card-actions>
            <v-chip size="small" variant="tonal">Скоро</v-chip>
          </v-card-actions>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>
