<script setup lang="ts">
const counter = useCounterStore()
</script>

<template>
  <v-container>
    <h1 class="text-h4 mb-4">Home</h1>
    <v-btn color="primary" prepend-icon="mdi-plus" @click="counter.increment">
      Count: {{ counter.count }} (x2 = {{ counter.doubled }})
    </v-btn>
  </v-container>
</template>
