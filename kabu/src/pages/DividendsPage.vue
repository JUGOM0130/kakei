<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useStocksStore } from '../stores/stocks'
import KnownCodesDatalist from '../components/KnownCodesDatalist.vue'
import { dateLabel, money, yen } from '../utils/format'
import { lookupStockName, normalizeCode } from '../utils/stockNames'

const stocks = useStocksStore()
const loading = ref(true)
const error = ref('')
const saving = ref(false)
const editingId = ref(null)

function emptyForm() {
  return {
    received_date: new Date().toLocaleDateString('sv-SE'),
    code: '',
    name: '',
    currency: '円',
    shares: null,
    gross_amount: null,
    tax_national: null,
    tax_local: null,
    amount: null,
    memo: '',
  }
}

const form = ref(emptyForm())

// 銘柄コードを入れたら銘柄マスタから銘柄名を自動補完 (手入力済みは上書きしない)
const autoName = ref('')
watch(
  () => form.value.code,
  async (code) => {
    if (form.value.name && form.value.name !== autoName.value) return
    const name = (await lookupStockName(code)) || stocks.knownName(normalizeCode(code))
    if (name && (!form.value.name || form.value.name === autoName.value)) {
      form.value.name = name
      autoName.value = name
    }
  },
)

// 税引前と源泉徴収を入れたら税引後を自動計算 (税引後だけの手入力も可)
// 履歴コピー・編集でフォームへ流し込む時は保存済みの税引後額を尊重して計算しない
const suppressAutoCalc = ref(false)
watch(
  () => [form.value.gross_amount, form.value.tax_national, form.value.tax_local],
  ([gross, national, local]) => {
    if (suppressAutoCalc.value) return
    if (typeof gross !== 'number') return
    form.value.amount = Math.max(0, gross - (national || 0) - (local || 0))
  },
)

const yearTotal = computed(() => {
  const year = String(new Date().getFullYear())
  return stocks.dividends
    .filter((d) => d.received_date.startsWith(year) && (!d.currency || d.currency === '円'))
    .reduce((sum, d) => sum + d.amount, 0)
})

// 外貨建て配当の今年の合計 (通貨別)。円と合算できないため別枠で表示する
const yearForeignTotals = computed(() => {
  const year = String(new Date().getFullYear())
  const map = new Map()
  for (const d of stocks.dividends) {
    if (!d.received_date.startsWith(year) || !d.currency || d.currency === '円') continue
    map.set(d.currency, (map.get(d.currency) || 0) + d.amount)
  }
  return [...map.entries()]
})

function numOrNull(v) {
  return typeof v === 'number' ? v : null
}

async function submit() {
  error.value = ''
  saving.value = true
  try {
    const payload = {
      received_date: form.value.received_date,
      code: normalizeCode(form.value.code),
      name: form.value.name,
      currency: form.value.currency || '円',
      shares: numOrNull(form.value.shares),
      gross_amount: numOrNull(form.value.gross_amount),
      tax_national: numOrNull(form.value.tax_national),
      tax_local: numOrNull(form.value.tax_local),
      amount: form.value.amount,
      memo: form.value.memo,
    }
    if (editingId.value) {
      await stocks.updateDividend(editingId.value, payload)
    } else {
      await stocks.createDividend(payload)
    }
    resetForm()
  } catch (e) {
    error.value =
      Object.values(e.response?.data || {})
        .flat()
        .join(' ') || '登録に失敗しました。'
  } finally {
    saving.value = false
  }
}

function resetForm() {
  form.value = emptyForm()
  editingId.value = null
  autoName.value = ''
  error.value = ''
}

function fillForm(d) {
  autoName.value = ''
  suppressAutoCalc.value = true
  form.value = {
    received_date: d.received_date,
    code: d.code,
    name: d.name,
    currency: d.currency || '円',
    shares: d.shares,
    gross_amount: d.gross_amount,
    tax_national: d.tax_national,
    tax_local: d.tax_local,
    amount: d.amount,
    memo: d.memo,
  }
  window.scrollTo({ top: 0, behavior: 'smooth' })
  nextTick(() => {
    suppressAutoCalc.value = false
  })
}

// 履歴タップ → 新規入力欄に内容をコピー (受取日は今日にする)
function copyToForm(d) {
  fillForm(d)
  form.value.received_date = new Date().toLocaleDateString('sv-SE')
  editingId.value = null
}

function startEdit(d) {
  fillForm(d)
  editingId.value = d.id
}

async function remove(d) {
  if (!confirm(`${d.name} の配当 ${money(d.amount, d.currency)} を削除しますか?`)) return
  await stocks.deleteDividend(d.id)
  if (editingId.value === d.id) resetForm()
}

function taxTotal(d) {
  return (d.tax_national || 0) + (d.tax_local || 0)
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
      <span class="value-wrap">
        <span class="value">{{ yen(yearTotal) }}</span>
        <span v-for="[cur, total] in yearForeignTotals" :key="cur" class="foreign">
          + {{ money(total, cur) }}
        </span>
      </span>
    </div>

    <form class="card" @submit.prevent="submit">
      <p v-if="editingId" class="editing-banner">
        登録済みの配当を編集中です
        <button type="button" class="btn btn-secondary btn-small" @click="resetForm">
          やめる
        </button>
      </p>
      <label for="received_date">受取日</label>
      <input id="received_date" v-model="form.received_date" type="date" required />
      <div class="two-col">
        <div>
          <label for="code">銘柄コード</label>
          <input id="code" v-model="form.code" type="text" placeholder="7203" list="known-codes" required />
          <KnownCodesDatalist />
        </div>
        <div>
          <label for="name">銘柄名</label>
          <input id="name" v-model="form.name" type="text" required />
        </div>
      </div>
      <div class="two-col">
        <div>
          <label for="shares">配当対象株数 (任意)</label>
          <input id="shares" v-model.number="form.shares" type="number" min="1" />
        </div>
        <div>
          <label for="currency">受取通貨</label>
          <select id="currency" v-model="form.currency">
            <option value="円">円</option>
            <option value="USドル">USドル</option>
            <option v-if="form.currency !== '円' && form.currency !== 'USドル'" :value="form.currency">
              {{ form.currency }}
            </option>
          </select>
        </div>
      </div>
      <label for="gross_amount">配当金 (税引前) — NISAなど非課税なら空欄でOK</label>
      <input id="gross_amount" v-model.number="form.gross_amount" type="number" min="0" step="any" />
      <div class="two-col">
        <div>
          <label for="tax_national">源泉徴収 国税</label>
          <input id="tax_national" v-model.number="form.tax_national" type="number" min="0" step="any" />
        </div>
        <div>
          <label for="tax_local">源泉徴収 地方税</label>
          <input id="tax_local" v-model.number="form.tax_local" type="number" min="0" step="any" />
        </div>
      </div>
      <label for="amount">受取額 (税引後) — 税引前を入れると自動計算</label>
      <input id="amount" v-model.number="form.amount" type="number" min="0" step="any" required />
      <label for="memo">メモ (任意)</label>
      <input id="memo" v-model="form.memo" type="text" />
      <p v-if="error" class="error-message">{{ error }}</p>
      <button class="btn submit" type="submit" :disabled="saving">
        {{ editingId ? '変更を保存する' : '登録する' }}
      </button>
    </form>

    <p v-if="!loading && stocks.dividends.length === 0" class="empty-message">
      まだ配当の記録がありません
    </p>
    <p v-if="stocks.dividends.length > 0" class="tap-hint">
      履歴をタップすると内容を入力欄にコピーできます
    </p>
    <div
      v-for="d in stocks.dividends"
      :key="d.id"
      class="card dividend-card"
      :class="{ editing: d.id === editingId }"
      @click="copyToForm(d)"
    >
      <div class="row">
        <div>
          <span class="date">{{ d.received_date.slice(0, 4) }}年 {{ dateLabel(d.received_date) }}</span>
          <div>
            <span class="code">{{ d.code }}</span>
            <span class="name">{{ d.name }}</span>
            <span v-if="d.shares" class="shares">{{ d.shares }}株</span>
          </div>
          <p v-if="d.gross_amount != null" class="tax-detail">
            税引前 {{ money(d.gross_amount, d.currency) }}
            <template v-if="taxTotal(d) > 0">
              / 源泉 {{ money(taxTotal(d), d.currency) }}<template v-if="d.tax_local">
                (国税 {{ yen(d.tax_national || 0) }}・地方税 {{ yen(d.tax_local || 0) }})</template>
            </template>
          </p>
          <p v-if="d.memo" class="memo">{{ d.memo }}</p>
        </div>
        <div class="right">
          <span class="amount">{{ money(d.amount, d.currency) }}</span>
          <div class="actions">
            <button class="btn btn-secondary btn-small" @click.stop="startEdit(d)">編集</button>
            <button class="btn btn-secondary btn-small" @click.stop="remove(d)">削除</button>
          </div>
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

.total-card .value-wrap {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}

.total-card .value {
  font-size: 1.4rem;
  font-weight: 700;
}

.total-card .foreign {
  font-size: 0.85rem;
  color: var(--color-text-sub);
}

.two-col {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.editing-banner {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  background: var(--color-bg, #f5f5f5);
  border-radius: 8px;
  padding: 8px 12px;
  font-size: 0.85rem;
  font-weight: 700;
  margin-bottom: 12px;
}

.submit {
  margin-top: 20px;
}

.tap-hint {
  font-size: 0.8rem;
  color: var(--color-text-sub);
  margin: 4px 2px 8px;
}

.dividend-card {
  padding: 12px 16px;
  cursor: pointer;
}

.dividend-card.editing {
  outline: 2px solid var(--color-primary, #4a90d9);
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

.shares {
  font-size: 0.85rem;
  color: var(--color-text-sub);
  margin-left: 6px;
}

.tax-detail {
  font-size: 0.8rem;
  color: var(--color-text-sub);
  margin-top: 2px;
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

.actions {
  display: flex;
  gap: 6px;
}

.amount {
  font-weight: 700;
}
</style>
