import { defineStore } from 'pinia'
import api from '../api/client'

export const useGroupStore = defineStore('group', {
  state: () => ({ group: null, loaded: false }),
  getters: {
    me: (s) => s.group?.members.find((m) => m.is_me) ?? null,
    partner: (s) => s.group?.members.find((m) => !m.is_me) ?? null,
  },
  actions: {
    async fetch() {
      const { data } = await api.get('/group/')
      this.group = data.group
      this.loaded = true
    },
    async create(name) {
      await api.post('/group/', { name })
      await this.fetch()
    },
    async join(inviteCode) {
      await api.post('/group/join/', { invite_code: inviteCode })
      await this.fetch()
    },
    async leave() {
      await api.post('/group/leave/')
      this.group = null
    },
    async updateShare(sharePercent) {
      await api.patch('/group/', { share_percent: sharePercent })
      await this.fetch()
    },
  },
})
