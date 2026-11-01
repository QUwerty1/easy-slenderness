<script setup lang="ts">
// The start page of the platform is the list of courses available for enrollment
definePageMeta({
  middleware: () => navigateTo('/courses', { replace: true }),
})
</script>

<template>
  <div />
</template>
