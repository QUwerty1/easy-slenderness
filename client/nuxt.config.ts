// https://nuxt.com/docs/api/configuration/nuxt-config
import vuetify, { transformAssetUrls } from 'vite-plugin-vuetify'

export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  devtools: { enabled: true },

  // Auth relies on Django session cookies, so the app is rendered in the browser only
  ssr: false,

  app: {
    head: {
      title: 'Легкая стройность',
      htmlAttrs: { lang: 'ru' },
    },
  },

  // Same origin for the client and the API: no CORS, cookies work as is
  routeRules: {
    '/api/**': { proxy: `${process.env.API_URL ?? 'http://localhost:8000'}/api/**` },
  },

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
