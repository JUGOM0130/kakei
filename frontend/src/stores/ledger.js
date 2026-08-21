import { defineStore } from 'pinia'
import dayjs from 'dayjs'
import api from '../api/client'

export const useLedgerStore = defineStore('ledger', {
  state: () => ({
    month: dayjs().format('YYYY-MM'),
    summary: null,
    transactions: [],
    categories: [],
    recurring: [],
    paymentMethods: [],
  }),
  actions: {
    prevMonth() {
      this.month = dayjs(this.month + '-01').subtract(1, 'month').format('YYYY-MM')
    },
    nextMonth() {
      this.month = dayjs(this.month + '-01').add(1, 'month').format('YYYY-MM')
    },
    async fetchSummary() {
      const { data } = await api.get('/summary/monthly/', { params: { month: this.month } })
      this.summary = data
    },
    async fetchTransactions(params = {}) {
      const { data } = await api.get('/transactions/', {
        params: { month: this.month, ...params },
      })
      this.transactions = data
    },
    async fetchCategories(force = false) {
      if (this.categories.length && !force) return
      const { data } = await api.get('/categories/')
      this.categories = data
    },
    async fetchRecurring() {
      const { data } = await api.get('/recurring-payments/')
      this.recurring = data
    },
    async fetchPaymentMethods(force = false) {
      if (this.paymentMethods.length && !force) return
      const { data } = await api.get('/payment-methods/')
      this.paymentMethods = data
    },
    async pay(id) {
      await api.post(`/recurring-payments/${id}/pay/`, { month: this.month })
      await this.fetchSummary()
    },
    async settle() {
      await api.post('/settlements/', { month: this.month })
      await this.fetchSummary()
    },
    async unsettle(id) {
      await api.delete(`/settlements/${id}/`)
      await this.fetchSummary()
    },
  },
})
