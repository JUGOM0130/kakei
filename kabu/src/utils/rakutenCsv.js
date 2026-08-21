// 楽天証券「取引履歴 (国内株式)」CSV (tradehistory(JP)_*.csv, Shift_JIS) の解析。
// 列はヘッダー名で特定するので列順の変化に強い。

import { normalizeCode } from './stockNames'

// 引用符・引用符内カンマ対応の素朴な CSV パーサ
export function parseCsv(text) {
  const rows = []
  let row = []
  let field = ''
  let inQuotes = false
  for (let i = 0; i < text.length; i++) {
    const c = text[i]
    if (inQuotes) {
      if (c === '"') {
        if (text[i + 1] === '"') {
          field += '"'
          i++
        } else {
          inQuotes = false
        }
      } else {
        field += c
      }
    } else if (c === '"') {
      inQuotes = true
    } else if (c === ',') {
      row.push(field)
      field = ''
    } else if (c === '\n' || c === '\r') {
      if (c === '\r' && text[i + 1] === '\n') i++
      row.push(field)
      field = ''
      if (row.some((v) => v !== '')) rows.push(row)
      row = []
    } else {
      field += c
    }
  }
  row.push(field)
  if (row.some((v) => v !== '')) rows.push(row)
  return rows
}

function toNumber(v) {
  const s = String(v ?? '').replace(/,/g, '').trim()
  if (!s || s === '-') return 0
  const n = Number(s)
  return Number.isFinite(n) ? n : 0
}

function toDate(v) {
  // '2024/1/10' → '2024-01-10'
  const m = String(v ?? '').match(/^(\d{4})\/(\d{1,2})\/(\d{1,2})/)
  if (!m) return null
  return `${m[1]}-${m[2].padStart(2, '0')}-${m[3].padStart(2, '0')}`
}

function mapSide(v) {
  if (v.includes('買付') || v.includes('積立')) return 'buy'
  if (v.includes('売付') || v.includes('売却')) return 'sell'
  return null
}

function mapAccount(v) {
  if (v.includes('つみたて')) return 'nisa_tsumitate'
  if (v.includes('NISA') || v.includes('ＮＩＳＡ')) return 'nisa_growth'
  if (v.includes('特定')) return 'tokutei'
  return 'ippan'
}

export async function readFileAsText(file) {
  const buf = await file.arrayBuffer()
  // 楽天は Shift_JIS。UTF-8 で保存し直したファイルにも対応
  const sjis = new TextDecoder('shift_jis').decode(buf)
  if (sjis.includes('約定日')) return sjis
  return new TextDecoder('utf-8').decode(buf)
}

export function parseRakutenTradeCsv(text) {
  const rows = parseCsv(text)
  const headerIdx = rows.findIndex((r) => r.some((c) => c.includes('約定日')) && r.some((c) => c.includes('銘柄コード')))
  if (headerIdx < 0) {
    throw new Error('楽天証券の取引履歴CSVではないようです (「約定日」「銘柄コード」列が見つかりません)。')
  }
  const header = rows[headerIdx]
  const col = (label) => header.findIndex((h) => h.includes(label))
  const idx = {
    date: col('約定日'),
    code: col('銘柄コード'),
    name: col('銘柄名'),
    account: col('口座区分'),
    tradeType: col('取引区分'),
    side: col('売買区分'),
    quantity: col('数量'),
    price: col('単価'),
    fee: col('手数料'),
    tax: col('税金等'),
    cost: col('諸費用'),
  }

  const trades = []
  const excluded = []
  for (const r of rows.slice(headerIdx + 1)) {
    const label = `${r[idx.date]} ${r[idx.code]} ${r[idx.name]}`
    const tradeType = r[idx.tradeType] || ''
    if (!tradeType.includes('現物')) {
      excluded.push({ label, reason: `現物以外 (${tradeType})` })
      continue
    }
    const side = mapSide(r[idx.side] || '')
    if (!side) {
      excluded.push({ label, reason: `未対応の売買区分 (${r[idx.side]})` })
      continue
    }
    const trade_date = toDate(r[idx.date])
    const quantity = toNumber(r[idx.quantity])
    const price = toNumber(r[idx.price])
    if (!trade_date || quantity <= 0 || price <= 0) {
      excluded.push({ label, reason: '日付・数量・単価を読み取れません' })
      continue
    }
    trades.push({
      trade_date,
      code: normalizeCode(r[idx.code]),
      name: (r[idx.name] || '').trim(),
      side,
      quantity,
      price,
      fee: toNumber(r[idx.fee]) + toNumber(r[idx.tax]) + toNumber(r[idx.cost]),
      account_type: mapAccount(r[idx.account] || ''),
      broker: '楽天証券',
      memo: (r[idx.side] || '').includes('積立') ? '積立' : '',
    })
  }
  return { trades, excluded }
}
