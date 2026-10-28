<script setup lang="ts">
defineProps<{ title: string; subtitle?: string }>()
</script>

<template>
  <v-container class="fill-height justify-center">
    <v-card :title="title" :subtitle="subtitle" width="100%" max-width="460" class="pa-2">
      <slot />
    </v-card>
  </v-container>
</template>
