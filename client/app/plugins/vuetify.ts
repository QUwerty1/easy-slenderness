import 'vuetify/styles'
import { createVuetify } from 'vuetify'
import { ru } from 'vuetify/locale'

export default defineNuxtPlugin((app) => {
  const vuetify = createVuetify({
    locale: {
      locale: 'ru',
      messages: { ru },
    },
    theme: {
      defaultTheme: 'light',
      themes: {
        light: {
          colors: {
            primary: '#2e7d32',
            secondary: '#558b2f',
          },
        },
      },
    },
  })
  app.vueApp.use(vuetify)
})
