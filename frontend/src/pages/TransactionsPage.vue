<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useLedgerStore } from '../stores/ledger'
import MonthPicker from '../components/MonthPicker.vue'
import { yen, dateLabel } from '../utils/format'

const ledger = useLedgerStore()
const typeFilter = ref('') // '' | 'income' | 'expense'
const methodFilter = ref('') // '' | payment method id

function load() {
  const params = {}
  if (typeFilter.value) params.type = typeFilter.value
  if (methodFilter.value) params.payment_method = methodFilter.value
  ledger.fetchTransactions(params)
}

onMounted(async () => {
  await ledger.fetchPaymentMethods()
  load()
})
watch(() => ledger.month, load)
watch([typeFilter, methodFilter], load)

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
    <div class="filters">
      <div class="chip-row">
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
      <select v-if="ledger.paymentMethods.length" v-model="methodFilter" class="method-select">
        <option value="">支払方法: すべて</option>
        <option v-for="m in ledger.paymentMethods" :key="m.id" :value="m.id">
          {{ m.name }}
        </option>
      </select>
    </div>

    <p v-if="!ledger.transactions.length" class="empty-message">今月の記録はまだありません。</p>

    <section v-for="[date, txs] in grouped" :key="date" class="day-group">
      <h2 class="day-label">{{ dateLabel(date) }}</h2>
      <div class="card day-card">
        <component
          :is="tx.is_mine ? 'RouterLink' : 'div'"
          v-for="tx in txs"
          :key="tx.id"
          :to="tx.is_mine ? `/transactions/${tx.id}/edit` : undefined"
          class="row"
          :class="{ theirs: !tx.is_mine }"
        >
          <span class="dot" :style="{ background: tx.category.color }"></span>
          <div class="info">
            <div class="cat">
              {{ tx.category.name }}
              <span v-if="tx.items && tx.items.length" class="badge items-badge">
                内訳{{ tx.items.length }}件
              </span>
              <span v-if="tx.is_shared" class="badge shared-badge">👥 共有</span>
              <span v-if="!tx.is_mine" class="badge payer-badge">{{ tx.payer.username }}</span>
            </div>
            <div class="sub">
              <span v-if="tx.payment_method">{{ tx.payment_method.name }}</span>
              <span v-if="tx.memo">{{ tx.memo }}</span>
            </div>
          </div>
          <span
            class="amount"
            :class="tx.category.type === 'income' ? 'amount-income' : 'amount-expense'"
          >
            {{ tx.category.type === 'income' ? '+' : '-' }}{{ yen(tx.amount) }}
          </span>
        </component>
      </div>
    </section>
  </div>
</template>

<style scoped>
.filters {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 16px;
}

.method-select {
  width: auto;
  align-self: flex-start;
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

.row.theirs {
  opacity: 0.85;
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
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.badge {
  font-size: 0.65rem;
  font-weight: 600;
  border-radius: 999px;
  padding: 1px 8px;
}

.shared-badge {
  background: #e8f5e9;
  color: var(--color-primary);
}

.payer-badge {
  background: var(--color-bg);
  color: var(--color-text-sub);
  border: 1px solid var(--color-border);
}

.items-badge {
  background: var(--color-bg);
  color: var(--color-text-sub);
  border: 1px solid var(--color-border);
}

.sub {
  font-size: 0.75rem;
  color: var(--color-text-sub);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  display: flex;
  gap: 8px;
}

.amount {
  white-space: nowrap;
}
</style>
