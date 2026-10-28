<script setup lang="ts">
const open = defineModel<boolean>({ required: true })
</script>

<template>
  <v-dialog v-model="open" max-width="440">
    <v-card title="Учётная запись уже существует">
      <v-card-text>
        Пользователь с таким email или телефоном уже зарегистрирован. Войдите в систему или
        восстановите пароль.
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn to="/forgot-password">Восстановить пароль</v-btn>
        <v-btn color="primary" variant="flat" to="/login">Войти</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
