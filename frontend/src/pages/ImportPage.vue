<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import dayjs from 'dayjs'
import api from '../api/client'
import { useLedgerStore } from '../stores/ledger'
import { useGroupStore } from '../stores/group'
import { yen } from '../utils/format'
import { decodeCsv, parseCsv, detectColumns, extractRows, fillYear } from '../utils/csv'

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
const refundNote = ref(null) // {count, total, matched, unmatchedTotal}
const paidRecurring = ref({}) // {rp_id: 'standalone'|'imported'} その月に支払記録済みの固定費
const propagateNote = ref('')
let propagateNoteTimer = null
const recurringNote = ref(null) // {replaced: [names], blocked: [names]}
const parentDate = ref(dayjs().format('YYYY-MM-DD'))
const parentAmount = ref('')
const parentCategoryId = ref(null)
const error = ref('')
const loading = ref(false)
const parsing = ref(false)
const ocrCandidate = ref(null) // 画像PDFと判定されたファイル (OCRの提案用)
const ocrRunning = ref(false)

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

const activeRecurring = computed(() => ledger.recurring.filter((r) => r.is_active))

onMounted(async () => {
  await Promise.all([
    ledger.fetchCategories(),
    ledger.fetchPaymentMethods(),
    ledger.fetchRecurring(),
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
  ocrCandidate.value = null
  refundNote.value = null
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
      const { extractTableFromPdf } = await import('../utils/pdf')
      rows = fillYear(await extractTableFromPdf(buffer), dayjs().year())
    } catch (e) {
      error.value =
        `PDF を読み取れませんでした (詳細: ${e?.message || e})。` +
        'パスワード付きの PDF は解除してから試してください。'
      ocrCandidate.value = file // OCR でなら読める可能性がある
      parsing.value = false
      return
    }
    parsing.value = false
    if (!rows.length) {
      // 文字なし = 画像PDF → サーバーOCR を提案
      ocrCandidate.value = file
      error.value = ''
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

async function runOcr() {
  if (!ocrCandidate.value) return
  error.value = ''
  ocrRunning.value = true
  try {
    const form = new FormData()
    form.append('file', ocrCandidate.value)
    const { data } = await api.post('/import/ocr/', form, { timeout: 180000 })
    const rows = fillYear(data.rows, dayjs().year())
    if (!rows.length) {
      error.value = 'OCR でも明細を見つけられませんでした。'
      return
    }
    rawRows.value = rows
    ocrCandidate.value = null
    const mapping = detectColumns(rows)
    if (mapping) {
      await buildPreview(mapping)
    } else {
      needManualMapping.value = true
    }
  } catch (e) {
    error.value = e.response?.data?.detail || 'OCR 処理に失敗しました。'
  } finally {
    ocrRunning.value = false
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
  const { items, skipped, refunds } = extractRows(rawRows.value, mapping)
  skippedCount.value = skipped
  if (!items.length) {
    error.value = '取込める明細がありません。列の割り当てを確認してください。'
    needManualMapping.value = true
    return
  }
  needManualMapping.value = false
  error.value = ''

  // 学習済みルールの取得 (店名+金額で問い合わせ → 金額付きルールが優先で返る)
  const month = items[0].used_date.slice(0, 7)
  let rowSuggestions = []
  try {
    const { data } = await api.post('/import/suggest/', {
      rows: items.map((i) => ({ merchant: i.merchant, amount: i.amount })),
      payment_method_id: paymentMethodId.value,
      month,
    })
    rowSuggestions = data.row_suggestions ?? []
    existingWarning.value = data.existing_statement
    paidRecurring.value = data.paid_recurring ?? {}
  } catch {
    /* 提案なしで続行 */
  }

  const fallback = defaultCategoryId()
  const myShare = groupStore.me?.share_percent ?? 50
  previewRows.value = items.map((item, i) => {
    const rule = rowSuggestions[i]
    return {
      ...item,
      include: true,
      refunded: false,
      category_id: rule?.category_id ?? fallback,
      shared: rule?.shared ?? false,
      share_percent: rule?.payer_share_percent ?? myShare,
      recurring_payment_id: rule?.recurring_payment_id ?? null,
    }
  })

  // 返品 (マイナス行) の相殺: 同額の購入明細を探してチェックを自動で外す。
  // 請求合計の初期値も返品を差し引いた実際の請求額にする
  refundNote.value = null
  let matched = 0
  let refundTotal = 0
  for (const refund of refunds ?? []) {
    refundTotal += -refund.amount
    const target =
      previewRows.value.find(
        (r) => r.include && !r.refunded && r.amount === -refund.amount && r.merchant === refund.merchant
      ) ??
      previewRows.value.find((r) => r.include && !r.refunded && r.amount === -refund.amount)
    if (target) {
      target.include = false
      target.refunded = true
      matched++
    }
  }
  if (refunds?.length) {
    refundNote.value = {
      count: refunds.length,
      total: refundTotal,
      matched,
      unmatched: refunds.length - matched,
    }
  }
  parentAmount.value = String(allTotal.value - refundTotal)

  // 固定費との重複防止: 学習で自動リンクされた行のうち、
  // その月に既に支払記録がある固定費を確認する
  recurringNote.value = null
  const replaced = []
  const blocked = []
  for (const row of previewRows.value) {
    if (!row.recurring_payment_id) continue
    const status = paidRecurring.value[String(row.recurring_payment_id)]
    if (status === 'imported') {
      // 別の取込で記録済み → 紐付け解除 (二重計上防止)
      const rp = activeRecurring.value.find((r) => r.id === row.recurring_payment_id)
      if (rp) blocked.push(rp.name)
      row.recurring_payment_id = null
    } else if (status === 'standalone') {
      const rp = activeRecurring.value.find((r) => r.id === row.recurring_payment_id)
      if (rp) replaced.push(rp.name)
    }
  }
  if (replaced.length || blocked.length) {
    recurringNote.value = { replaced, blocked }
  }
}

// この明細の内容で定期支払 (固定費) を新規作成して紐付ける
async function createRecurringFromRow(row) {
  try {
    const { data } = await api.post('/recurring-payments/', {
      name: row.merchant.slice(0, 100),
      amount: row.amount,
      category_id: row.category_id,
      payment_method_id: paymentMethodId.value,
      day_of_month: Number(row.used_date.slice(8, 10)),
      interval_months: 1,
      is_shared: row.shared,
      payer_share_percent: Number(row.share_percent),
    })
    await ledger.fetchRecurring()
    await nextTick() // 新しい選択肢が描画されてから選択状態を反映する
    row.recurring_payment_id = data.id
  } catch (e) {
    alert(e.response?.data?.detail || '固定費の登録に失敗しました。')
  }
}

function onRecurringLink(row) {
  const rp = activeRecurring.value.find((r) => r.id === row.recurring_payment_id)
  if (!rp) return
  // 二重計上防止: 既に取込済みの固定費には紐付けない
  const status = paidRecurring.value[String(rp.id)]
  if (status === 'imported') {
    alert(`「${rp.name}」はこの月に既に取込済みのため紐付けできません。`)
    row.recurring_payment_id = null
    return
  }
  if (status === 'standalone') {
    alert(
      `「${rp.name}」はこの月に「支払済にする」の記録があります。取込時にその記録をこの明細で置き換えます (二重計上にはなりません)。`
    )
  }
  // カテゴリも定期支払側に合わせる
  row.category_id = rp.category.id
}

function setAllShared(shared) {
  for (const row of previewRows.value) {
    if (row.refunded) continue
    row.shared = shared
  }
}

// カテゴリ変更を「同じ店名・同じ金額」の行に一括適用する
// (例: ＥＴＣカード売上 1,190円 × 16行 → 1回の変更で全行が通勤ETCに)
function propagateCategory(row) {
  let count = 0
  for (const other of previewRows.value) {
    if (other === row) continue
    if (other.merchant === row.merchant && other.amount === row.amount) {
      other.category_id = row.category_id
      count++
    }
  }
  if (count > 0) {
    propagateNote.value = `同じ店名・同額の ${count} 行にも適用しました`
    clearTimeout(propagateNoteTimer)
    propagateNoteTimer = setTimeout(() => (propagateNote.value = ''), 2500)
  }
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
        recurring_payment_id: r.recurring_payment_id,
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

    <!-- 画像PDF → サーバーOCRの提案 -->
    <div v-if="ocrCandidate" class="card">
      <div class="heading">画像タイプの PDF です</div>
      <p class="hint">
        この PDF には文字データが埋め込まれていません。サーバーで文字認識 (OCR)
        して読み取れます (最大3ページ・1分ほどかかることがあります)。
        <strong>金額や店名を誤認識することがあるため、取込前にプレビューを必ず確認してください。</strong>
      </p>
      <p v-if="error" class="error-message">{{ error }}</p>
      <button class="btn" :disabled="ocrRunning" @click="runOcr">
        {{ ocrRunning ? 'サーバーで解析中...' : 'サーバーで読み取る (OCR)' }}
      </button>
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

      <div v-if="refundNote" class="card" :class="{ warn: refundNote.unmatched > 0 }">
        <template v-if="refundNote.unmatched === 0">
          ↩ 返品 {{ refundNote.count }}件 ({{ yen(refundNote.total) }}) を検出し、対応する明細のチェックを自動で外しました。請求合計も返品後の金額にしています。
        </template>
        <template v-else>
          ⚠ 返品 {{ refundNote.count }}件 ({{ yen(refundNote.total) }}) のうち
          {{ refundNote.unmatched }}件は対応する明細を特定できませんでした。取込合計が請求合計を超える場合は、該当する明細のチェックを手動で外してください。
        </template>
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

      <div v-if="recurringNote" class="card" :class="{ warn: recurringNote.blocked.length }">
        <template v-if="recurringNote.replaced.length">
          🔁 {{ recurringNote.replaced.join('・') }} は「支払済にする」の単独記録があるため、取込時にこの明細で置き換えます (二重計上になりません)。<br />
        </template>
        <template v-if="recurringNote.blocked.length">
          ⚠ {{ recurringNote.blocked.join('・') }} はこの月に既に取込済みのため、紐付けを解除しました。
        </template>
      </div>

      <div class="card">
        <div class="heading">
          明細 {{ previewRows.length }}件
          <span v-if="skippedCount" class="hint-inline">(読み飛ばし {{ skippedCount }}件)</span>
        </div>
        <p class="hint">
          カテゴリを変えると同じ店名・同額の行にも一括適用され、次回の取込から自動で同じ設定になります。
        </p>
        <p v-if="propagateNote" class="propagate-note">✓ {{ propagateNote }}</p>
        <div v-if="hasGroup" class="bulk-row">
          <button class="btn btn-secondary btn-small" @click="setAllShared(true)">
            👥 全行を折半にする
          </button>
          <button class="btn btn-secondary btn-small" @click="setAllShared(false)">
            全行を自分のみに
          </button>
        </div>
        <div v-for="(r, i) in previewRows" :key="i" class="row" :class="{ excluded: !r.include }">
          <input v-model="r.include" type="checkbox" class="check" />
          <div class="info">
            <div class="merchant">
              {{ r.merchant }}
              <span v-if="r.refunded" class="refund-badge">返品相殺</span>
            </div>
            <div class="sub">{{ r.used_date }}</div>
            <div class="controls">
              <select v-model="r.category_id" class="cat-select" @change="propagateCategory(r)">
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
            <div class="controls">
              <select
                v-model="r.recurring_payment_id"
                class="cat-select"
                :class="{ linked: r.recurring_payment_id }"
                @change="onRecurringLink(r)"
              >
                <option :value="null">🔁 定期支払に紐付けない</option>
                <option v-for="rp in activeRecurring" :key="rp.id" :value="rp.id">
                  🔁 {{ rp.name }}
                </option>
              </select>
              <button
                v-if="!r.recurring_payment_id"
                class="chip chip-mini"
                @click="createRecurringFromRow(r)"
              >
                ＋固定費に登録
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

.bulk-row {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
}

.propagate-note {
  color: var(--color-primary);
  font-size: 0.8rem;
  font-weight: 600;
  margin-bottom: 6px;
}

.refund-badge {
  font-size: 0.65rem;
  font-weight: 600;
  border-radius: 999px;
  padding: 1px 8px;
  background: var(--warn-soft, #fdf3e2);
  color: #8a5a12;
}

.total-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 700;
}
</style>
