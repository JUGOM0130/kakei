// 銘柄マスタ (JPX 上場銘柄一覧から生成した src/data/stockNames.json)。
// 更新方法は scripts/update-stock-names.mjs 参照。
// 85KB あるので初回参照時に動的 import で遅延ロードする。
let namesPromise = null

function loadNames() {
  if (!namesPromise) {
    namesPromise = import('../data/stockNames.json').then((m) => m.default)
  }
  return namesPromise
}

// 全角英数字→半角 + 大文字化 (「７２０３」「285a」等の入力ゆれを吸収)
export function normalizeCode(raw) {
  return String(raw || '')
    .trim()
    .replace(/[０-９Ａ-Ｚａ-ｚ]/g, (c) => String.fromCharCode(c.charCodeAt(0) - 0xfee0))
    .toUpperCase()
}

export async function lookupStockName(code) {
  const c = normalizeCode(code)
  if (!c) return null
  const names = await loadNames()
  return names[c] || null
}
