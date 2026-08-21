<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import dayjs from 'dayjs'
import api from '../api/client'
import { useLedgerStore } from '../stores/ledger'
import { useGroupStore } from '../stores/group'
import AmountInput from '../components/AmountInput.vue'
import { yen } from '../utils/format'

const route = useRoute()
const router = useRouter()
const ledger = useLedgerStore()
const groupStore = useGroupStore()

const isEdit = computed(() => !!route.params.id)

const type = ref('expense')
const categoryId = ref(null)
const amount = ref('')
const date = ref(dayjs().format('YYYY-MM-DD'))
const memo = ref('')
const paymentMethodId = ref(null)
const shared = ref(false)
const sharePercent = ref(50)
const error = ref('')
const loading = ref(false)
const notMine = ref(false)

// カード内訳 (親子)
const items = ref([])
const isChild = ref(false) // この取引自体が内訳行
const itemAmount = ref('')
const itemCategoryId = ref(null)
const itemShared = ref(false)
const itemSharePercent = ref(50)
const itemMemo = ref('')
const itemError = ref('')

const itemsTotal = computed(() => items.value.reduce((s, i) => s + i.amount, 0))
const remainder = computed(() => Number(amount.value || 0) - itemsTotal.value)
const canBreakdown = computed(
  () => isEdit.value && !notMine.value && !isChild.value && type.value === 'expense' && !shared.value
)

const filteredCategories = computed(() =>
  ledger.categories.filter((c) => c.type === type.value)
)

const hasGroup = computed(() => !!groupStore.group)
const partnerName = computed(() => groupStore.partner?.username ?? '相手')

function switchType(t) {
  type.value = t
  if (!filteredCategories.value.some((c) => c.id === categoryId.value)) {
    categoryId.value = filteredCategories.value[0]?.id ?? null
  }
  if (t === 'income') shared.value = false
}

onMounted(async () => {
  await Promise.all([
    ledger.fetchCategories(),
    ledger.fetchPaymentMethods(),
    groupStore.loaded ? Promise.resolve() : groupStore.fetch(),
  ])
  if (groupStore.me) sharePercent.value = groupStore.me.share_percent
  if (isEdit.value) {
    await loadTransaction()
  } else {
    categoryId.value = filteredCategories.value[0]?.id ?? null
  }
})

async function loadTransaction() {
  const { data } = await api.get(`/transactions/${route.params.id}/`)
  notMine.value = !data.is_mine
  type.value = data.category.type
  categoryId.value = data.category.id
  amount.value = String(data.amount)
  date.value = data.date
  memo.value = data.memo
  paymentMethodId.value = data.payment_method?.id ?? null
  shared.value = data.is_shared
  if (data.payer_share_percent != null) sharePercent.value = data.payer_share_percent
  items.value = data.items ?? []
  isChild.value = data.parent != null
  if (itemCategoryId.value === null) {
    itemCategoryId.value = ledger.categories.find((c) => c.type === 'expense')?.id ?? null
  }
}

async function addItem() {
  itemError.value = ''
  const value = Number(itemAmount.value)
  if (!value || !itemCategoryId.value) {
    itemError.value = '金額とカテゴリを入力してください。'
    return
  }
  if (value > remainder.value) {
    itemError.value = `残額 (¥${remainder.value.toLocaleString('ja-JP')}) を超えています。`
    return
  }
  try {
    await api.post('/transactions/', {
      parent: Number(route.params.id),
      category_id: itemCategoryId.value,
      amount: value,
      memo: itemMemo.value,
      shared: itemShared.value,
      payer_share_percent: itemShared.value ? Number(itemSharePercent.value) : null,
    })
    itemAmount.value = ''
    itemMemo.value = ''
    itemShared.value = false
    await loadTransaction()
  } catch (e) {
    const data = e.response?.data
    itemError.value =
      data?.amount?.[0] || data?.shared?.[0] || data?.detail || '追加に失敗しました。'
  }
}

async function removeItem(item) {
  await api.delete(`/transactions/${item.id}/`)
  await loadTransaction()
}

async function submit(goBreakdown = false) {
  error.value = ''
  if (!categoryId.value) {
    error.value = 'カテゴリを選択してください。'
    return
  }
  if (!Number(amount.value)) {
    error.value = '金額を入力してください。'
    return
  }
  loading.value = true
  const payload = {
    category_id: categoryId.value,
    amount: Number(amount.value),
    date: date.value,
    memo: memo.value,
    payment_method_id: paymentMethodId.value,
    shared: items.value.length ? undefined : shared.value,
    payer_share_percent: shared.value && !items.value.length ? Number(sharePercent.value) : null,
  }
  try {
    if (isEdit.value) {
      await api.patch(`/transactions/${route.params.id}/`, payload)
      router.push('/transactions')
    } else {
      const { data } = await api.post('/transactions/', payload)
      if (goBreakdown) {
        router.push(`/transactions/${data.id}/edit`)
      } else {
        router.push('/transactions')
      }
    }
  } catch (e) {
    const data = e.response?.data
    error.value =
      data?.shared?.[0] || data?.amount?.[0] || data?.detail || '保存に失敗しました。'
  } finally {
    loading.value = false
  }
}

async function remove() {
  if (!confirm('この記録を削除しますか?')) return
  await api.delete(`/transactions/${route.params.id}/`)
  router.push('/transactions')
}
</script>

<template>
  <div class="page">
    <h1 class="page-title">{{ isEdit ? '記録を編集' : '記録を追加' }}</h1>

    <div v-if="notMine" class="card">
      <p>これは{{ partnerName }}さんの記録のため、閲覧のみ可能です。</p>
    </div>

    <div class="card">
      <div class="chip-row type-toggle">
        <button
          class="chip"
          :class="{ active: type === 'expense' }"
          :disabled="notMine"
          @click="switchType('expense')"
        >
          支出
        </button>
        <button
          class="chip"
          :class="{ active: type === 'income' }"
          :disabled="notMine"
          @click="switchType('income')"
        >
          収入
        </button>
      </div>

      <label>金額</label>
      <AmountInput v-model="amount" :disabled="notMine" />

      <label>カテゴリ</label>
      <div class="chip-row">
        <button
          v-for="c in filteredCategories"
          :key="c.id"
          class="chip"
          :class="{ active: categoryId === c.id }"
          :disabled="notMine"
          @click="categoryId = c.id"
        >
          <span class="chip-dot" :style="{ background: c.color }"></span>{{ c.name }}
        </button>
      </div>

      <template v-if="type === 'expense' && ledger.paymentMethods.length">
        <label>支払方法 (任意)</label>
        <div class="chip-row">
          <button
            class="chip"
            :class="{ active: paymentMethodId === null }"
            :disabled="notMine"
            @click="paymentMethodId = null"
          >
            未設定
          </button>
          <button
            v-for="m in ledger.paymentMethods"
            :key="m.id"
            class="chip"
            :class="{ active: paymentMethodId === m.id }"
            :disabled="notMine"
            @click="paymentMethodId = m.id"
          >
            {{ m.name }}
          </button>
        </div>
      </template>

      <p v-if="items.length" class="hint">
        内訳が {{ items.length }} 件あります。共有は内訳行ごとに設定してください。
      </p>
      <template v-if="hasGroup && type === 'expense' && !items.length">
        <label>共有 (グループで折半・分担)</label>
        <div class="chip-row">
          <button class="chip" :class="{ active: !shared }" :disabled="notMine" @click="shared = false">
            自分のみ
          </button>
          <button class="chip" :class="{ active: shared }" :disabled="notMine" @click="shared = true">
            👥 共有する
          </button>
        </div>
        <div v-if="shared" class="share-box">
          <div class="chip-row">
            <button
              class="chip"
              :class="{ active: Number(sharePercent) === 50 }"
              :disabled="notMine"
              @click="sharePercent = 50"
            >
              折半 (50/50)
            </button>
          </div>
          <div class="share-inline">
            <span>あなたの負担</span>
            <input
              v-model="sharePercent"
              type="number"
              inputmode="numeric"
              min="0"
              max="100"
              class="share-input"
              :disabled="notMine"
            />
            <span>% / {{ partnerName }}さん {{ 100 - Number(sharePercent || 0) }}%</span>
          </div>
        </div>
      </template>

      <label for="date">日付</label>
      <input id="date" v-model="date" type="date" required :disabled="notMine" />

      <label for="memo">メモ (任意)</label>
      <input id="memo" v-model="memo" type="text" maxlength="200" :disabled="notMine" />

      <p v-if="error" class="error-message">{{ error }}</p>
      <template v-if="!notMine">
        <button class="btn save" :disabled="loading" @click="submit()">保存</button>
        <button
          v-if="!isEdit && type === 'expense'"
          class="btn btn-secondary breakdown-btn"
          :disabled="loading"
          @click="submit(true)"
        >
          保存して内訳を入力 (カード請求など)
        </button>
        <button v-if="isEdit" class="btn btn-danger delete" :disabled="loading" @click="remove">
          削除
        </button>
      </template>
    </div>

    <!-- カード内訳 (親子) -->
    <div v-if="canBreakdown" class="card">
      <div class="heading">内訳 (カード請求の中身など)</div>
      <p class="hint">
        合計 {{ yen(Number(amount || 0)) }} のうち、共有(折半)したいものやカテゴリを分けたいものを行として追加します。
      </p>

      <div v-for="item in items" :key="item.id" class="item-row">
        <span class="chip-dot" :style="{ background: item.category.color }"></span>
        <div class="item-info">
          <div class="item-name">
            {{ item.category.name }}
            <span v-if="item.is_shared" class="badge">👥 共有</span>
          </div>
          <div v-if="item.memo" class="item-memo">{{ item.memo }}</div>
        </div>
        <span class="item-amount">{{ yen(item.amount) }}</span>
        <button class="btn btn-danger btn-small" @click="removeItem(item)">削除</button>
      </div>
      <div class="item-row remainder-row">
        <div class="item-info">
          <div class="item-name">残額 (自分のみ・このカテゴリのまま)</div>
        </div>
        <span class="item-amount">{{ yen(remainder) }}</span>
      </div>

      <div class="add-item">
        <label>内訳を追加</label>
        <AmountInput v-model="itemAmount" />
        <div class="chip-row item-cats">
          <button
            v-for="c in filteredCategories"
            :key="c.id"
            class="chip"
            :class="{ active: itemCategoryId === c.id }"
            @click="itemCategoryId = c.id"
          >
            <span class="chip-dot" :style="{ background: c.color }"></span>{{ c.name }}
          </button>
        </div>
        <template v-if="hasGroup">
          <div class="chip-row">
            <button class="chip" :class="{ active: !itemShared }" @click="itemShared = false">
              自分のみ
            </button>
            <button class="chip" :class="{ active: itemShared }" @click="itemShared = true">
              👥 共有する
            </button>
          </div>
          <div v-if="itemShared" class="share-inline">
            <span>あなたの負担</span>
            <input
              v-model="itemSharePercent"
              type="number"
              inputmode="numeric"
              min="0"
              max="100"
              class="share-input"
            />
            <span>% / {{ partnerName }}さん {{ 100 - Number(itemSharePercent || 0) }}%</span>
          </div>
        </template>
        <input v-model="itemMemo" type="text" placeholder="メモ (任意)" maxlength="200" />
        <p v-if="itemError" class="error-message">{{ itemError }}</p>
        <button class="btn" @click="addItem">内訳を追加</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.type-toggle {
  margin-bottom: 4px;
}

.type-toggle .chip {
  flex: 1;
  justify-content: center;
}

.share-box {
  margin-top: 8px;
  padding: 10px;
  background: var(--color-bg);
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.share-inline {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.9rem;
}

.share-input {
  width: 80px;
  text-align: right;
}

.save {
  margin-top: 20px;
}

.breakdown-btn,
.delete {
  margin-top: 10px;
}

.heading {
  font-weight: 700;
  margin-bottom: 8px;
}

.hint {
  font-size: 0.78rem;
  color: var(--color-text-sub);
  margin-bottom: 8px;
}

.item-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  border-bottom: 1px solid var(--color-border);
}

.item-info {
  flex: 1;
  min-width: 0;
}

.item-name {
  font-weight: 600;
  font-size: 0.9rem;
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.item-memo {
  font-size: 0.75rem;
  color: var(--color-text-sub);
}

.item-amount {
  font-weight: 700;
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}

.remainder-row {
  color: var(--color-text-sub);
  border-bottom: none;
}

.badge {
  font-size: 0.65rem;
  font-weight: 600;
  border-radius: 999px;
  padding: 1px 8px;
  background: #e8f5e9;
  color: var(--color-primary);
}

.add-item {
  margin-top: 12px;
  padding-top: 4px;
  border-top: 1px dashed var(--color-border);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.item-cats {
  margin-top: 4px;
}
</style>
