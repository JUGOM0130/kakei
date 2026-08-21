// 銘柄マスタ (src/data/stockNames.json) を JPX の上場銘柄一覧から再生成する。
// 新規上場・社名変更を反映したいときに実行:
//   cd kabu
//   npm i --no-save xlsx
//   node scripts/update-stock-names.mjs
import { writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import * as XLSX from 'xlsx'

const PAGE = 'https://www.jpx.co.jp/markets/statistics-equities/misc/01.html'

const html = await (await fetch(PAGE)).text()
const match = html.match(/href="([^"]*data_j[^"]*\.xls)"/)
if (!match) throw new Error('JPX ページから data_j.xls のリンクが見つかりません: ' + PAGE)
const url = new URL(match[1], PAGE).href
console.log('downloading', url)

const buf = Buffer.from(await (await fetch(url)).arrayBuffer())
const wb = XLSX.read(buf)
const rows = XLSX.utils.sheet_to_json(wb.Sheets[wb.SheetNames[0]], { header: 1 })

const header = rows[0].map(String)
const codeIdx = header.findIndex((h) => h.includes('コード') && !h.includes('業種') && !h.includes('規模'))
const nameIdx = header.findIndex((h) => h.includes('銘柄名'))
if (codeIdx < 0 || nameIdx < 0) throw new Error('列構成が変わっています: ' + header.join(','))

const map = {}
for (const row of rows.slice(1)) {
  const code = String(row[codeIdx] ?? '').trim().toUpperCase()
  const name = String(row[nameIdx] ?? '').trim()
  if (code && name) map[code] = name
}

const out = join(dirname(fileURLToPath(import.meta.url)), '..', 'src', 'data', 'stockNames.json')
writeFileSync(out, JSON.stringify(map), 'utf8')
console.log(`${Object.keys(map).length} 銘柄を書き込みました → ${out}`)
