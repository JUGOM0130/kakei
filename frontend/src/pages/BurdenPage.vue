<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import api from '../api/client'
import { useLedgerStore } from '../stores/ledger'
import MonthPicker from '../components/MonthPicker.vue'
import { yen } from '../utils/format'

const ledger = useLedgerStore()
const data = ref(null)

async function load() {
  const res = await api.get('/summary/burden/', { params: { month: ledger.month } })
  data.value = res.data
}

onMounted(load)
watch(() => ledger.month, load)

function sortedItems(items) {
  const paid = items
    .filter((i) => i.kind === 'paid')
    .sort((a, b) => a.date.localeCompare(b.date))
  const planned = items
    .filter((i) => i.kind === 'planned')
    .sort((a, b) => a.day_of_month - b.day_of_month)
  return [...paid, ...planned]
}

function itemDay(item) {
  if (item.kind === 'paid') {
    return `${Number(item.date.slice(5, 7))}/${Number(item.date.slice(8, 10))}`
  }
  return `${item.day_of_month}日`
}

const sections = computed(() => {
  if (!data.value) return []
  const list = [{ title: 'あなた', person: data.value.me, mine: true }]
  if (data.value.partner) {
    list.push({
      title: `${data.value.partner.username}さん`,
      person: data.value.partner,
      mine: false,
    })
  }
  return list
})
</script>

<template>
  <div class="page">
    <h1 class="page-title">負担詳細 (今月の見込み)</h1>
    <MonthPicker />

    <template v-if="data">
      <!-- 見込み精算 (未払いの固定費も含めた月末予想) -->
      <div v-if="data.forecast_transfer" class="card forecast">
        月末の精算見込み:
        <strong>
          {{ data.forecast_transfer.from }} → {{ data.forecast_transfer.to }}
          {{ yen(data.forecast_transfer.amount) }}
        </strong>
        <span class="note">(予定の固定費も含む)</span>
      </div>

      <section v-for="sec in sections" :key="sec.title">
        <h2 class="section-label">{{ sec.title }}が支払うもの</h2>
        <div class="card">
          <div class="totals">
            <div class="total-cell">
              <div class="t-label">支払見込み合計</div>
              <div class="t-value">{{ yen(sec.person.pay_total) }}</div>
              <div class="t-sub">
                支払済 {{ yen(sec.person.paid_total) }} + 予定 {{ yen(sec.person.planned_total) }}
              </div>
            </div>
            <div class="total-cell">
              <div class="t-label">実質負担合計</div>
              <div class="t-value">{{ yen(sec.person.burden_total) }}</div>
              <div class="t-sub">共有分は割合で按分</div>
            </div>
          </div>

          <p v-if="!sec.person.items.length" class="empty-message">
            この月の支払いはありません。
          </p>
          <div v-for="(item, i) in sortedItems(sec.person.items)" :key="i" class="row">
            <span
              class="kind-badge"
              :class="item.kind === 'paid' ? 'kind-paid' : 'kind-planned'"
            >
              {{ item.kind === 'paid' ? '済' : '予定' }}
            </span>
            <span class="dot" :style="{ background: item.color }"></span>
            <div class="info">
              <div class="name">{{ item.name }}</div>
              <div class="sub">
                {{ itemDay(item) }} ・ {{ item.category }}
                <span v-if="item.shared" class="shared-mark">👥</span>
              </div>
            </div>
            <div class="nums">
              <div class="amount">{{ yen(item.amount) }}</div>
              <div v-if="item.shared" class="burden">
                × {{ item.percent }}% = {{ yen(item.burden) }}
              </div>
            </div>
          </div>

          <p v-if="!sec.mine" class="hint">
            ※ {{ sec.title }}の「共有していない支出・固定費」はここには表示されません。
          </p>
        </div>
      </section>

      <p v-if="!data.partner" class="hint center">
        グループに相手が参加すると、相手の支払予定もここに表示されます。
      </p>
    </template>
  </div>
</template>

<style scoped>
.forecast {
  font-size: 0.9rem;
}

.forecast strong {
  color: var(--color-primary);
}

.forecast .note {
  font-size: 0.75rem;
  color: var(--color-text-sub);
}

.section-label {
  font-size: 0.85rem;
  color: var(--color-text-sub);
  margin: 16px 0 6px;
}

.totals {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  padding-bottom: 10px;
  margin-bottom: 6px;
  border-bottom: 2px solid var(--color-border);
}

.t-label {
  font-size: 0.72rem;
  color: var(--color-text-sub);
}

.t-value {
  font-size: 1.1rem;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
}

.t-sub {
  font-size: 0.68rem;
  color: var(--color-text-sub);
}

.row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  border-bottom: 1px solid var(--color-border);
}

.row:last-of-type {
  border-bottom: none;
}

.kind-badge {
  font-size: 0.65rem;
  font-weight: 700;
  border-radius: 6px;
  padding: 2px 6px;
  flex-shrink: 0;
}

.kind-paid {
  background: #e8f5e9;
  color: var(--color-primary);
}

.kind-planned {
  background: var(--warn-soft, #fdf3e2);
  color: #8a5a12;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.info {
  flex: 1;
  min-width: 0;
}

.name {
  font-size: 0.85rem;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sub {
  font-size: 0.7rem;
  color: var(--color-text-sub);
}

.nums {
  text-align: right;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.amount {
  font-size: 0.85rem;
  font-weight: 700;
}

.burden {
  font-size: 0.72rem;
  color: var(--color-text-sub);
}

.hint {
  font-size: 0.75rem;
  color: var(--color-text-sub);
  margin-top: 8px;
}

.hint.center {
  text-align: center;
}
</style>
