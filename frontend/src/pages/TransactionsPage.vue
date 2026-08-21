<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useLedgerStore } from '../stores/ledger'
import MonthPicker from '../components/MonthPicker.vue'
import { yen, dateLabel } from '../utils/format'

const ledger = useLedgerStore()
const typeFilter = ref('') // '' | 'income' | 'expense'
const methodFilter = ref('') // '' | payment method id
// 表示モード: 'list' = 新しい順 / 'calendar' = 日付順 (1日→末日、日毎)
const viewMode = ref(localStorage.getItem('kakei-tx-view') || 'list')
watch(viewMode, (v) => localStorage.setItem('kakei-tx-view', v))

const WEEKDAYS = ['日', '月', '火', '水', '木', '金', '土']

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

// カレンダー表示: 月の 1日〜末日を上から順に、日毎の記録と合計を並べる
const calendarDays = computed(() => {
  const [y, m] = ledger.month.split('-').map(Number)
  const daysInMonth = new Date(y, m, 0).getDate()
  const byDay = new Map()
  for (const tx of ledger.transactions) {
    const d = Number(tx.date.slice(8, 10))
    if (!byDay.has(d)) byDay.set(d, [])
    byDay.get(d).push(tx)
  }
  const days = []
  for (let d = 1; d <= daysInMonth; d++) {
    const txs = byDay.get(d) ?? []
    let expense = 0
    let income = 0
    for (const tx of txs) {
      if (tx.category.type === 'income') income += tx.amount
      else expense += tx.amount
    }
    days.push({ day: d, week: new Date(y, m - 1, d).getDay(), txs, expense, income })
  }
  return days
})
</script>

<template>
  <div class="page">
    <header class="header">
      <h1 class="page-title">履歴</h1>
      <RouterLink to="/import" class="btn btn-secondary btn-small">CSV取込</RouterLink>
    </header>
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
      <div class="chip-row">
        <button class="chip" :class="{ active: viewMode === 'list' }" @click="viewMode = 'list'">
          新しい順
        </button>
        <button
          class="chip"
          :class="{ active: viewMode === 'calendar' }"
          @click="viewMode = 'calendar'"
        >
          📅 日付順 (1日→末日)
        </button>
      </div>
    </div>

    <!-- 新しい順 (記録のある日だけ) -->
    <template v-if="viewMode === 'list'">
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
    </template>

    <!-- 日付順カレンダー (1日〜末日を全部並べる) -->
    <template v-else>
      <div
        v-for="d in calendarDays"
        :key="d.day"
        class="cal-day"
        :class="{ 'cal-empty': !d.txs.length }"
      >
        <div class="cal-head">
          <span class="cal-date" :class="{ sun: d.week === 0, sat: d.week === 6 }">
            {{ d.day }}日 ({{ WEEKDAYS[d.week] }})
          </span>
          <span class="cal-totals">
            <span v-if="d.income" class="amount-income">+{{ yen(d.income) }}</span>
            <span v-if="d.expense" class="amount-expense">-{{ yen(d.expense) }}</span>
          </span>
        </div>
        <div v-if="d.txs.length" class="card day-card">
          <component
            :is="tx.is_mine ? 'RouterLink' : 'div'"
            v-for="tx in d.txs"
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
      </div>
    </template>
  </div>
</template>

<style scoped>
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.header .page-title {
  margin-bottom: 0;
}

.header .btn {
  text-decoration: none;
}

.filters {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 16px;
}

.cal-day {
  margin-bottom: 4px;
}

.cal-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  padding: 6px 2px 2px;
}

.cal-date {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--color-text-sub);
}

.cal-date.sun {
  color: var(--color-expense);
}

.cal-date.sat {
  color: #1565c0;
}

.cal-empty .cal-head {
  padding: 3px 2px;
  border-bottom: 1px dashed var(--color-border);
}

.cal-empty .cal-date {
  font-weight: 400;
  opacity: 0.6;
  font-size: 0.75rem;
}

.cal-totals {
  display: flex;
  gap: 10px;
  font-size: 0.85rem;
  font-variant-numeric: tabular-nums;
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
