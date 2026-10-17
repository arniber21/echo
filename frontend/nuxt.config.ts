export default defineNuxtConfig({
  compatibilityDate: '2026-10-17',
  modules: ['@nuxt/ui'],
  css: ['~/assets/css/main.css'],
  ui: { fonts: false, colorMode: false },
  icon: {
    localApiEndpoint: '/_icons',
    serverBundle: { collections: ['lucide'] },
    clientBundle: { scan: true },
    provider: 'server',
  },
  typescript: { strict: true },
  devtools: { enabled: false },
  runtimeConfig: { apiBase: process.env.NUXT_API_BASE ?? 'http://127.0.0.1:8000' },
  nitro: {
    routeRules: {
      '/api/**': { proxy: `${process.env.NUXT_API_BASE ?? 'http://127.0.0.1:8000'}/api/**` },
    },
  },
  app: {
    head: {
      title: 'Rewind — evidence into understanding',
      meta: [
        { name: 'description', content: 'An evidence-linked incident reconstruction workspace.' },
      ],
    },
  },
})
