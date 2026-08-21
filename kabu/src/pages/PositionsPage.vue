<script setup>
import { onMounted, ref } from 'vue'
import { useStocksStore } from '../stores/stocks'
import { accountLabel, pnlClass, signedYen, yen } from '../utils/format'

const stocks = useStocksStore()
const loading = ref(true)
const priceInputs = ref({})
const saving = ref('')

async function savePrice(row) {
  const price = priceInputs.value[row.code]
  if (!price) return
  saving.value = row.code
  try {
    await stocks.setPrice(row.code, price)
  } finally {
    saving.value = ''
  }
}

onMounted(async () => {
  await stocks.fetchPositions()
  for (const row of stocks.positions) {
    if (row.current_price != null) priceInputs.value[row.code] = row.current_price
  }
  loading.value = false
})
</script>

<template>
  <div class="page">
    <h1 class="page-title">保有一覧</h1>

    <div v-if="stocks.positions.length" class="card totals">
      <div>
        <span class="label">取得額合計</span>
        <span>{{ yen(stocks.positionTotals.cost) }}</span>
      </div>
      <div v-if="stocks.positionTotals.market_value">
        <span class="label">評価額</span>
        <span>{{ yen(stocks.positionTotals.market_value) }}</span>
      </div>
      <div v-if="stocks.positionTotals.market_value">
        <span class="label">評価損益</span>
        <span :class="pnlClass(stocks.positionTotals.unrealized_pnl)">
          {{ signedYen(stocks.positionTotals.unrealized_pnl) }}
        </span>
      </div>
    </div>

    <p v-if="!loading && stocks.positions.length === 0" class="empty-message">
      保有中の銘柄はありません
    </p>

    <div v-for="row in stocks.positions" :key="row.code + row.account_type" class="card">
      <div class="head">
        <div>
          <span class="code">{{ row.code }}</span>
          <span class="name">{{ row.name }}</span>
        </div>
        <span class="badge badge-account">{{ accountLabel(row.account_type) }}</span>
      </div>
      <div class="grid">
        <div>
          <span class="label">株数</span>
          <span>{{ row.quantity.toLocaleString() }}株</span>
        </div>
        <div>
          <span class="label">平均取得単価</span>
          <span>{{ row.avg_price.toLocaleString() }}円</span>
        </div>
        <div>
          <span class="label">取得額</span>
          <span>{{ yen(row.cost) }}</span>
        </div>
        <div v-if="row.unrealized_pnl != null">
          <span class="label">評価損益</span>
          <span :class="pnlClass(row.unrealized_pnl)">{{ signedYen(row.unrealized_pnl) }}</span>
        </div>
      </div>
      <div class="price-row">
        <input
          v-model.number="priceInputs[row.code]"
          type="number"
          min="0"
          step="0.0001"
          placeholder="現在値を入力すると評価損益を表示"
        />
        <button
          class="btn btn-small"
          :disabled="saving === row.code || !priceInputs[row.code]"
          @click="savePrice(row)"
        >
          更新
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.totals {
  display: flex;
  justify-content: space-around;
  text-align: center;
}

.totals > div {
  display: flex;
  flex-direction: column;
}

.label {
  display: block;
  font-size: 0.75rem;
  color: var(--color-text-sub);
}

.head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.code {
  color: var(--color-text-sub);
  font-size: 0.85rem;
  margin-right: 4px;
}

.name {
  font-weight: 700;
}

.grid {
  display: grid;
  grid-template-columns: repeat(4, auto);
  justify-content: space-between;
  gap: 8px;
  font-size: 0.95rem;
}

.price-row {
  display: flex;
  gap: 8px;
  margin-top: 12px;
}

.price-row input {
  flex: 1;
}
</style>
