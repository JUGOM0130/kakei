<script setup>
import { onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api/client'
import { useStocksStore } from '../stores/stocks'
import { ACCOUNT_TYPES } from '../utils/format'
import { lookupStockName, normalizeCode } from '../utils/stockNames'

const props = defineProps({ id: { type: String, default: null } })
const router = useRouter()
const stocks = useStocksStore()

const form = ref({
  side: 'buy',
  trade_date: new Date().toLocaleDateString('sv-SE'), // YYYY-MM-DD
  code: '',
  name: '',
  quantity: null,
  price: null,
  fee: 0,
  account_type: 'tokutei',
  broker: '',
  memo: '',
})
const error = ref('')
const loading = ref(false)

// 銘柄コードを入れたら銘柄マスタ (JPX 上場一覧) から銘柄名を、
// 過去の取引から証券会社・口座区分を自動補完
const autoName = ref('')
watch(
  () => form.value.code,
  async (code) => {
    if (props.id) return
    const c = normalizeCode(code)
    if (!c) return
    const past = stocks.trades.find((t) => t.code === c)
    if (past) {
      if (!form.value.broker) form.value.broker = past.broker
      form.value.account_type = past.account_type
    }
    // 手入力済みの銘柄名は上書きしない (自動補完した値だけ差し替え可)
    if (form.value.name && form.value.name !== autoName.value) return
    const name = (await lookupStockName(c)) || past?.name
    if (name && (!form.value.name || form.value.name === autoName.value)) {
      form.value.name = name
      autoName.value = name
    }
  },
)

async function submit() {
  error.value = ''
  loading.value = true
  try {
    form.value.code = normalizeCode(form.value.code)
    await stocks.saveTrade(form.value, props.id)
    router.push('/trades')
  } catch (e) {
    const data = e.response?.data
    error.value =
      Object.values(data || {})
        .flat()
        .join(' ') || '保存に失敗しました。'
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  if (stocks.trades.length === 0) stocks.fetchTrades().catch(() => {})
  if (props.id) {
    const { data } = await api.get(`/stocks/trades/${props.id}/`)
    form.value = { ...data }
  }
})
</script>

<template>
  <div class="page">
    <h1 class="page-title">{{ props.id ? '取引を編集' : '取引を登録' }}</h1>
    <form class="card" @submit.prevent="submit">
      <div class="chip-row side-row">
        <button
          type="button"
          class="chip"
          :class="{ active: form.side === 'buy' }"
          @click="form.side = 'buy'"
        >
          買付
        </button>
        <button
          type="button"
          class="chip"
          :class="{ active: form.side === 'sell' }"
          @click="form.side = 'sell'"
        >
          売却
        </button>
      </div>

      <label for="trade_date">約定日</label>
      <input id="trade_date" v-model="form.trade_date" type="date" required />

      <div class="two-col">
        <div>
          <label for="code">銘柄コード</label>
          <input id="code" v-model="form.code" type="text" placeholder="7203" required />
        </div>
        <div>
          <label for="name">銘柄名</label>
          <input id="name" v-model="form.name" type="text" placeholder="トヨタ自動車" required />
        </div>
      </div>

      <div class="two-col">
        <div>
          <label for="quantity">株数</label>
          <input id="quantity" v-model.number="form.quantity" type="number" min="1" required />
        </div>
        <div>
          <label for="price">単価 (円)</label>
          <input
            id="price"
            v-model.number="form.price"
            type="number"
            min="0"
            step="0.0001"
            required
          />
        </div>
      </div>

      <label for="fee">手数料 (円)</label>
      <input id="fee" v-model.number="form.fee" type="number" min="0" />

      <label>口座区分</label>
      <div class="chip-row">
        <button
          v-for="a in ACCOUNT_TYPES"
          :key="a.value"
          type="button"
          class="chip"
          :class="{ active: form.account_type === a.value }"
          @click="form.account_type = a.value"
        >
          {{ a.label }}
        </button>
      </div>

      <label for="broker">証券会社 (任意)</label>
      <input id="broker" v-model="form.broker" type="text" placeholder="楽天証券" />

      <label for="memo">メモ (任意)</label>
      <input id="memo" v-model="form.memo" type="text" />

      <p v-if="error" class="error-message">{{ error }}</p>
      <button class="btn submit" type="submit" :disabled="loading">
        {{ props.id ? '保存する' : '登録する' }}
      </button>
    </form>
  </div>
</template>

<style scoped>
.side-row {
  margin-bottom: 4px;
}

.side-row .chip {
  flex: 1;
  justify-content: center;
}

.two-col {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.submit {
  margin-top: 20px;
}
</style>
