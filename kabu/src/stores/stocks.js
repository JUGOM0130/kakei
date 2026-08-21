import { defineStore } from 'pinia'
import api from '../api/client'

export const useStocksStore = defineStore('stocks', {
  state: () => ({
    year: new Date().getFullYear(),
    summary: null,
    trades: [],
    dividends: [],
    positions: [],
    positionTotals: { cost: 0, market_value: 0, unrealized_pnl: 0 },
  }),
  actions: {
    async fetchSummary() {
      const { data } = await api.get('/stocks/summary/', { params: { year: this.year } })
      this.summary = data
    },
    async fetchTrades(params = {}) {
      const { data } = await api.get('/stocks/trades/', { params })
      this.trades = data
    },
    async saveTrade(payload, id = null) {
      if (id) {
        await api.patch(`/stocks/trades/${id}/`, payload)
      } else {
        await api.post('/stocks/trades/', payload)
      }
    },
    async deleteTrade(id) {
      await api.delete(`/stocks/trades/${id}/`)
      this.trades = this.trades.filter((t) => t.id !== id)
    },
    async fetchDividends(params = {}) {
      const { data } = await api.get('/stocks/dividends/', { params })
      this.dividends = data
    },
    async createDividend(payload) {
      await api.post('/stocks/dividends/', payload)
      await this.fetchDividends()
    },
    async deleteDividend(id) {
      await api.delete(`/stocks/dividends/${id}/`)
      this.dividends = this.dividends.filter((d) => d.id !== id)
    },
    async fetchPositions() {
      const { data } = await api.get('/stocks/positions/')
      this.positions = data.positions
      this.positionTotals = data.totals
    },
    async setPrice(code, price) {
      await api.put(`/stocks/prices/${code}/`, { price })
      await this.fetchPositions()
    },
  },
})
