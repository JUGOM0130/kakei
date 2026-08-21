<script setup>
import { onMounted, watch } from 'vue'
import { useLedgerStore } from '../stores/ledger'
import MonthPicker from '../components/MonthPicker.vue'
import MinimumRequiredCard from '../components/MinimumRequiredCard.vue'
import SummaryCard from '../components/SummaryCard.vue'
import CategoryPie from '../components/CategoryPie.vue'
import RecurringChecklist from '../components/RecurringChecklist.vue'
import SharedCard from '../components/SharedCard.vue'
import PaymentMethodTotals from '../components/PaymentMethodTotals.vue'
import BalanceCard from '../components/BalanceCard.vue'

const ledger = useLedgerStore()

onMounted(() => ledger.fetchSummary())
watch(() => ledger.month, () => ledger.fetchSummary())

async function onPay(id) {
  try {
    await ledger.pay(id)
  } catch (e) {
    alert(e.response?.data?.detail || '支払処理に失敗しました。')
  }
}

async function onSettle() {
  try {
    await ledger.settle()
  } catch (e) {
    alert(e.response?.data?.detail || '精算の記録に失敗しました。')
  }
}

async function onUnsettle(id) {
  if (!confirm('精算済みの記録を取り消しますか?')) return
  await ledger.unsettle(id)
}
</script>

<template>
  <div class="page">
    <h1 class="page-title">ホーム</h1>
    <MonthPicker />
    <template v-if="ledger.summary">
      <MinimumRequiredCard :recurring="ledger.summary.recurring" />
      <BalanceCard :forecast="ledger.summary.balance_forecast" />
      <SummaryCard
        :income="ledger.summary.income_total"
        :expense="ledger.summary.expense_total"
        :balance="ledger.summary.balance"
      />
      <SharedCard
        v-if="ledger.summary.shared.enabled"
        :shared="ledger.summary.shared"
        @settle="onSettle"
        @unsettle="onUnsettle"
      />
      <div class="card">
        <div class="heading">支出の内訳</div>
        <CategoryPie
          v-if="ledger.summary.expense_by_category.length"
          :items="ledger.summary.expense_by_category"
        />
        <p v-else class="empty-message">今月の支出はまだありません。</p>
      </div>
      <PaymentMethodTotals :items="ledger.summary.payment_methods" />
      <RecurringChecklist :items="ledger.summary.recurring.items" @pay="onPay" />
    </template>
  </div>
</template>

<style scoped>
.heading {
  font-weight: 700;
  margin-bottom: 8px;
}
</style>
