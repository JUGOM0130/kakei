<script setup>
import { computed, ref } from 'vue'
import api from '../api/client'
import { parseRakutenTradeCsv, readFileAsText } from '../utils/rakutenCsv'
import { accountLabel, dateLabel, yen } from '../utils/format'

const trades = ref([])
const excluded = ref([])
const fileName = ref('')
const parseError = ref('')
const result = ref(null)
const importing = ref(false)

const buyCount = computed(() => trades.value.filter((t) => t.side === 'buy').length)
const sellCount = computed(() => trades.value.filter((t) => t.side === 'sell').length)

async function onFile(e) {
  const file = e.target.files[0]
  e.target.value = ''
  if (!file) return
  parseError.value = ''
  result.value = null
  trades.value = []
  excluded.value = []
  fileName.value = file.name
  try {
    const text = await readFileAsText(file)
    const parsed = parseRakutenTradeCsv(text)
    trades.value = parsed.trades
    excluded.value = parsed.excluded
  } catch (err) {
    parseError.value = err.message || 'CSVの解析に失敗しました。'
  }
}

async function doImport() {
  importing.value = true
  try {
    const { data } = await api.post('/stocks/import/trades/', { trades: trades.value })
    result.value = data
    trades.value = []
  } catch (e) {
    parseError.value =
      JSON.stringify(e.response?.data || '') !== '""'
        ? '取込に失敗しました: ' + JSON.stringify(e.response.data)
        : '取込に失敗しました。'
  } finally {
    importing.value = false
  }
}
</script>

<template>
  <div class="page">
    <h1 class="page-title">取引履歴CSV取込</h1>

    <div class="card">
      <p class="help">
        楽天証券の「取引履歴 (国内株式)」CSV (tradehistory(JP)_～.csv) を選択してください。
        同じファイルを何度取り込んでも二重登録されません (取込済み・手入力済みの取引は自動スキップ)。
      </p>
      <label class="btn file-btn">
        ファイルを選択
        <input type="file" accept=".csv,text/csv" @change="onFile" />
      </label>
      <p v-if="fileName" class="file-name">{{ fileName }}</p>
      <p v-if="parseError" class="error-message">{{ parseError }}</p>
    </div>

    <div v-if="result" class="card result">
      <p class="result-main">{{ result.imported }}件を取り込みました</p>
      <p v-if="result.skipped_imported" class="sub">取込済みのためスキップ: {{ result.skipped_imported }}件</p>
      <p v-if="result.skipped_manual" class="sub">手入力済みのためスキップ: {{ result.skipped_manual }}件</p>
      <RouterLink to="/trades" class="btn btn-secondary">履歴を見る</RouterLink>
    </div>

    <template v-if="trades.length">
      <div class="card">
        <p class="summary">
          {{ trades.length }}件 (買付 {{ buyCount }} / 売却 {{ sellCount }})
          <template v-if="excluded.length"> ・対象外 {{ excluded.length }}件</template>
        </p>
        <button class="btn" :disabled="importing" @click="doImport">この内容で取り込む</button>
      </div>

      <div class="card preview">
        <table>
          <thead>
            <tr>
              <th>約定日</th>
              <th>銘柄</th>
              <th>売買</th>
              <th class="num">数量×単価</th>
              <th>口座</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(t, i) in trades" :key="i">
              <td class="nowrap">{{ t.trade_date.slice(0, 4) }}年 {{ dateLabel(t.trade_date) }}</td>
              <td>
                <span class="code">{{ t.code }}</span>{{ t.name }}
                <span v-if="t.memo" class="memo-tag">{{ t.memo }}</span>
              </td>
              <td>
                <span class="badge" :class="t.side === 'buy' ? 'badge-buy' : 'badge-sell'">
                  {{ t.side === 'buy' ? '買付' : '売却' }}
                </span>
              </td>
              <td class="num nowrap">
                {{ t.quantity.toLocaleString() }}株 × {{ t.price.toLocaleString() }}円
                <span v-if="t.fee" class="fee">(手数料等 {{ yen(t.fee) }})</span>
              </td>
              <td class="nowrap">{{ accountLabel(t.account_type) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>

    <div v-if="excluded.length" class="card">
      <p class="summary">取込対象外の行</p>
      <p v-for="(x, i) in excluded" :key="i" class="excluded-row">{{ x.label }} — {{ x.reason }}</p>
    </div>
  </div>
</template>

<style scoped>
.help {
  font-size: 0.85rem;
  color: var(--color-text-sub);
  margin-bottom: 12px;
}

.file-btn {
  position: relative;
  overflow: hidden;
}

.file-btn input {
  position: absolute;
  inset: 0;
  opacity: 0;
  cursor: pointer;
}

.file-name {
  margin-top: 8px;
  font-size: 0.85rem;
  color: var(--color-text-sub);
}

.result {
  text-align: center;
}

.result-main {
  font-size: 1.2rem;
  font-weight: 700;
  color: var(--color-primary);
  margin-bottom: 4px;
}

.result .sub {
  font-size: 0.85rem;
  color: var(--color-text-sub);
}

.result .btn {
  margin-top: 12px;
  text-decoration: none;
}

.summary {
  font-weight: 700;
  margin-bottom: 10px;
}

.preview {
  overflow-x: auto;
  padding: 8px;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8rem;
}

th {
  text-align: left;
  color: var(--color-text-sub);
  font-weight: 600;
  padding: 4px 6px;
}

td {
  padding: 6px;
  border-top: 1px solid var(--color-border);
}

.num {
  text-align: right;
}

.nowrap {
  white-space: nowrap;
}

.code {
  color: var(--color-text-sub);
  margin-right: 4px;
}

.fee {
  display: block;
  font-size: 0.7rem;
  color: var(--color-text-sub);
}

.memo-tag {
  font-size: 0.7rem;
  color: var(--color-primary);
  border: 1px solid var(--color-primary);
  border-radius: 4px;
  padding: 0 4px;
  margin-left: 4px;
}

.excluded-row {
  font-size: 0.8rem;
  color: var(--color-text-sub);
  padding: 2px 0;
}
</style>
