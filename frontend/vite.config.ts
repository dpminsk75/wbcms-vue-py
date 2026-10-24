import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  server: {
    host: '0.0.0.0',
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        // тяжёлый расчёт матрицы может думать десятки секунд; без таймаута
        // прокси держал сокет «вечно» и страница висела, пока не умрёт бекенд
        timeout: 150000,
        proxyTimeout: 150000,
      },
    },
  },
})
