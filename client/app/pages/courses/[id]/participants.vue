<script setup lang="ts">
import type { Course, PublicParticipant } from '~/types/course'

// Список участников курса (без контактных данных — 152-ФЗ)
const route = useRoute()
const api = useCourseApi()
const id = Number(route.params.id)
const { data: course } = useAsyncData(`course-${id}`, () => api<Course>(`courses/${id}/`))
const { data: participants, error } = useAsyncData(`participants-${id}`, () =>
  api<PublicParticipant[]>(`courses/${id}/participants/`),
)
</script>

<template>
  <v-container max-width="720">
    <v-btn variant="text" prepend-icon="mdi-arrow-left" :to="`/courses/${id}/view`" class="mb-2">
      К курсу
    </v-btn>
    <h1 class="text-h4 mb-4">Участники: {{ course?.name }}</h1>
    <v-alert v-if="error" type="error" variant="tonal">{{ parseApiError(error).detail }}</v-alert>
    <v-card v-else>
      <v-table>
        <thead>
          <tr>
            <th>ФИО</th>
            <th>Роль</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="p in participants" :key="p.id">
            <td>{{ p.full_name }}</td>
            <td>{{ p.role }}</td>
          </tr>
          <tr v-if="!participants?.length">
            <td colspan="2" class="text-medium-emphasis">Участников пока нет</td>
          </tr>
        </tbody>
      </v-table>
    </v-card>
  </v-container>
</template>
