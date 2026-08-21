<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useStocksStore } from '../stores/stocks'
import { dateLabel, yen } from '../utils/format'
import { lookupStockName, normalizeCode } from '../utils/stockNames'

const stocks = useStocksStore()
const loading = ref(true)
const error = ref('')
const saving = ref(false)

const form = ref({
  received_date: new Date().toLocaleDateString('sv-SE'),
  code: '',
  name: '',
  amount: null,
  memo: '',
})

// 銘柄コードを入れたら銘柄マスタから銘柄名を自動補完 (手入力済みは上書きしない)
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

const yearTotal = computed(() => {
  const year = String(new Date().getFullYear())
  return stocks.dividends
    .filter((d) => d.received_date.startsWith(year))
    .reduce((sum, d) => sum + d.amount, 0)
})

async function submit() {
  error.value = ''
  saving.value = true
  try {
    form.value.code = normalizeCode(form.value.code)
    await stocks.createDividend(form.value)
    form.value.code = ''
    form.value.name = ''
    form.value.amount = null
    form.value.memo = ''
  } catch (e) {
    error.value =
      Object.values(e.response?.data || {})
        .flat()
        .join(' ') || '登録に失敗しました。'
  } finally {
    saving.value = false
  }
}

async function remove(d) {
  if (!confirm(`${d.name} の配当 ${yen(d.amount)} を削除しますか?`)) return
  await stocks.deleteDividend(d.id)
}

onMounted(async () => {
  await stocks.fetchDividends()
  loading.value = false
})
</script>

<template>
  <div class="page">
    <h1 class="page-title">配当金</h1>

    <div class="card total-card">
      <span class="label">今年の受取合計 (税引後)</span>
      <span class="value">{{ yen(yearTotal) }}</span>
    </div>

    <form class="card" @submit.prevent="submit">
      <label for="received_date">受取日</label>
      <input id="received_date" v-model="form.received_date" type="date" required />
      <div class="two-col">
        <div>
          <label for="code">銘柄コード</label>
          <input id="code" v-model="form.code" type="text" placeholder="7203" required />
        </div>
        <div>
          <label for="name">銘柄名</label>
          <input id="name" v-model="form.name" type="text" required />
        </div>
      </div>
      <label for="amount">受取額 (税引後・円)</label>
      <input id="amount" v-model.number="form.amount" type="number" min="1" required />
      <label for="memo">メモ (任意)</label>
      <input id="memo" v-model="form.memo" type="text" />
      <p v-if="error" class="error-message">{{ error }}</p>
      <button class="btn submit" type="submit" :disabled="saving">登録する</button>
    </form>

    <p v-if="!loading && stocks.dividends.length === 0" class="empty-message">
      まだ配当の記録がありません
    </p>
    <div v-for="d in stocks.dividends" :key="d.id" class="card dividend-card">
      <div class="row">
        <div>
          <span class="date">{{ d.received_date.slice(0, 4) }}年 {{ dateLabel(d.received_date) }}</span>
          <div>
            <span class="code">{{ d.code }}</span>
            <span class="name">{{ d.name }}</span>
          </div>
          <p v-if="d.memo" class="memo">{{ d.memo }}</p>
        </div>
        <div class="right">
          <span class="amount">{{ yen(d.amount) }}</span>
          <button class="btn btn-secondary btn-small" @click="remove(d)">削除</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.total-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.total-card .label {
  font-size: 0.85rem;
  color: var(--color-text-sub);
}

.total-card .value {
  font-size: 1.4rem;
  font-weight: 700;
}

.two-col {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.submit {
  margin-top: 20px;
}

.dividend-card {
  padding: 12px 16px;
}

.row {
  display: flex;
  justify-content: space-between;
  gap: 8px;
}

.date {
  font-size: 0.8rem;
  color: var(--color-text-sub);
}

.code {
  color: var(--color-text-sub);
  font-size: 0.85rem;
  margin-right: 4px;
}

.name {
  font-weight: 700;
}

.memo {
  font-size: 0.85rem;
  color: var(--color-text-sub);
  margin-top: 2px;
}

.right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 6px;
}

.amount {
  font-weight: 700;
}
</style>
