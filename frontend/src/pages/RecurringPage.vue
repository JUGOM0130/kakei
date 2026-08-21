<script setup>
import { computed, onMounted, ref } from 'vue'
import dayjs from 'dayjs'
import api from '../api/client'
import { useLedgerStore } from '../stores/ledger'
import { useGroupStore } from '../stores/group'
import AmountInput from '../components/AmountInput.vue'
import { yen } from '../utils/format'

const ledger = useLedgerStore()
const groupStore = useGroupStore()

const INTERVALS = [
  { value: 1, label: '毎月' },
  { value: 2, label: '2ヶ月ごと' },
  { value: 3, label: '3ヶ月ごと' },
  { value: 4, label: '4ヶ月ごと' },
  { value: 6, label: '半年ごと' },
  { value: 12, label: '毎年' },
]

const editing = ref(null) // null=閉じる, 'new'=新規, number=編集中ID
const name = ref('')
const amount = ref('')
const categoryId = ref(null)
const paymentMethodId = ref(null)
const dayOfMonth = ref(1)
const intervalMonths = ref(1)
const anchorMonth = ref(dayjs().format('YYYY-MM'))
const isShared = ref(false)
const sharePercent = ref(50)
const memo = ref('')
const error = ref('')

const expenseCategories = computed(() =>
  ledger.categories.filter((c) => c.type === 'expense')
)

const hasGroup = computed(() => !!groupStore.group)
const partnerName = computed(() => groupStore.partner?.username ?? '相手')

const monthlyEquivalent = computed(() =>
  ledger.recurring
    .filter((r) => r.is_active)
    .reduce((sum, r) => sum + Math.round(r.amount / r.interval_months), 0)
)

function intervalLabel(r) {
  return INTERVALS.find((i) => i.value === r.interval_months)?.label ?? `${r.interval_months}ヶ月ごと`
}

onMounted(async () => {
  await Promise.all([
    ledger.fetchCategories(),
    ledger.fetchRecurring(),
    ledger.fetchPaymentMethods(),
    groupStore.loaded ? Promise.resolve() : groupStore.fetch(),
  ])
  if (groupStore.me) sharePercent.value = groupStore.me.share_percent
})

function openNew() {
  editing.value = 'new'
  name.value = ''
  amount.value = ''
  categoryId.value = expenseCategories.value[0]?.id ?? null
  paymentMethodId.value = null
  dayOfMonth.value = 1
  intervalMonths.value = 1
  anchorMonth.value = dayjs().format('YYYY-MM')
  isShared.value = false
  sharePercent.value = groupStore.me?.share_percent ?? 50
  memo.value = ''
  error.value = ''
}

function openEdit(item) {
  editing.value = item.id
  name.value = item.name
  amount.value = String(item.amount)
  categoryId.value = item.category.id
  paymentMethodId.value = item.payment_method?.id ?? null
  dayOfMonth.value = item.day_of_month
  intervalMonths.value = item.interval_months
  anchorMonth.value = item.anchor_month
    ? item.anchor_month.slice(0, 7)
    : dayjs().format('YYYY-MM')
  isShared.value = item.is_shared
  sharePercent.value = item.payer_share_percent
  memo.value = item.memo
  error.value = ''
}

async function save() {
  error.value = ''
  if (!name.value || !Number(amount.value) || !categoryId.value) {
    error.value = '名前・金額・カテゴリを入力してください。'
    return
  }
  const payload = {
    name: name.value,
    amount: Number(amount.value),
    category_id: categoryId.value,
    payment_method_id: paymentMethodId.value,
    day_of_month: Number(dayOfMonth.value),
    interval_months: Number(intervalMonths.value),
    anchor_month: Number(intervalMonths.value) > 1 ? anchorMonth.value + '-01' : null,
    is_shared: isShared.value,
    payer_share_percent: Number(sharePercent.value),
    memo: memo.value,
  }
  try {
    if (editing.value === 'new') {
      await api.post('/recurring-payments/', payload)
    } else {
      await api.patch(`/recurring-payments/${editing.value}/`, payload)
    }
    editing.value = null
    await ledger.fetchRecurring()
  } catch (e) {
    const data = e.response?.data
    error.value =
      data?.anchor_month?.[0] || data?.is_shared?.[0] || data?.detail || '保存に失敗しました。'
  }
}

async function toggleActive(item) {
  await api.patch(`/recurring-payments/${item.id}/`, { is_active: !item.is_active })
  await ledger.fetchRecurring()
}

async function remove(item) {
  if (!confirm(`「${item.name}」を削除しますか?\n(過去の支払記録は残ります)`)) return
  await api.delete(`/recurring-payments/${item.id}/`)
  await ledger.fetchRecurring()
}
</script>

<template>
  <div class="page">
    <h1 class="page-title">固定費 (定期支払)</h1>

    <div class="card total-card">
      <span>有効な固定費の月あたり換算</span>
      <strong>{{ yen(monthlyEquivalent) }}</strong>
    </div>

    <button v-if="editing === null" class="btn add" @click="openNew">＋ 固定費を追加</button>

    <div v-if="editing !== null" class="card">
      <label for="rp-name">名前</label>
      <input id="rp-name" v-model="name" type="text" placeholder="家賃、水道代、固定資産税など" />
      <label>金額 (1回あたり)</label>
      <AmountInput v-model="amount" />
      <label for="rp-category">カテゴリ</label>
      <select id="rp-category" v-model="categoryId">
        <option v-for="c in expenseCategories" :key="c.id" :value="c.id">{{ c.name }}</option>
      </select>

      <label for="rp-method">支払方法 (任意。カード払いの固定費に)</label>
      <select id="rp-method" v-model="paymentMethodId">
        <option :value="null">未設定</option>
        <option v-for="m in ledger.paymentMethods" :key="m.id" :value="m.id">
          {{ m.name }}
        </option>
      </select>

      <label for="rp-interval">支払間隔</label>
      <select id="rp-interval" v-model="intervalMonths">
        <option v-for="i in INTERVALS" :key="i.value" :value="i.value">{{ i.label }}</option>
      </select>

      <template v-if="Number(intervalMonths) > 1">
        <label for="rp-anchor">該当月 (支払いがある月をひとつ指定)</label>
        <input id="rp-anchor" v-model="anchorMonth" type="month" />
        <p class="hint">
          例: 4ヶ月ごとで 5月 を指定すると 5月・9月・1月 が支払月になります。
        </p>
      </template>

      <label for="rp-day">支払日</label>
      <select id="rp-day" v-model="dayOfMonth">
        <option v-for="d in 31" :key="d" :value="d">{{ d }}日{{ d >= 29 ? ' (月末調整)' : '' }}</option>
      </select>

      <template v-if="hasGroup">
        <label>共有 (支払済にしたとき自動で共有記録になる)</label>
        <div class="chip-row">
          <button class="chip" :class="{ active: !isShared }" @click="isShared = false">
            自分のみ
          </button>
          <button class="chip" :class="{ active: isShared }" @click="isShared = true">
            👥 共有する
          </button>
        </div>
        <div v-if="isShared" class="share-inline">
          <span>あなたの負担</span>
          <input
            v-model="sharePercent"
            type="number"
            inputmode="numeric"
            min="0"
            max="100"
            class="share-input"
          />
          <span>% / {{ partnerName }}さん {{ 100 - Number(sharePercent || 0) }}%</span>
        </div>
      </template>

      <label for="rp-memo">メモ (任意)</label>
      <input id="rp-memo" v-model="memo" type="text" maxlength="200" />
      <p v-if="error" class="error-message">{{ error }}</p>
      <button class="btn save" @click="save">保存</button>
      <button class="btn btn-secondary cancel" @click="editing = null">キャンセル</button>
    </div>

    <p v-if="!ledger.recurring.length" class="empty-message">固定費はまだ登録されていません。</p>

    <div
      v-for="item in ledger.recurring"
      :key="item.id"
      class="card row"
      :class="{ inactive: !item.is_active }"
    >
      <div class="info" @click="openEdit(item)">
        <div class="name">
          {{ item.name }}
          <span v-if="item.is_shared" class="badge">👥</span>
        </div>
        <div class="sub">
          {{ intervalLabel(item) }} {{ item.day_of_month }}日 ・ {{ item.category.name
          }}{{ item.payment_method ? ` ・ ${item.payment_method.name}` : '' }}
        </div>
      </div>
      <div class="amount">{{ yen(item.amount) }}</div>
      <div class="actions">
        <button class="btn btn-secondary btn-small" @click="toggleActive(item)">
          {{ item.is_active ? '無効にする' : '有効にする' }}
        </button>
        <button class="btn btn-danger btn-small" @click="remove(item)">削除</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.total-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.9rem;
}

.total-card strong {
  font-size: 1.2rem;
  color: var(--color-primary);
}

.add {
  margin-bottom: 12px;
}

.hint {
  font-size: 0.78rem;
  color: var(--color-text-sub);
  margin-top: 4px;
}

.share-inline {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.9rem;
  margin-top: 8px;
}

.share-input {
  width: 80px;
  text-align: right;
}

.save {
  margin-top: 20px;
}

.cancel {
  margin-top: 10px;
}

.row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.row.inactive {
  opacity: 0.5;
}

.info {
  flex: 1;
  min-width: 120px;
  cursor: pointer;
}

.name {
  font-weight: 600;
}

.badge {
  font-size: 0.75rem;
}

.sub {
  font-size: 0.75rem;
  color: var(--color-text-sub);
}

.amount {
  font-weight: 700;
}

.actions {
  display: flex;
  gap: 6px;
}
</style>
