<script setup lang="ts">
import type { Course } from '~/types/course'

definePageMeta({ middleware: 'course-role', roles: ['admin'] })

const route = useRoute()
const api = useCourseApi()
const id = Number(route.params.id)
const { data: course } = useAsyncData(`course-${id}`, () => api<Course>(`courses/${id}/`))
</script>

<template>
  <v-container max-width="640">
    <v-card title="Редактирование курса">
      <v-card-text v-if="course && !course.can_edit">
        <v-alert type="warning" variant="tonal">
          Курс уже начался: редактирование запрещено.
        </v-alert>
      </v-card-text>
      <CourseForm v-else-if="course" :course="course" />
    </v-card>
  </v-container>
</template>
