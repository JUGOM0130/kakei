import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    host: true,
    port: 5173,
    // Windows のバインドマウント (Docker) では inotify が飛ばないため polling が必要
    watch: { usePolling: true },
    proxy: {
      // Docker Compose では VITE_PROXY_TARGET=http://backend:8000 を注入。
      // changeOrigin は false 必須: true だと Host が書き換わり
      // Django の CSRF オリジン検証 (Origin vs Host) が失敗する
      '/api': {
        target: process.env.VITE_PROXY_TARGET || 'http://127.0.0.1:8000',
        changeOrigin: false,
      },
    },
  },
})
