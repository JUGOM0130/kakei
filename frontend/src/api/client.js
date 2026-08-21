import axios from 'axios'

// 同一オリジン (Vite プロキシ / Nginx) 前提。axios が csrftoken Cookie を
// X-CSRFToken ヘッダに自動転記する。
const api = axios.create({
  baseURL: '/api',
  xsrfCookieName: 'csrftoken',
  xsrfHeaderName: 'X-CSRFToken',
})

// セッション切れ (401/403) はログイン画面へ。認証系エンドポイント自身は除外
export function setupAuthRedirect(router) {
  api.interceptors.response.use(null, (error) => {
    const status = error.response?.status
    const url = error.config?.url || ''
    if ((status === 401 || status === 403) && !url.startsWith('/auth/')) {
      router.push('/login')
    }
    return Promise.reject(error)
  })
}

export default api
