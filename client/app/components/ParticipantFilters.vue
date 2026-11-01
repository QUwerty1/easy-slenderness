<script setup lang="ts">
// Группа фильтров: ФИО, телефон, email и, при необходимости, статус участия
defineProps<{ withStatus?: boolean }>()
const filters = defineModel<Record<string, string>>({ required: true })

const statuses = [
  { title: 'Активен', value: 'active' },
  { title: 'Исключён', value: 'excluded' },
]

function reset() {
  for (const key of Object.keys(filters.value)) filters.value[key] = ''
}
</script>

<template>
  <v-card class="mb-4" title="Фильтры" density="compact">
    <v-card-text>
      <v-row dense>
        <v-col cols="12" sm="6" md="3">
          <v-text-field v-model="filters.full_name" label="ФИО" density="compact" hide-details />
        </v-col>
        <v-col cols="12" sm="6" md="3">
          <v-text-field v-model="filters.phone" label="Телефон" density="compact" hide-details />
        </v-col>
        <v-col cols="12" sm="6" md="3">
          <v-text-field v-model="filters.email" label="Email" density="compact" hide-details />
        </v-col>
        <v-col v-if="withStatus" cols="12" sm="6" md="3">
          <v-select
            v-model="filters.status"
            :items="statuses"
            label="Статус участия"
            density="compact"
            clearable
            hide-details
          />
        </v-col>
      </v-row>
      <v-btn class="mt-3" size="small" variant="text" @click="reset">Сбросить фильтры</v-btn>
    </v-card-text>
  </v-card>
</template>
