<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import dayjs from 'dayjs'
import api from '../api/client'
import { useLedgerStore } from '../stores/ledger'
import { useGroupStore } from '../stores/group'
import AmountInput from '../components/AmountInput.vue'

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
  } else {
    categoryId.value = filteredCategories.value[0]?.id ?? null
  }
})

async function submit() {
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
    shared: shared.value,
    payer_share_percent: shared.value ? Number(sharePercent.value) : null,
  }
  try {
    if (isEdit.value) {
      await api.patch(`/transactions/${route.params.id}/`, payload)
    } else {
      await api.post('/transactions/', payload)
    }
    router.push('/transactions')
  } catch (e) {
    const data = e.response?.data
    error.value = data?.shared?.[0] || data?.detail || '保存に失敗しました。'
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

      <template v-if="hasGroup && type === 'expense'">
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
        <button class="btn save" :disabled="loading" @click="submit">保存</button>
        <button v-if="isEdit" class="btn btn-danger delete" :disabled="loading" @click="remove">
          削除
        </button>
      </template>
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

.delete {
  margin-top: 10px;
}
</style>
