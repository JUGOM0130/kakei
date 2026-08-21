export function yen(n) {
  return '¥' + Number(n ?? 0).toLocaleString('ja-JP')
}

// 通貨付き金額。円は ¥1,234、外貨は 0.39 USドル のように表示する
export function money(n, currency) {
  if (!currency || currency === '円') return yen(n)
  const v = Number(n ?? 0)
  return `${v.toLocaleString('ja-JP', { maximumFractionDigits: 2 })} ${currency}`
}

// 損益表示用: プラスに + を付ける
export function signedYen(n) {
  const v = Number(n ?? 0)
  return (v > 0 ? '+' : '') + yen(v).replace('¥-', '-¥')
}

export function pnlClass(n) {
  const v = Number(n ?? 0)
  return v > 0 ? 'gain' : v < 0 ? 'loss' : ''
}

// ISO 日時 → '8/22 09:15' (株価の取得時点表示用)
export function timeLabel(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const hh = String(d.getHours()).padStart(2, '0')
  const mm = String(d.getMinutes()).padStart(2, '0')
  return `${d.getMonth() + 1}/${d.getDate()} ${hh}:${mm}`
}

export function dateLabel(dateStr) {
  const d = new Date(dateStr + 'T00:00:00')
  const week = ['日', '月', '火', '水', '木', '金', '土'][d.getDay()]
  return `${d.getMonth() + 1}/${d.getDate()} (${week})`
}

export const ACCOUNT_TYPES = [
  { value: 'tokutei', label: '特定' },
  { value: 'nisa_growth', label: 'NISA成長' },
  { value: 'nisa_tsumitate', label: 'NISAつみたて' },
  { value: 'ippan', label: '一般' },
]

export function accountLabel(value) {
  return ACCOUNT_TYPES.find((a) => a.value === value)?.label || value
}
