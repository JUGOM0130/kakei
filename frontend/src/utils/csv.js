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

// "2026/8/3" "2026-08-03" "2026年8月3日" "26/07/01" → "2026-08-03"
// (三井住友の明細は 2桁年)
export function parseDateCell(s) {
  const m = String(s ?? '')
    .trim()
    .match(/^(\d{2}|\d{4})[/\-年.](\d{1,2})[/\-月.](\d{1,2})/)
  if (!m) return null
  const year = m[1].length === 2 ? `20${m[1]}` : m[1]
  const month = Number(m[2])
  if (month < 1 || month > 12) return null
  return `${year}-${m[2].padStart(2, '0')}-${m[3].padStart(2, '0')}`
}

// "1,234" "¥1,234" "1234円" → 1234
export function parseAmountCell(s) {
  const cleaned = String(s ?? '').replace(/[¥\\,\s円"]/g, '')
  if (!/^-?\d+(\.\d+)?$/.test(cleaned)) return NaN
  return Math.round(Number(cleaned))
}

// 列の自動判定。成功: {headerIndex, dateCol, merchantCol, amountCol, headerLen} / 失敗: null
export function detectColumns(rows) {
  // 1) ヘッダー行を探す (PDF明細はヘッダーが文書の途中にあるため全行を見る)
  //    楽天: 利用日・利用店名・利用金額 / 三井住友: ご利用日・ご利用店名・お支払い金額
  for (let i = 0; i < rows.length; i++) {
    const r = rows[i]
    const dateCol = r.findIndex((c) => /利用日|ご利用日|^日付$/.test(c))
    const merchantCol = r.findIndex((c) => /店名|利用店|商品名|利用内容|摘要/.test(c))
    const amountCol = r.findIndex((c) => /利用金額|ご利用金額|お支払い金額|^金額$/.test(c))
    if (dateCol >= 0 && merchantCol >= 0 && amountCol >= 0) {
      return { headerIndex: i, dateCol, merchantCol, amountCol, headerLen: r.length }
    }
  }
  // 2) ヘッダー無し: 1列目が日付なら [日付, 店名, 金額] の並びと推定。
  // OCR 由来のデータは行が欠けることがあるため 7割一致で判定する
  const data = rows.filter((r) => parseDateCell(r[0]))
  if (data.length >= Math.max(1, rows.length / 2)) {
    const maxCols = Math.max(...data.map((r) => r.length))
    let amountCol = -1
    for (let c = 2; c < maxCols; c++) {
      const hit = data.filter((r) => Number.isFinite(parseAmountCell(r[c]))).length
      if (hit >= data.length * 0.7) {
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

// "8/3" のような年なしの日付セルに年を補う (明細は年を省くことがある)
export function fillYear(rows, year) {
  return rows.map((r) =>
    r.map((c) => (/^\d{1,2}\/\d{1,2}$/.test(c) ? `${year}/${c}` : c))
  )
}

// 判定済みの列割り当てで正規化。{items, skipped}
//
// PDF明細は店名が複数セルに割れて列が右へずれることがある。そこで
// 「日付が読めるデータ行の標準列数 (最頻値)」を基準に:
//   - 標準より長い行は、超過分だけ店名が割れたとみなして店名セルを結合し、
//     金額列も同じ数だけ右へずらす
//   - ヘッダーと同じ列数の行はヘッダーの金額列をそのまま信用する
export function extractRows(rows, { headerIndex, dateCol, merchantCol, amountCol, headerLen }) {
  const dataRows = []
  for (let i = headerIndex + 1; i < rows.length; i++) {
    dataRows.push(rows[i])
  }
  const dated = dataRows.filter((r) => parseDateCell(r[dateCol]))

  // 標準列数 (最頻値)
  const lengthCounts = new Map()
  for (const r of dated) lengthCounts.set(r.length, (lengthCounts.get(r.length) ?? 0) + 1)
  let referenceLen = 0
  let best = -1
  for (const [len, count] of lengthCounts) {
    if (count > best) {
      best = count
      referenceLen = len
    }
  }

  // 標準列数の行における金額列: 店名列より右で最初に「7割の行が数値」になる列
  const refRows = dated.filter((r) => r.length === referenceLen)
  let amountIdxRef = -1
  for (let c = merchantCol + 1; c < referenceLen; c++) {
    const hit = refRows.filter((r) => Number.isFinite(parseAmountCell(r[c]))).length
    if (hit >= refRows.length * 0.7) {
      amountIdxRef = c
      break
    }
  }

  const items = []
  let skipped = 0
  for (const r of dated) {
    let amountIdx
    let span = 1
    if (headerLen && r.length === headerLen) {
      amountIdx = amountCol
    } else {
      const extra = Math.max(0, r.length - referenceLen)
      amountIdx = (amountIdxRef >= 0 ? amountIdxRef : amountCol) + extra
      span = 1 + extra
    }
    let amount = parseAmountCell(r[amountIdx])
    if (!Number.isFinite(amount)) {
      // フォールバック: 店名の直後以降で最初に数値として読めるセル
      amountIdx = -1
      for (let c = merchantCol + span; c < r.length; c++) {
        if (Number.isFinite(parseAmountCell(r[c]))) {
          amountIdx = c
          break
        }
      }
      amount = amountIdx >= 0 ? parseAmountCell(r[amountIdx]) : NaN
    }

    const merchant = r
      .slice(merchantCol, merchantCol + span)
      .join(' ')
      .trim()

    if (!merchant || !Number.isFinite(amount) || amount <= 0) {
      skipped++
      continue
    }
    items.push({ used_date: parseDateCell(r[dateCol]), merchant, amount })
  }
  // 日付が読めず読み飛ばした行 (継続行・合計行など) も件数に含める
  skipped += dataRows.length - dated.length
  return { items, skipped }
}
