<script setup>
import { computed, onMounted, ref } from 'vue'
import api from '../api/client'
import { useLedgerStore } from '../stores/ledger'

const ledger = useLedgerStore()

const newType = ref('expense')
const newName = ref('')
const newColor = ref('#9e9e9e')
const error = ref('')

const expense = computed(() => ledger.categories.filter((c) => c.type === 'expense'))
const income = computed(() => ledger.categories.filter((c) => c.type === 'income'))

onMounted(() => ledger.fetchCategories(true))

async function add() {
  error.value = ''
  if (!newName.value.trim()) return
  try {
    await api.post('/categories/', {
      name: newName.value.trim(),
      type: newType.value,
      color: newColor.value,
    })
    newName.value = ''
    await ledger.fetchCategories(true)
  } catch (e) {
    error.value = e.response?.data?.name?.[0] || e.response?.data?.detail || '追加に失敗しました。'
  }
}

async function rename(cat) {
  const name = prompt('カテゴリ名', cat.name)
  if (!name || name === cat.name) return
  try {
    await api.patch(`/categories/${cat.id}/`, { name })
    await ledger.fetchCategories(true)
  } catch (e) {
    alert(e.response?.data?.name?.[0] || '変更に失敗しました。')
  }
}

async function changeColor(cat, event) {
  await api.patch(`/categories/${cat.id}/`, { color: event.target.value })
  await ledger.fetchCategories(true)
}

async function remove(cat) {
  if (!confirm(`「${cat.name}」を削除しますか?`)) return
  try {
    await api.delete(`/categories/${cat.id}/`)
    await ledger.fetchCategories(true)
  } catch (e) {
    alert(e.response?.data?.detail || '削除に失敗しました。')
  }
}
</script>

<template>
  <div class="page">
    <h1 class="page-title">カテゴリ</h1>

    <div class="card">
      <div class="chip-row">
        <button
          class="chip"
          :class="{ active: newType === 'expense' }"
          @click="newType = 'expense'"
        >
          支出
        </button>
        <button class="chip" :class="{ active: newType === 'income' }" @click="newType = 'income'">
          収入
        </button>
      </div>
      <div class="add-row">
        <input v-model="newName" type="text" placeholder="新しいカテゴリ名" maxlength="50" />
        <input v-model="newColor" type="color" class="color-input" aria-label="色" />
        <button class="btn btn-small" @click="add">追加</button>
      </div>
      <p v-if="error" class="error-message">{{ error }}</p>
    </div>

    <template v-for="(list, label) in { 支出: expense, 収入: income }" :key="label">
      <h2 class="section-label">{{ label }}</h2>
      <div class="card list-card">
        <div v-for="cat in list" :key="cat.id" class="row">
          <input
            type="color"
            class="color-input"
            :value="cat.color"
            :aria-label="`${cat.name}の色`"
            @change="changeColor(cat, $event)"
          />
          <span class="name" @click="rename(cat)">{{ cat.name }}</span>
          <button class="btn btn-secondary btn-small" @click="rename(cat)">名前</button>
          <button class="btn btn-danger btn-small" @click="remove(cat)">削除</button>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.add-row {
  display: flex;
  gap: 8px;
  margin-top: 12px;
  align-items: center;
}

.add-row input[type='text'] {
  flex: 1;
}

.color-input {
  width: 44px;
  height: 44px;
  padding: 4px;
  flex-shrink: 0;
}

.add-row .btn {
  flex-shrink: 0;
}

.section-label {
  font-size: 0.85rem;
  color: var(--color-text-sub);
  margin: 16px 0 6px;
}

.list-card {
  padding: 4px 16px;
}

.row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 0;
  border-bottom: 1px solid var(--color-border);
}

.row:last-child {
  border-bottom: none;
}

.name {
  flex: 1;
  font-weight: 600;
  cursor: pointer;
}
</style>
