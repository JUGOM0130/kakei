<script setup>
import { computed, onMounted, ref } from 'vue'
import api from '../api/client'
import { useLedgerStore } from '../stores/ledger'
import AmountInput from '../components/AmountInput.vue'
import { yen } from '../utils/format'

const ledger = useLedgerStore()

const editing = ref(null) // null=閉じる, 'new'=新規, number=編集中ID
const name = ref('')
const amount = ref('')
const categoryId = ref(null)
const dayOfMonth = ref(1)
const memo = ref('')
const error = ref('')

const expenseCategories = computed(() =>
  ledger.categories.filter((c) => c.type === 'expense')
)

const totalActive = computed(() =>
  ledger.recurring.filter((r) => r.is_active).reduce((sum, r) => sum + r.amount, 0)
)

onMounted(async () => {
  await Promise.all([ledger.fetchCategories(), ledger.fetchRecurring()])
})

function openNew() {
  editing.value = 'new'
  name.value = ''
  amount.value = ''
  categoryId.value = expenseCategories.value[0]?.id ?? null
  dayOfMonth.value = 1
  memo.value = ''
  error.value = ''
}

function openEdit(item) {
  editing.value = item.id
  name.value = item.name
  amount.value = String(item.amount)
  categoryId.value = item.category.id
  dayOfMonth.value = item.day_of_month
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
    day_of_month: Number(dayOfMonth.value),
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
    error.value = e.response?.data?.detail || '保存に失敗しました。'
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
      <span>有効な固定費の合計 (月の最低必要額)</span>
      <strong>{{ yen(totalActive) }}</strong>
    </div>

    <button v-if="editing === null" class="btn add" @click="openNew">＋ 固定費を追加</button>

    <div v-if="editing !== null" class="card">
      <label for="rp-name">名前</label>
      <input id="rp-name" v-model="name" type="text" placeholder="家賃、サブスクなど" />
      <label>金額</label>
      <AmountInput v-model="amount" />
      <label for="rp-category">カテゴリ</label>
      <select id="rp-category" v-model="categoryId">
        <option v-for="c in expenseCategories" :key="c.id" :value="c.id">{{ c.name }}</option>
      </select>
      <label for="rp-day">支払日 (毎月)</label>
      <select id="rp-day" v-model="dayOfMonth">
        <option v-for="d in 31" :key="d" :value="d">{{ d }}日{{ d >= 29 ? ' (月末調整)' : '' }}</option>
      </select>
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
        <div class="name">{{ item.name }}</div>
        <div class="sub">毎月{{ item.day_of_month }}日 ・ {{ item.category.name }}</div>
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
