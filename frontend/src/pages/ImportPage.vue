<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import dayjs from 'dayjs'
import api from '../api/client'
import { useLedgerStore } from '../stores/ledger'
import { useGroupStore } from '../stores/group'
import { yen } from '../utils/format'
import { decodeCsv, parseCsv, detectColumns, extractRows } from '../utils/csv'

const router = useRouter()
const ledger = useLedgerStore()
const groupStore = useGroupStore()

const paymentMethodId = ref(null)
const rawRows = ref([]) // パース済み CSV の生データ (手動割り当て用)
const previewRows = ref([]) // [{used_date, merchant, amount, include, category_id, shared, share_percent}]
const skippedCount = ref(0)
const needManualMapping = ref(false)
const manualDateCol = ref(0)
const manualMerchantCol = ref(1)
const manualAmountCol = ref(2)
const existingWarning = ref(false)
const parentDate = ref(dayjs().format('YYYY-MM-DD'))
const parentAmount = ref('')
const parentCategoryId = ref(null)
const error = ref('')
const loading = ref(false)
const parsing = ref(false)

const expenseCategories = computed(() =>
  ledger.categories.filter((c) => c.type === 'expense')
)
const hasGroup = computed(() => !!groupStore.group)
const included = computed(() => previewRows.value.filter((r) => r.include))
const includedTotal = computed(() => included.value.reduce((s, r) => s + r.amount, 0))
const allTotal = computed(() => previewRows.value.reduce((s, r) => s + r.amount, 0))
const columnCount = computed(() =>
  rawRows.value.length ? Math.max(...rawRows.value.map((r) => r.length)) : 0
)

onMounted(async () => {
  await Promise.all([
    ledger.fetchCategories(),
    ledger.fetchPaymentMethods(),
    groupStore.loaded ? Promise.resolve() : groupStore.fetch(),
  ])
  paymentMethodId.value = ledger.paymentMethods.find((m) => m.name !== '現金')?.id ?? null
  const other = expenseCategories.value.find((c) => c.name === 'その他')
  parentCategoryId.value = other?.id ?? expenseCategories.value[0]?.id ?? null
})

function defaultCategoryId() {
  const other = expenseCategories.value.find((c) => c.name === 'その他')
  return other?.id ?? expenseCategories.value[0]?.id ?? null
}

async function onFileSelected(event) {
  error.value = ''
  needManualMapping.value = false
  previewRows.value = []
  const file = event.target.files?.[0]
  if (!file) return
  const buffer = await file.arrayBuffer()

  // ファイル種別は中身で判定する (スマホはファイル名や MIME が当てにならない)
  const head = new TextDecoder('ascii').decode(new Uint8Array(buffer.slice(0, 5)))
  const isPdf = head === '%PDF-'

  let rows
  if (isPdf) {
    parsing.value = true
    try {
      // pdfjs は重いので使うときだけ読み込む
      const { extractTableFromPdf, fillYear } = await import('../utils/pdf')
      rows = fillYear(await extractTableFromPdf(buffer), dayjs().year())
    } catch (e) {
      error.value =
        `PDF を読み取れませんでした (詳細: ${e?.message || e})。` +
        'パスワード付き・画像スキャンの PDF は取込できません。'
      parsing.value = false
      return
    }
    parsing.value = false
    if (!rows.length) {
      error.value =
        'PDF から文字を取り出せませんでした。画像として保存された PDF の可能性があります。'
      return
    }
  } else {
    rows = parseCsv(decodeCsv(buffer))
  }

  if (!rows.length) {
    error.value = 'ファイルを読み取れませんでした。'
    return
  }
  rawRows.value = rows
  const mapping = detectColumns(rows)
  if (mapping) {
    await buildPreview(mapping)
  } else {
    needManualMapping.value = true
  }
}

async function applyManualMapping() {
  await buildPreview({
    headerIndex: -1,
    dateCol: Number(manualDateCol.value),
    merchantCol: Number(manualMerchantCol.value),
    amountCol: Number(manualAmountCol.value),
  })
}

async function buildPreview(mapping) {
  const { items, skipped } = extractRows(rawRows.value, mapping)
  skippedCount.value = skipped
  if (!items.length) {
    error.value = '取込める明細がありません。列の割り当てを確認してください。'
    needManualMapping.value = true
    return
  }
  needManualMapping.value = false
  error.value = ''

  // 学習済みルールの取得
  const month = items[0].used_date.slice(0, 7)
  let suggestions = {}
  try {
    const { data } = await api.post('/import/suggest/', {
      merchants: [...new Set(items.map((i) => i.merchant))],
      payment_method_id: paymentMethodId.value,
      month,
    })
    suggestions = data.suggestions
    existingWarning.value = data.existing_statement
  } catch {
    /* 提案なしで続行 */
  }

  const fallback = defaultCategoryId()
  const myShare = groupStore.me?.share_percent ?? 50
  previewRows.value = items.map((item) => {
    const rule = suggestions[item.merchant]
    return {
      ...item,
      include: true,
      category_id: rule?.category_id ?? fallback,
      shared: rule?.shared ?? false,
      share_percent: rule?.payer_share_percent ?? myShare,
    }
  })
  parentAmount.value = String(allTotal.value)
}

async function submit() {
  error.value = ''
  if (!paymentMethodId.value) {
    error.value = 'カード (支払方法) を選択してください。'
    return
  }
  if (!included.value.length) {
    error.value = '取込む明細を選択してください。'
    return
  }
  const parentValue = Number(parentAmount.value)
  if (!parentValue) {
    error.value = '請求合計を入力してください。'
    return
  }
  loading.value = true
  try {
    await api.post('/import/transactions/', {
      payment_method_id: paymentMethodId.value,
      parent: {
        date: parentDate.value,
        amount: parentValue,
        category_id: parentCategoryId.value,
        memo: 'CSV取込',
      },
      rows: included.value.map((r) => ({
        merchant: r.merchant,
        used_date: r.used_date,
        amount: r.amount,
        category_id: r.category_id,
        shared: r.shared,
        payer_share_percent: r.shared ? Number(r.share_percent) : null,
      })),
    })
    router.push('/transactions')
  } catch (e) {
    const data = e.response?.data
    error.value =
      data?.parent?.[0] || data?.rows?.[0] || data?.detail || '取込に失敗しました。'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="page">
    <h1 class="page-title">CSV取込 (カード明細)</h1>

    <div class="card">
      <label for="imp-method">カード (支払方法)</label>
      <select id="imp-method" v-model="paymentMethodId">
        <option v-for="m in ledger.paymentMethods" :key="m.id" :value="m.id">
          {{ m.name }}
        </option>
      </select>
      <label for="imp-file">明細ファイル (CSV / PDF)</label>
      <!-- accept は指定しない: スマホのファイルピッカーが PDF/CSV を
           グレーアウトすることがあるため。種別は中身で自動判定する -->
      <input id="imp-file" type="file" @change="onFileSelected" />
      <p v-if="parsing" class="hint">PDF を解析中...</p>
      <p class="hint">
        VPASS / 楽天カード e-NAVI の明細 CSV・PDF に対応 (文字コード・列は自動判定)。
        PDF はレイアウトのばらつきで読み取れないことがあります。その場合は PC
        版サイトから CSV をダウンロードするのが確実です。
      </p>
    </div>

    <!-- 列の手動割り当て (自動判定に失敗したとき) -->
    <div v-if="needManualMapping" class="card">
      <div class="heading">列の割り当て</div>
      <p class="hint">
        形式を自動判定できませんでした。下の読み取り結果を見て、各項目がどの列かを指定してください
        (うまくいかない場合はこの画面のスクリーンショットがあれば調整できます)。
      </p>
      <div class="table-scroll">
        <table class="sample">
          <tr v-for="(r, i) in rawRows.slice(0, 10)" :key="i">
            <td class="rowno">{{ i + 1 }}</td>
            <td v-for="(c, j) in r" :key="j">{{ c }}</td>
          </tr>
        </table>
      </div>
      <label>日付の列</label>
      <select v-model="manualDateCol">
        <option v-for="n in columnCount" :key="n" :value="n - 1">{{ n }}列目</option>
      </select>
      <label>店名の列</label>
      <select v-model="manualMerchantCol">
        <option v-for="n in columnCount" :key="n" :value="n - 1">{{ n }}列目</option>
      </select>
      <label>金額の列</label>
      <select v-model="manualAmountCol">
        <option v-for="n in columnCount" :key="n" :value="n - 1">{{ n }}列目</option>
      </select>
      <button class="btn apply" @click="applyManualMapping">この割り当てで読み込む</button>
    </div>

    <!-- プレビュー -->
    <template v-if="previewRows.length">
      <div v-if="existingWarning" class="card warn">
        ⚠ この月のこのカードには取込済みの請求があります。二重取込にご注意ください。
      </div>

      <div class="card">
        <div class="heading">請求 (親として1件登録)</div>
        <label for="imp-date">請求日 (引落日)</label>
        <input id="imp-date" v-model="parentDate" type="date" />
        <label for="imp-amount">請求合計</label>
        <input
          id="imp-amount"
          v-model="parentAmount"
          type="text"
          inputmode="numeric"
          pattern="[0-9]*"
          @input="parentAmount = parentAmount.replace(/[^0-9]/g, '')"
        />
        <label for="imp-cat">残額のカテゴリ</label>
        <select id="imp-cat" v-model="parentCategoryId">
          <option v-for="c in expenseCategories" :key="c.id" :value="c.id">{{ c.name }}</option>
        </select>
      </div>

      <div class="card">
        <div class="heading">
          明細 {{ previewRows.length }}件
          <span v-if="skippedCount" class="hint-inline">(読み飛ばし {{ skippedCount }}件)</span>
        </div>
        <div v-for="(r, i) in previewRows" :key="i" class="row" :class="{ excluded: !r.include }">
          <input v-model="r.include" type="checkbox" class="check" />
          <div class="info">
            <div class="merchant">{{ r.merchant }}</div>
            <div class="sub">{{ r.used_date }}</div>
            <div class="controls">
              <select v-model="r.category_id" class="cat-select">
                <option v-for="c in expenseCategories" :key="c.id" :value="c.id">
                  {{ c.name }}
                </option>
              </select>
              <button
                v-if="hasGroup"
                class="chip chip-mini"
                :class="{ active: r.shared }"
                @click="r.shared = !r.shared"
              >
                👥 {{ r.shared ? '共有' : '共有しない' }}
              </button>
            </div>
          </div>
          <span class="amount">{{ yen(r.amount) }}</span>
        </div>
      </div>

      <div class="card total-bar">
        <span>取込 {{ included.length }}件 / {{ yen(includedTotal) }}</span>
        <span class="hint-inline">請求合計 {{ yen(Number(parentAmount || 0)) }}</span>
      </div>

      <p v-if="error" class="error-message">{{ error }}</p>
      <button class="btn" :disabled="loading" @click="submit">取込む</button>
    </template>
    <p v-else-if="error" class="error-message">{{ error }}</p>
  </div>
</template>

<style scoped>
.heading {
  font-weight: 700;
  margin-bottom: 8px;
}

.hint {
  font-size: 0.78rem;
  color: var(--color-text-sub);
  margin-top: 8px;
}

.hint-inline {
  font-size: 0.75rem;
  color: var(--color-text-sub);
  font-weight: 400;
}

.warn {
  border-left: 4px solid #e6a817;
  color: #8a5a12;
  font-size: 0.85rem;
}

.table-scroll {
  overflow-x: auto;
  margin: 8px 0;
}

.sample {
  border-collapse: collapse;
  font-size: 0.7rem;
  white-space: nowrap;
}

.sample td {
  border: 1px solid var(--color-border);
  padding: 3px 6px;
}

.sample .rowno {
  color: var(--color-text-sub);
  background: var(--color-bg);
}

.apply {
  margin-top: 16px;
}

.row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 10px 0;
  border-bottom: 1px solid var(--color-border);
}

.row:last-child {
  border-bottom: none;
}

.row.excluded {
  opacity: 0.4;
}

.check {
  width: 22px;
  height: 22px;
  margin-top: 2px;
  flex-shrink: 0;
}

.info {
  flex: 1;
  min-width: 0;
}

.merchant {
  font-weight: 600;
  font-size: 0.9rem;
  word-break: break-all;
}

.sub {
  font-size: 0.72rem;
  color: var(--color-text-sub);
}

.controls {
  display: flex;
  gap: 6px;
  margin-top: 4px;
  align-items: center;
  flex-wrap: wrap;
}

.cat-select {
  width: auto;
  min-height: 36px;
  padding: 4px 8px;
  font-size: 0.85rem;
}

.chip-mini {
  min-height: 36px;
  padding: 4px 10px;
  font-size: 0.78rem;
}

.amount {
  font-weight: 700;
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}

.total-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 700;
}
</style>
