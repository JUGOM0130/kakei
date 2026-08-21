<script setup>
import { computed, onMounted, ref } from 'vue'
import { useStocksStore } from '../stores/stocks'
import SettlementMonthSelect from '../components/SettlementMonthSelect.vue'
import { accountLabel, pnlClass, signedYen, timeLabel, yen } from '../utils/format'

const stocks = useStocksStore()
const loading = ref(true)
const priceInputs = ref({})
const saving = ref('')

const priceTime = computed(() => {
  const times = stocks.positions.map((p) => p.price_updated_at).filter(Boolean)
  return times.length ? timeLabel(times.sort().at(-1)) : ''
})

async function refresh() {
  await stocks.refreshPrices()
  await stocks.fetchPositions()
}

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
  loading.value = false
  // 表示後にバックグラウンドで株価を最新化
  refresh().catch(() => {})
})
</script>

<template>
  <div class="page">
    <div class="title-row">
      <h1 class="page-title">保有一覧</h1>
      <button class="btn btn-secondary btn-small" :disabled="stocks.refreshing" @click="refresh">
        {{ stocks.refreshing ? '取得中…' : '株価更新' }}
      </button>
    </div>
    <p v-if="priceTime" class="price-time">株価: {{ priceTime }} 時点 (Yahoo!ファイナンス)</p>

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
          <span class="label">現在値</span>
          <span v-if="row.current_price != null">{{ row.current_price.toLocaleString() }}円</span>
          <span v-else>—</span>
        </div>
        <div>
          <span class="label">評価損益</span>
          <span v-if="row.unrealized_pnl != null" :class="pnlClass(row.unrealized_pnl)">
            {{ signedYen(row.unrealized_pnl) }}
          </span>
          <span v-else>—</span>
        </div>
      </div>
      <div class="foot">
        <span class="sub">取得額 {{ yen(row.cost) }}<template v-if="row.market_value != null"> / 評価額 {{ yen(row.market_value) }}</template></span>
        <SettlementMonthSelect :code="row.code" :month="row.settlement_month" />
      </div>
      <!-- 株価を自動取得できなかった銘柄だけ手動入力を出す -->
      <div v-if="row.current_price == null || stocks.priceFailed.includes(row.code)" class="price-row">
        <input
          v-model.number="priceInputs[row.code]"
          type="number"
          min="0"
          step="0.0001"
          placeholder="自動取得できないため現在値を手入力"
        />
        <button
          class="btn btn-small"
          :disabled="saving === row.code || !priceInputs[row.code]"
          @click="savePrice(row)"
        >
          保存
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.title-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.title-row .page-title {
  margin-bottom: 0;
}

.price-time {
  font-size: 0.75rem;
  color: var(--color-text-sub);
  margin-bottom: 12px;
}

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

.foot {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 10px;
}

.sub {
  font-size: 0.8rem;
  color: var(--color-text-sub);
}

.price-row {
  display: flex;
  gap: 8px;
  margin-top: 10px;
}

.price-row input {
  flex: 1;
}
</style>
