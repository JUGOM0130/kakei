export function yen(n) {
  return '¥' + Number(n ?? 0).toLocaleString('ja-JP')
}

export function monthLabel(month) {
  const [y, m] = month.split('-')
  return `${y}年${Number(m)}月`
}

export function dateLabel(dateStr) {
  const d = new Date(dateStr + 'T00:00:00')
  const week = ['日', '月', '火', '水', '木', '金', '土'][d.getDay()]
  return `${d.getMonth() + 1}/${d.getDate()} (${week})`
}
