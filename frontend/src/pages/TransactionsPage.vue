<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useLedgerStore } from '../stores/ledger'
import MonthPicker from '../components/MonthPicker.vue'
import { yen, dateLabel } from '../utils/format'

const ledger = useLedgerStore()
const typeFilter = ref('') // '' | 'income' | 'expense'

function load() {
  const params = {}
  if (typeFilter.value) params.type = typeFilter.value
  ledger.fetchTransactions(params)
}

onMounted(load)
watch(() => ledger.month, load)
watch(typeFilter, load)

const grouped = computed(() => {
  const map = new Map()
  for (const tx of ledger.transactions) {
    if (!map.has(tx.date)) map.set(tx.date, [])
    map.get(tx.date).push(tx)
  }
  return [...map.entries()]
})
</script>

<template>
  <div class="page">
    <h1 class="page-title">履歴</h1>
    <MonthPicker />
    <div class="chip-row tabs">
      <button class="chip" :class="{ active: typeFilter === '' }" @click="typeFilter = ''">
        すべて
      </button>
      <button
        class="chip"
        :class="{ active: typeFilter === 'income' }"
        @click="typeFilter = 'income'"
      >
        収入
      </button>
      <button
        class="chip"
        :class="{ active: typeFilter === 'expense' }"
        @click="typeFilter = 'expense'"
      >
        支出
      </button>
    </div>

    <p v-if="!ledger.transactions.length" class="empty-message">今月の記録はまだありません。</p>

    <section v-for="[date, txs] in grouped" :key="date" class="day-group">
      <h2 class="day-label">{{ dateLabel(date) }}</h2>
      <div class="card day-card">
        <RouterLink
          v-for="tx in txs"
          :key="tx.id"
          :to="`/transactions/${tx.id}/edit`"
          class="row"
        >
          <span class="dot" :style="{ background: tx.category.color }"></span>
          <div class="info">
            <div class="cat">{{ tx.category.name }}</div>
            <div v-if="tx.memo" class="memo">{{ tx.memo }}</div>
          </div>
          <span
            class="amount"
            :class="tx.category.type === 'income' ? 'amount-income' : 'amount-expense'"
          >
            {{ tx.category.type === 'income' ? '+' : '-' }}{{ yen(tx.amount) }}
          </span>
        </RouterLink>
      </div>
    </section>
  </div>
</template>

<style scoped>
.tabs {
  margin-bottom: 16px;
}

.day-label {
  font-size: 0.85rem;
  color: var(--color-text-sub);
  margin: 12px 0 6px;
  font-weight: 600;
}

.day-card {
  padding: 4px 16px;
}

.row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 0;
  border-bottom: 1px solid var(--color-border);
  text-decoration: none;
  color: inherit;
  min-height: 44px;
}

.row:last-child {
  border-bottom: none;
}

.dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

.info {
  flex: 1;
  min-width: 0;
}

.cat {
  font-weight: 600;
}

.memo {
  font-size: 0.75rem;
  color: var(--color-text-sub);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.amount {
  white-space: nowrap;
}
</style>
