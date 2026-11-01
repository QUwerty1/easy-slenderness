<script setup lang="ts">
definePageMeta({ middleware: 'course-role', roles: ['admin'] })
</script>

<template>
  <v-container max-width="640">
    <v-card title="Создание курса">
      <CourseForm />
    </v-card>
  </v-container>
</template>
