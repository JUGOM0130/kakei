<script setup>
import { computed, onMounted, ref } from 'vue'
import { useStocksStore } from '../stores/stocks'
import { ACCOUNT_TYPES, accountLabel, dateLabel, pnlClass, signedYen, yen } from '../utils/format'
import { normalizeCode } from '../utils/stockNames'

const stocks = useStocksStore()
const loading = ref(true)

// 絞り込み
const query = ref('')
const sideFilter = ref('') // '' | 'buy' | 'sell'
const accountFilter = ref('')

const filtered = computed(() => {
  const q = query.value.trim()
  const qCode = normalizeCode(q)
  return stocks.trades.filter((t) => {
    if (sideFilter.value && t.side !== sideFilter.value) return false
    if (accountFilter.value && t.account_type !== accountFilter.value) return false
    if (q && !t.name.includes(q) && !t.code.includes(qCode) && !(t.broker || '').includes(q))
      return false
    return true
  })
})

// 月ごとにグループ化して表示
const groups = computed(() => {
  const map = new Map()
  for (const t of filtered.value) {
    const month = t.trade_date.slice(0, 7)
    if (!map.has(month)) map.set(month, [])
    map.get(month).push(t)
  }
  return [...map.entries()].map(([month, items]) => {
    const [y, m] = month.split('-')
    return { month, label: `${y}年${Number(m)}月`, items }
  })
})

async function remove(t) {
  if (!confirm(`${t.code} ${t.name} の${t.side === 'buy' ? '買付' : '売却'}を削除しますか?`)) return
  await stocks.deleteTrade(t.id)
  // 削除で他の行の売却損益が変わるため取り直す
  await stocks.fetchTrades()
}

onMounted(async () => {
  await stocks.fetchTrades()
  loading.value = false
})
</script>

<template>
  <div class="page">
    <div class="title-row">
      <h1 class="page-title">取引履歴</h1>
      <RouterLink to="/import" class="btn btn-secondary btn-small">CSV取込</RouterLink>
    </div>
    <div v-if="stocks.trades.length" class="card filter-card">
      <input
        v-model="query"
        type="text"
        placeholder="銘柄名・コード・証券会社で検索"
        class="search"
      />
      <div class="filter-row">
        <div class="chip-row">
          <button type="button" class="chip chip-mini" :class="{ active: sideFilter === '' }" @click="sideFilter = ''">すべて</button>
          <button type="button" class="chip chip-mini" :class="{ active: sideFilter === 'buy' }" @click="sideFilter = 'buy'">買付</button>
          <button type="button" class="chip chip-mini" :class="{ active: sideFilter === 'sell' }" @click="sideFilter = 'sell'">売却</button>
        </div>
        <select v-model="accountFilter" class="account-select">
          <option value="">全口座</option>
          <option v-for="a in ACCOUNT_TYPES" :key="a.value" :value="a.value">{{ a.label }}</option>
        </select>
      </div>
      <p v-if="query || sideFilter || accountFilter" class="filter-count">
        {{ filtered.length }}件 / {{ stocks.trades.length }}件
      </p>
    </div>

    <p v-if="!loading && stocks.trades.length === 0" class="empty-message">
      まだ取引がありません。＋から登録するか、CSV取込で楽天証券の履歴を読み込めます。
    </p>
    <p v-if="!loading && stocks.trades.length > 0 && filtered.length === 0" class="empty-message">
      条件に一致する取引がありません
    </p>
    <section v-for="group in groups" :key="group.month">
      <h2 class="month-label">{{ group.label }}</h2>
      <div v-for="t in group.items" :key="t.id" class="card trade-card">
        <div class="row1">
          <span class="date">{{ dateLabel(t.trade_date) }}</span>
          <span class="badge" :class="t.side === 'buy' ? 'badge-buy' : 'badge-sell'">
            {{ t.side === 'buy' ? '買付' : '売却' }}
          </span>
          <span class="badge badge-account">{{ accountLabel(t.account_type) }}</span>
          <span v-if="t.broker" class="broker">{{ t.broker }}</span>
        </div>
        <div class="row2">
          <div class="stock">
            <span class="code">{{ t.code }}</span>
            <span class="name">{{ t.name }}</span>
          </div>
          <div class="amount">
            {{ Number(t.quantity).toLocaleString() }}株 × {{ Number(t.price).toLocaleString() }}円
          </div>
        </div>
        <div class="row3">
          <span class="sub">
            約定代金 {{ yen(Math.round(t.quantity * t.price)) }}
            <template v-if="t.fee"> / 手数料 {{ yen(t.fee) }}</template>
          </span>
          <span v-if="t.side === 'sell' && t.realized_pnl != null" :class="pnlClass(t.realized_pnl)">
            {{ signedYen(t.realized_pnl) }}
          </span>
        </div>
        <p v-if="t.memo" class="memo">{{ t.memo }}</p>
        <div class="actions">
          <RouterLink :to="`/trades/${t.id}/edit`" class="btn btn-secondary btn-small">編集</RouterLink>
          <button class="btn btn-secondary btn-small" @click="remove(t)">削除</button>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.title-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.title-row .page-title {
  margin-bottom: 0;
}

.title-row a {
  text-decoration: none;
}

.filter-card {
  padding: 12px;
}

.search {
  margin-bottom: 8px;
}

.filter-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.chip-mini {
  min-height: 36px;
  padding: 4px 12px;
  font-size: 0.85rem;
}

.account-select {
  width: auto;
  min-height: 36px;
  padding: 4px 8px;
  font-size: 0.85rem;
}

.filter-count {
  font-size: 0.75rem;
  color: var(--color-text-sub);
  margin-top: 8px;
}

.month-label {
  font-size: 0.9rem;
  color: var(--color-text-sub);
  margin: 16px 0 8px;
}

.trade-card {
  padding: 12px 16px;
}

.row1 {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.8rem;
  color: var(--color-text-sub);
}

.row2 {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-top: 6px;
  gap: 8px;
}

.stock .code {
  color: var(--color-text-sub);
  font-size: 0.85rem;
  margin-right: 4px;
}

.stock .name {
  font-weight: 700;
}

.amount {
  white-space: nowrap;
}

.row3 {
  display: flex;
  justify-content: space-between;
  margin-top: 4px;
  font-size: 0.85rem;
}

.sub {
  color: var(--color-text-sub);
}

.memo {
  font-size: 0.85rem;
  color: var(--color-text-sub);
  margin-top: 4px;
}

.actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  margin-top: 8px;
}

.actions a {
  text-decoration: none;
}
</style>
