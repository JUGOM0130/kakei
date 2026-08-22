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
    watches: [],
    refreshing: false,
    priceFailed: [],
    // 過去に取引・配当のある銘柄 (入力候補用、最近使った順)
    knownStocks: [],
  }),
  getters: {
    knownName: (state) => (code) =>
      state.knownStocks.find((s) => s.code === code)?.name || null,
  },
  actions: {
    async fetchKnownStocks() {
      const { data } = await api.get('/stocks/codes/')
      this.knownStocks = data
    },
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
    async updateDividend(id, payload) {
      await api.patch(`/stocks/dividends/${id}/`, payload)
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
    // 保有中 + ウォッチ中の銘柄の株価を API から取得して反映する
    async refreshPrices() {
      this.refreshing = true
      try {
        const { data } = await api.post('/stocks/prices/refresh/', {})
        this.priceFailed = data.failed
      } finally {
        this.refreshing = false
      }
    },
    async fetchWatches() {
      const { data } = await api.get('/stocks/watches/')
      this.watches = data
    },
    async createWatch(payload) {
      await api.post('/stocks/watches/', payload)
      await this.fetchWatches()
    },
    async updateWatch(id, payload) {
      await api.patch(`/stocks/watches/${id}/`, payload)
      await this.fetchWatches()
    },
    async deleteWatch(id) {
      await api.delete(`/stocks/watches/${id}/`)
      this.watches = this.watches.filter((w) => w.id !== id)
    },
    // 決算月の設定 (保有・ウォッチ両方に反映)
    async setSettlementMonth(code, month) {
      await api.put(`/stocks/info/${code}/`, { settlement_month: month })
      this.positions = this.positions.map((p) =>
        p.code === code ? { ...p, settlement_month: month } : p,
      )
      this.watches = this.watches.map((w) =>
        w.code === code ? { ...w, settlement_month: month } : w,
      )
    },
  },
})
