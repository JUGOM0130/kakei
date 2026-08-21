<script setup>
import { onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useLedgerStore } from '../stores/ledger'
import MonthPicker from '../components/MonthPicker.vue'
import MinimumRequiredCard from '../components/MinimumRequiredCard.vue'
import SummaryCard from '../components/SummaryCard.vue'
import CategoryPie from '../components/CategoryPie.vue'
import RecurringChecklist from '../components/RecurringChecklist.vue'

const auth = useAuthStore()
const ledger = useLedgerStore()
const router = useRouter()

onMounted(() => ledger.fetchSummary())
watch(() => ledger.month, () => ledger.fetchSummary())

async function onPay(id) {
  try {
    await ledger.pay(id)
  } catch (e) {
    alert(e.response?.data?.detail || '支払処理に失敗しました。')
  }
}

async function logout() {
  await auth.logout()
  router.push('/login')
}
</script>

<template>
  <div class="page">
    <header class="header">
      <h1 class="page-title">ホーム</h1>
      <button class="btn btn-secondary btn-small" @click="logout">ログアウト</button>
    </header>
    <MonthPicker />
    <template v-if="ledger.summary">
      <MinimumRequiredCard :recurring="ledger.summary.recurring" />
      <SummaryCard
        :income="ledger.summary.income_total"
        :expense="ledger.summary.expense_total"
        :balance="ledger.summary.balance"
      />
      <div class="card">
        <div class="heading">支出の内訳</div>
        <CategoryPie
          v-if="ledger.summary.expense_by_category.length"
          :items="ledger.summary.expense_by_category"
        />
        <p v-else class="empty-message">今月の支出はまだありません。</p>
      </div>
      <RecurringChecklist :items="ledger.summary.recurring.items" @pay="onPay" />
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

.heading {
  font-weight: 700;
  margin-bottom: 8px;
}
</style>
