<script setup>
import { computed, onMounted, ref } from 'vue'
import { useStocksStore } from '../stores/stocks'
import { money, pnlClass, signedYen, yen } from '../utils/format'

const stocks = useStocksStore()
const loading = ref(true)

function pct(numerator, denominator) {
  if (!denominator) return null
  return (numerator / denominator) * 100
}

function pctLabel(v) {
  return v == null ? '—' : `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`
}

// 評価額は現在値が登録されている銘柄だけ合算されるため、その分の元本も分けて持つ
const pricedCost = computed(() =>
  stocks.positions
    .filter((p) => p.market_value != null)
    .reduce((sum, p) => sum + p.cost, 0),
)

const totals = computed(() => {
  const cost = stocks.positionTotals.cost
  const market = stocks.positionTotals.market_value
  const unrealized = stocks.positionTotals.unrealized_pnl
  const allTime = stocks.summary?.all_time || { realized: 0, dividends: 0, dividends_foreign: {} }
  const totalReturn = unrealized + allTime.realized + allTime.dividends
  return {
    cost,
    market,
    unrealized,
    unrealizedRate: pct(unrealized, pricedCost.value),
    realized: allTime.realized,
    dividends: allTime.dividends,
    dividendsForeign: allTime.dividends_foreign || {},
    totalReturn,
    totalReturnRate: pct(totalReturn, cost),
  }
})

// 今年の配当利回り (取得元本ベース)
const yearDividends = computed(() => stocks.summary?.dividends || 0)
const dividendYield = computed(() => pct(yearDividends.value, totals.value.cost))

// 銘柄別: 保有 (口座区分をまたいで合算) + 今年の配当
const byCode = computed(() => {
  const map = new Map()
  for (const p of stocks.positions) {
    const row = map.get(p.code) || {
      code: p.code,
      name: p.name,
      cost: 0,
      market: null,
      unrealized: null,
      dividends: 0,
    }
    row.cost += p.cost
    if (p.market_value != null) {
      row.market = (row.market || 0) + p.market_value
      row.unrealized = (row.unrealized || 0) + p.unrealized_pnl
    }
    map.set(p.code, row)
  }
  for (const s of stocks.summary?.by_code || []) {
    const row = map.get(s.code)
    if (row) row.dividends = s.dividends
  }
  const rows = [...map.values()]
  for (const row of rows) {
    row.unrealizedRate = row.unrealized != null ? pct(row.unrealized, row.cost) : null
    row.dividendYield = row.dividends ? pct(row.dividends, row.cost) : null
  }
  rows.sort((a, b) => b.cost - a.cost)
  return rows
})

onMounted(async () => {
  await Promise.all([
    stocks.summary ? Promise.resolve() : stocks.fetchSummary(),
    stocks.fetchPositions(),
  ])
  loading.value = false
})
</script>

<template>
  <div class="page">
    <h1 class="page-title">分析</h1>

    <template v-if="!loading">
      <div class="card">
        <p class="card-title">資産 (現在保有)</p>
        <div class="stat-grid">
          <div class="stat">
            <span class="stat-label">元本 (取得額)</span>
            <span class="stat-value">{{ yen(totals.cost) }}</span>
          </div>
          <div class="stat">
            <span class="stat-label">評価額</span>
            <span class="stat-value">{{ yen(totals.market) }}</span>
          </div>
          <div class="stat">
            <span class="stat-label">評価損益</span>
            <span class="stat-value" :class="pnlClass(totals.unrealized)">
              {{ signedYen(totals.unrealized) }}
              <small>({{ pctLabel(totals.unrealizedRate) }})</small>
            </span>
          </div>
        </div>
        <p v-if="pricedCost < totals.cost" class="note">
          ※ 評価額・評価損益は現在値が登録されている銘柄のみの合計です
        </p>
      </div>

      <div class="card">
        <p class="card-title">累計リターン (全期間)</p>
        <div class="stat-grid">
          <div class="stat">
            <span class="stat-label">売買 (実現損益)</span>
            <span class="stat-value" :class="pnlClass(totals.realized)">{{
              signedYen(totals.realized)
            }}</span>
          </div>
          <div class="stat">
            <span class="stat-label">配当</span>
            <span class="stat-value">{{ yen(totals.dividends) }}</span>
          </div>
          <div class="stat">
            <span class="stat-label">評価損益</span>
            <span class="stat-value" :class="pnlClass(totals.unrealized)">{{
              signedYen(totals.unrealized)
            }}</span>
          </div>
          <div class="stat total">
            <span class="stat-label">トータル</span>
            <span class="stat-value" :class="pnlClass(totals.totalReturn)">
              {{ signedYen(totals.totalReturn) }}
              <small>(元本比 {{ pctLabel(totals.totalReturnRate) }})</small>
            </span>
          </div>
        </div>
        <p v-for="(total, cur) in totals.dividendsForeign" :key="cur" class="note">
          ほかに外貨配当 {{ money(total, cur) }} (円換算せず別枠)
        </p>
      </div>

      <div class="card">
        <p class="card-title">配当利回り ({{ stocks.year }}年・取得元本ベース)</p>
        <p class="yield-value">
          {{ dividendYield != null ? dividendYield.toFixed(2) + '%' : '—' }}
          <small>= 今年の配当 {{ yen(yearDividends) }} ÷ 元本 {{ yen(totals.cost) }}</small>
        </p>
      </div>

      <div class="card">
        <p class="card-title">銘柄別 (保有中)</p>
        <p v-if="byCode.length === 0" class="empty-message">保有銘柄がありません</p>
        <div v-else class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>銘柄</th>
                <th class="num">元本</th>
                <th class="num">評価損益</th>
                <th class="num">配当 ({{ stocks.year }}年)</th>
                <th class="num">利回り</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in byCode" :key="row.code">
                <td>
                  <span class="code">{{ row.code }}</span>
                  {{ row.name }}
                </td>
                <td class="num nowrap">{{ yen(row.cost) }}</td>
                <td class="num nowrap" :class="pnlClass(row.unrealized)">
                  <template v-if="row.unrealized != null">
                    {{ signedYen(row.unrealized) }}
                    <small class="sub-line">{{ pctLabel(row.unrealizedRate) }}</small>
                  </template>
                  <template v-else>—</template>
                </td>
                <td class="num nowrap">{{ row.dividends ? yen(row.dividends) : '—' }}</td>
                <td class="num nowrap">
                  {{ row.dividendYield != null ? row.dividendYield.toFixed(2) + '%' : '—' }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.card-title {
  font-weight: 700;
  margin-bottom: 10px;
}

.stat-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.stat {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.stat.total {
  grid-column: 1 / -1;
  border-top: 1px solid var(--color-border);
  padding-top: 8px;
}

.stat-label {
  font-size: 0.75rem;
  color: var(--color-text-sub);
}

.stat-value {
  font-size: 1.1rem;
  font-weight: 700;
}

.stat-value small {
  font-size: 0.8rem;
  font-weight: 400;
}

.note {
  margin-top: 8px;
  font-size: 0.75rem;
  color: var(--color-text-sub);
}

.yield-value {
  font-size: 1.6rem;
  font-weight: 700;
}

.yield-value small {
  display: block;
  font-size: 0.75rem;
  font-weight: 400;
  color: var(--color-text-sub);
  margin-top: 4px;
}

.table-wrap {
  overflow-x: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
}

th {
  font-size: 0.7rem;
  color: var(--color-text-sub);
  font-weight: 600;
  text-align: left;
  padding: 4px 6px 4px 0;
}

td {
  padding: 8px 6px 8px 0;
  border-top: 1px solid var(--color-border);
}

.num {
  text-align: right;
}

.nowrap {
  white-space: nowrap;
}

.sub-line {
  display: block;
  font-size: 0.7rem;
  color: var(--color-text-sub);
}

.code {
  display: inline-block;
  color: var(--color-text-sub);
  font-size: 0.75rem;
  margin-right: 4px;
}
</style>
