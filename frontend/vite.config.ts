import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  server: {
    host: '127.0.0.1',
    port: 5173,
    proxy: {
      '/accounts': 'http://backend:8000',
      '/agent/chat': 'http://backend:8000',
      '/api': 'http://backend:8000',
      '/business-metrics': 'http://backend:8000',
      '/metrics': 'http://backend:8000',
      '/performance-reports': 'http://backend:8000',
      '/reviews': 'http://backend:8000',
      '/strategy-memories': 'http://backend:8000',
      '/workflow-runs': 'http://backend:8000',
      '/xhs': 'http://backend:8000'
    }
  }
})
