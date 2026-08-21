<script setup>
import { onMounted, ref, watch } from 'vue'
import { useStocksStore } from '../stores/stocks'
import SettlementMonthSelect from '../components/SettlementMonthSelect.vue'
import { timeLabel } from '../utils/format'
import { lookupStockName, normalizeCode } from '../utils/stockNames'

const stocks = useStocksStore()
const loading = ref(true)
const error = ref('')
const saving = ref(false)
const targetInputs = ref({})

const form = ref({ code: '', name: '', kind: 'buy', target_price: null, memo: '' })

// 銘柄コード → 銘柄名の自動補完
const autoName = ref('')
watch(
  () => form.value.code,
  async (code) => {
    if (form.value.name && form.value.name !== autoName.value) return
    const name = await lookupStockName(code)
    if (name && (!form.value.name || form.value.name === autoName.value)) {
      form.value.name = name
      autoName.value = name
    }
  },
)

async function submit() {
  error.value = ''
  saving.value = true
  try {
    form.value.code = normalizeCode(form.value.code)
    await stocks.createWatch(form.value)
    form.value = { code: '', name: '', kind: form.value.kind, target_price: null, memo: '' }
    autoName.value = ''
    refresh().catch(() => {})
  } catch (e) {
    error.value =
      Object.values(e.response?.data || {})
        .flat()
        .join(' ') || '登録に失敗しました。'
  } finally {
    saving.value = false
  }
}

async function refresh() {
  await stocks.refreshPrices()
  await stocks.fetchWatches()
}

async function saveTarget(w) {
  const price = targetInputs.value[w.id]
  if (!price) return
  await stocks.updateWatch(w.id, { target_price: price })
  targetInputs.value[w.id] = null
}

async function remove(w) {
  if (!confirm(`${w.name} のウォッチを削除しますか?`)) return
  await stocks.deleteWatch(w.id)
}

onMounted(async () => {
  await stocks.fetchWatches()
  loading.value = false
  refresh().catch(() => {})
})
</script>

<template>
  <div class="page">
    <div class="title-row">
      <h1 class="page-title">ウォッチ</h1>
      <button class="btn btn-secondary btn-small" :disabled="stocks.refreshing" @click="refresh">
        {{ stocks.refreshing ? '取得中…' : '株価更新' }}
      </button>
    </div>

    <form class="card" @submit.prevent="submit">
      <div class="chip-row kind-row">
        <button
          type="button"
          class="chip"
          :class="{ active: form.kind === 'buy' }"
          @click="form.kind = 'buy'"
        >
          この価格まで下がったら買い
        </button>
        <button
          type="button"
          class="chip"
          :class="{ active: form.kind === 'sell' }"
          @click="form.kind = 'sell'"
        >
          この価格まで上がったら売り
        </button>
      </div>
      <div class="two-col">
        <div>
          <label for="w-code">銘柄コード</label>
          <input id="w-code" v-model="form.code" type="text" placeholder="7203" required />
        </div>
        <div>
          <label for="w-name">銘柄名</label>
          <input id="w-name" v-model="form.name" type="text" required />
        </div>
      </div>
      <label for="w-target">目標価格 (円)</label>
      <input
        id="w-target"
        v-model.number="form.target_price"
        type="number"
        min="0"
        step="0.0001"
        required
      />
      <label for="w-memo">メモ (任意)</label>
      <input id="w-memo" v-model="form.memo" type="text" placeholder="例: 決算後に押したら" />
      <p v-if="error" class="error-message">{{ error }}</p>
      <button class="btn submit" type="submit" :disabled="saving">登録する</button>
    </form>

    <p v-if="!loading && stocks.watches.length === 0" class="empty-message">
      ウォッチ中の銘柄はありません
    </p>

    <div
      v-for="w in stocks.watches"
      :key="w.id"
      class="card watch-card"
      :class="{ reached: w.reached }"
    >
      <div class="head">
        <div>
          <span class="code">{{ w.code }}</span>
          <span class="name">{{ w.name }}</span>
        </div>
        <span v-if="w.reached" class="badge badge-reached">
          {{ w.kind === 'buy' ? '買いチャンス!' : '売りチャンス!' }}
        </span>
        <span v-else class="badge badge-account">{{ w.kind === 'buy' ? '買い目標' : '売り目標' }}</span>
      </div>
      <div class="grid">
        <div>
          <span class="label">目標</span>
          <span>{{ Number(w.target_price).toLocaleString() }}円{{ w.kind === 'buy' ? '以下' : '以上' }}</span>
        </div>
        <div>
          <span class="label">現在値</span>
          <span v-if="w.current_price != null" :class="w.reached ? 'gain' : ''">
            {{ w.current_price.toLocaleString() }}円
          </span>
          <span v-else>—</span>
        </div>
        <div v-if="w.current_price != null">
          <span class="label">目標まで</span>
          <span>{{ Math.abs(w.current_price - w.target_price).toLocaleString() }}円</span>
        </div>
      </div>
      <p v-if="w.memo" class="memo">{{ w.memo }}</p>
      <p v-if="w.price_updated_at" class="time">株価: {{ timeLabel(w.price_updated_at) }} 時点</p>
      <div class="foot">
        <SettlementMonthSelect :code="w.code" :month="w.settlement_month" />
        <div class="edit-row">
          <input
            v-model.number="targetInputs[w.id]"
            type="number"
            min="0"
            step="0.0001"
            placeholder="目標変更"
          />
          <button class="btn btn-secondary btn-small" :disabled="!targetInputs[w.id]" @click="saveTarget(w)">
            変更
          </button>
          <button class="btn btn-secondary btn-small" @click="remove(w)">削除</button>
        </div>
      </div>
    </div>
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

.kind-row {
  margin-bottom: 4px;
}

.kind-row .chip {
  flex: 1;
  justify-content: center;
  font-size: 0.8rem;
  padding: 8px 6px;
}

.two-col {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.submit {
  margin-top: 20px;
}

.watch-card.reached {
  border: 2px solid var(--color-gain);
}

.head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  gap: 8px;
}

.code {
  color: var(--color-text-sub);
  font-size: 0.85rem;
  margin-right: 4px;
}

.name {
  font-weight: 700;
}

.badge-reached {
  background: #e8f5e9;
  color: var(--color-gain);
}

.grid {
  display: grid;
  grid-template-columns: repeat(3, auto);
  justify-content: space-between;
  gap: 8px;
  font-size: 0.95rem;
}

.label {
  display: block;
  font-size: 0.75rem;
  color: var(--color-text-sub);
}

.memo {
  font-size: 0.85rem;
  color: var(--color-text-sub);
  margin-top: 6px;
}

.time {
  font-size: 0.7rem;
  color: var(--color-text-sub);
  margin-top: 4px;
}

.foot {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
  flex-wrap: wrap;
}

.edit-row {
  display: flex;
  gap: 6px;
}

.edit-row input {
  width: 110px;
  min-height: 36px;
  padding: 4px 8px;
  font-size: 0.85rem;
}
</style>
