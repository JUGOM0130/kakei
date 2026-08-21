<script setup>
import { onMounted } from 'vue'
import { useAuthStore } from '../stores/auth'
import { useStocksStore } from '../stores/stocks'
import { signedYen, pnlClass, yen } from '../utils/format'
import MonthlyBar from '../components/MonthlyBar.vue'

const auth = useAuthStore()
const stocks = useStocksStore()

async function changeYear(delta) {
  stocks.year += delta
  await stocks.fetchSummary()
}

async function logout() {
  await auth.logout()
  location.href = import.meta.env.BASE_URL + 'login'
}

onMounted(() => stocks.fetchSummary())
</script>

<template>
  <div class="page">
    <header class="header">
      <h1 class="page-title">KABU</h1>
      <button class="logout" @click="logout">ログアウト</button>
    </header>

    <div class="year-nav">
      <button aria-label="前の年" @click="changeYear(-1)">◀</button>
      <span class="label">{{ stocks.year }}年</span>
      <button aria-label="次の年" @click="changeYear(1)">▶</button>
    </div>

    <template v-if="stocks.summary">
      <div class="card total-card">
        <p class="total-label">年間トータル (実現損益 + 配当)</p>
        <p class="total-value" :class="pnlClass(stocks.summary.total)">
          {{ signedYen(stocks.summary.total) }}
        </p>
        <div class="breakdown">
          <div>
            <span class="bd-label">実現損益</span>
            <span :class="pnlClass(stocks.summary.realized)">{{
              signedYen(stocks.summary.realized)
            }}</span>
          </div>
          <div>
            <span class="bd-label">配当</span>
            <span>{{ yen(stocks.summary.dividends) }}</span>
          </div>
        </div>
      </div>

      <div class="card">
        <p class="card-title">月別推移</p>
        <MonthlyBar :monthly="stocks.summary.monthly" />
      </div>

      <div class="card">
        <p class="card-title">銘柄別 ({{ stocks.year }}年)</p>
        <p v-if="stocks.summary.by_code.length === 0" class="empty-message">
          まだ記録がありません
        </p>
        <table v-else class="code-table">
          <thead>
            <tr>
              <th>銘柄</th>
              <th class="num">実現損益</th>
              <th class="num">配当</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in stocks.summary.by_code" :key="row.code">
              <td>
                <span class="code">{{ row.code }}</span>
                {{ row.name }}
              </td>
              <td class="num" :class="pnlClass(row.realized)">
                {{ row.realized ? signedYen(row.realized) : '—' }}
              </td>
              <td class="num">{{ row.dividends ? yen(row.dividends) : '—' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </div>
</template>

<style scoped>
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header .page-title {
  color: var(--color-primary);
  margin-bottom: 0;
}

.logout {
  border: none;
  background: none;
  color: var(--color-text-sub);
  font-size: 0.85rem;
  cursor: pointer;
  min-height: 44px;
}

.total-card {
  text-align: center;
}

.total-label {
  font-size: 0.85rem;
  color: var(--color-text-sub);
}

.total-value {
  font-size: 2rem;
  margin: 4px 0 12px;
}

.breakdown {
  display: flex;
  justify-content: center;
  gap: 24px;
  font-size: 0.95rem;
}

.bd-label {
  color: var(--color-text-sub);
  margin-right: 6px;
  font-size: 0.8rem;
}

.card-title {
  font-weight: 700;
  margin-bottom: 8px;
}

.code-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
}

.code-table th {
  font-size: 0.75rem;
  color: var(--color-text-sub);
  font-weight: 600;
  text-align: left;
  padding: 4px 0;
}

.code-table td {
  padding: 8px 0;
  border-top: 1px solid var(--color-border);
}

.code-table .num {
  text-align: right;
  white-space: nowrap;
}

.code {
  display: inline-block;
  color: var(--color-text-sub);
  font-size: 0.8rem;
  margin-right: 4px;
}
</style>
