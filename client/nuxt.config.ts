// https://nuxt.com/docs/api/configuration/nuxt-config
import vuetify, { transformAssetUrls } from 'vite-plugin-vuetify'

export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  devtools: { enabled: true },

  build: {
    transpile: ['vuetify'],
  },

  modules: [
    '@pinia/nuxt',
    (_options, nuxt) => {
      nuxt.hooks.hook('vite:extendConfig', (config) => {
        // @ts-expect-error plugins is always defined here
        config.plugins.push(vuetify({ autoImport: true }))
      })
    },
  ],

  css: ['@mdi/font/css/materialdesignicons.css'],

  vite: {
    vue: {
      template: {
        transformAssetUrls,
      },
    },
  },
})
