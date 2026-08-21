// PDF 明細から表データ (行×セル) を復元する。
// 文字が埋め込まれた PDF (カード会社が生成する明細) が対象。スキャン画像は不可。
// pdfjs-dist は重いので、このモジュールごと動的 import して使う。

import * as pdfjs from 'pdfjs-dist'
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'

pdfjs.GlobalWorkerOptions.workerSrc = workerUrl

// ArrayBuffer → 行×セルの2次元配列。
// テキスト片を Y 座標でグルーピングして行に、X 座標の間隔でセルに分ける。
export async function extractTableFromPdf(buffer) {
  const doc = await pdfjs.getDocument({
    data: buffer,
    // 日本語 CMap (Adobe-Japan1 / 90ms-RKSJ 等)。これが無いと
    // カード会社の明細 PDF (非埋め込み CID フォント) から文字が取れない
    cMapUrl: `${location.origin}${import.meta.env.BASE_URL}cmaps/`,
    cMapPacked: true,
  }).promise
  const rows = []

  for (let pageNo = 1; pageNo <= doc.numPages; pageNo++) {
    const page = await doc.getPage(pageNo)
    const content = await page.getTextContent()

    // Y座標 (transform[5]) でクラスタリング (許容 3pt)
    const lines = []
    for (const item of content.items) {
      const text = item.str
      if (!text || !text.trim()) continue
      const x = item.transform[4]
      const y = item.transform[5]
      let line = lines.find((l) => Math.abs(l.y - y) <= 3)
      if (!line) {
        line = { y, items: [] }
        lines.push(line)
      }
      line.items.push({ x, width: item.width ?? 0, text })
    }

    // 上から下へ、行内は左から右へ
    lines.sort((a, b) => b.y - a.y)
    for (const line of lines) {
      line.items.sort((a, b) => a.x - b.x)
      const cells = []
      let prevEnd = null
      for (const item of line.items) {
        // 直前の文字との隙間が小さければ同じセルとして連結
        if (prevEnd !== null && item.x - prevEnd < 6 && cells.length) {
          cells[cells.length - 1] += item.text
        } else {
          cells.push(item.text)
        }
        prevEnd = item.x + item.width
      }
      rows.push(cells.map((c) => c.trim()).filter((c) => c !== ''))
    }
  }

  await doc.destroy()
  return rows.filter((r) => r.length)
}
