import { defineStore } from 'pinia'
import api from '../api/client'

// KAKEI とアカウント共通 (同じバックエンドの認証 API を使う)
export const useAuthStore = defineStore('auth', {
  state: () => ({ user: null, initialized: false }),
  actions: {
    async init() {
      try {
        await api.get('/auth/csrf/')
        const { data } = await api.get('/auth/me/')
        this.user = data
      } catch {
        this.user = null
      }
      this.initialized = true
    },
    async login(username, password) {
      const { data } = await api.post('/auth/login/', { username, password })
      this.user = data
    },
    async register(username, password) {
      const { data } = await api.post('/auth/register/', { username, password })
      this.user = data
    },
    async logout() {
      await api.post('/auth/logout/')
      this.user = null
    },
  },
})
