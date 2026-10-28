<script setup lang="ts">
const { state, close } = useSystemDialog()
</script>

<template>
  <v-dialog :model-value="state.open" max-width="440" persistent>
    <v-card :title="state.title">
      <v-card-text class="text-pre-wrap">{{ state.text }}</v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn color="primary" variant="flat" @click="close">ОК</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
