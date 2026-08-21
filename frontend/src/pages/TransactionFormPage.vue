<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import dayjs from 'dayjs'
import api from '../api/client'
import { useLedgerStore } from '../stores/ledger'
import AmountInput from '../components/AmountInput.vue'

const route = useRoute()
const router = useRouter()
const ledger = useLedgerStore()

const isEdit = computed(() => !!route.params.id)

const type = ref('expense')
const categoryId = ref(null)
const amount = ref('')
const date = ref(dayjs().format('YYYY-MM-DD'))
const memo = ref('')
const error = ref('')
const loading = ref(false)

const filteredCategories = computed(() =>
  ledger.categories.filter((c) => c.type === type.value)
)

function switchType(t) {
  type.value = t
  if (!filteredCategories.value.some((c) => c.id === categoryId.value)) {
    categoryId.value = filteredCategories.value[0]?.id ?? null
  }
}

onMounted(async () => {
  await ledger.fetchCategories()
  if (isEdit.value) {
    const { data } = await api.get(`/transactions/${route.params.id}/`)
    type.value = data.category.type
    categoryId.value = data.category.id
    amount.value = String(data.amount)
    date.value = data.date
    memo.value = data.memo
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
  }
  try {
    if (isEdit.value) {
      await api.patch(`/transactions/${route.params.id}/`, payload)
    } else {
      await api.post('/transactions/', payload)
    }
    router.push('/transactions')
  } catch (e) {
    error.value = e.response?.data?.detail || '保存に失敗しました。'
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

    <div class="card">
      <div class="chip-row type-toggle">
        <button
          class="chip"
          :class="{ active: type === 'expense' }"
          @click="switchType('expense')"
        >
          支出
        </button>
        <button
          class="chip"
          :class="{ active: type === 'income' }"
          @click="switchType('income')"
        >
          収入
        </button>
      </div>

      <label>金額</label>
      <AmountInput v-model="amount" />

      <label>カテゴリ</label>
      <div class="chip-row">
        <button
          v-for="c in filteredCategories"
          :key="c.id"
          class="chip"
          :class="{ active: categoryId === c.id }"
          @click="categoryId = c.id"
        >
          <span class="chip-dot" :style="{ background: c.color }"></span>{{ c.name }}
        </button>
      </div>

      <label for="date">日付</label>
      <input id="date" v-model="date" type="date" required />

      <label for="memo">メモ (任意)</label>
      <input id="memo" v-model="memo" type="text" maxlength="200" />

      <p v-if="error" class="error-message">{{ error }}</p>
      <button class="btn save" :disabled="loading" @click="submit">保存</button>
      <button v-if="isEdit" class="btn btn-danger delete" :disabled="loading" @click="remove">
        削除
      </button>
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

.save {
  margin-top: 20px;
}

.delete {
  margin-top: 10px;
}
</style>
