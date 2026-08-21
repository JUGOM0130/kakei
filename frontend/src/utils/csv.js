// カード明細 CSV の読み取りユーティリティ (楽天カード / VPASS などを想定)

// エンコーディング自動判定: UTF-8 として不正なら Shift_JIS とみなす
export function decodeCsv(buffer) {
  try {
    return new TextDecoder('utf-8', { fatal: true }).decode(buffer)
  } catch {
    return new TextDecoder('shift_jis').decode(buffer)
  }
}

// クォート対応の簡易 CSV パーサ
export function parseCsv(text) {
  const rows = []
  let row = []
  let field = ''
  let inQuotes = false
  for (let i = 0; i < text.length; i++) {
    const ch = text[i]
    if (inQuotes) {
      if (ch === '"') {
        if (text[i + 1] === '"') {
          field += '"'
          i++
        } else {
          inQuotes = false
        }
      } else {
        field += ch
      }
    } else if (ch === '"') {
      inQuotes = true
    } else if (ch === ',') {
      row.push(field)
      field = ''
    } else if (ch === '\n') {
      row.push(field)
      rows.push(row)
      row = []
      field = ''
    } else if (ch !== '\r') {
      field += ch
    }
  }
  if (field !== '' || row.length) {
    row.push(field)
    rows.push(row)
  }
  return rows.filter((r) => r.some((c) => c.trim() !== ''))
}

// "2026/8/3" "2026-08-03" "2026年8月3日" → "2026-08-03"
export function parseDateCell(s) {
  const m = String(s ?? '')
    .trim()
    .match(/^(\d{4})[/\-年.](\d{1,2})[/\-月.](\d{1,2})/)
  if (!m) return null
  return `${m[1]}-${m[2].padStart(2, '0')}-${m[3].padStart(2, '0')}`
}

// "1,234" "¥1,234" "1234円" → 1234
export function parseAmountCell(s) {
  const cleaned = String(s ?? '').replace(/[¥\\,\s円"]/g, '')
  if (!/^-?\d+(\.\d+)?$/.test(cleaned)) return NaN
  return Math.round(Number(cleaned))
}

// 列の自動判定。成功: {headerIndex, dateCol, merchantCol, amountCol} / 失敗: null
export function detectColumns(rows) {
  // 1) ヘッダー行を探す (楽天: 利用日・利用店名・商品名・利用金額 / VPASS: ご利用日・ご利用店名・ご利用金額)
  for (let i = 0; i < Math.min(rows.length, 10); i++) {
    const r = rows[i]
    const dateCol = r.findIndex((c) => /利用日|ご利用日|^日付$/.test(c))
    const merchantCol = r.findIndex((c) => /店名|利用店|商品名|利用内容|摘要/.test(c))
    const amountCol = r.findIndex((c) => /利用金額|ご利用金額|^金額$/.test(c))
    if (dateCol >= 0 && merchantCol >= 0 && amountCol >= 0) {
      return { headerIndex: i, dateCol, merchantCol, amountCol }
    }
  }
  // 2) ヘッダー無し: 1列目が日付なら [日付, 店名, 金額] の並びと推定
  const data = rows.filter((r) => parseDateCell(r[0]))
  if (data.length >= Math.max(1, rows.length / 2)) {
    const sample = data[0]
    let amountCol = -1
    for (let c = 2; c < sample.length; c++) {
      const ok = data.every((r) => {
        const n = parseAmountCell(r[c])
        return Number.isFinite(n)
      })
      if (ok) {
        amountCol = c
        break
      }
    }
    if (amountCol >= 0) {
      return { headerIndex: -1, dateCol: 0, merchantCol: 1, amountCol }
    }
  }
  return null
}

// 判定済みの列割り当てで正規化。{items, skipped}
export function extractRows(rows, { headerIndex, dateCol, merchantCol, amountCol }) {
  const items = []
  let skipped = 0
  for (let i = headerIndex + 1; i < rows.length; i++) {
    const r = rows[i]
    const usedDate = parseDateCell(r[dateCol])
    const amount = parseAmountCell(r[amountCol])
    const merchant = String(r[merchantCol] ?? '').trim()
    if (!usedDate || !merchant || !Number.isFinite(amount) || amount <= 0) {
      skipped++
      continue
    }
    items.push({ used_date: usedDate, merchant, amount })
  }
  return { items, skipped }
}
