import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// API は KAKEI のバックエンドを共用する。本番は Nginx の既存 /kakei/api/ に
// 同一オリジンでそのまま届くため、開発でもパスを /kakei/api に揃えてプロキシする。
const apiProxy = {
  '/kakei/api': {
    target: process.env.VITE_PROXY_TARGET || 'http://127.0.0.1:8000',
    // changeOrigin は false 必須: true だと Host が書き換わり
    // Django の CSRF オリジン検証 (Origin vs Host) が失敗する。
    changeOrigin: false,
    // 開発の Django には SCRIPT_NAME が無いので /kakei を剥がして転送する
    rewrite: (path) => path.replace(/^\/kakei\/api/, '/api'),
  },
}

export default defineConfig({
  plugins: [vue()],
  // 本番はサブパス /kabu/ で公開 (開発も同じパスに揃える)
  base: '/kabu/',
  server: {
    host: true,
    port: 5173,
    // Windows のバインドマウント (Docker) では inotify が飛ばないため polling が必要
    watch: { usePolling: true },
    proxy: apiProxy,
  },
  // 本番ビルドの動作確認用 (vite preview)
  preview: {
    host: true,
    port: 4174,
    proxy: apiProxy,
  },
})
