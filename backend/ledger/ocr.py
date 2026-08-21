"""画像PDF の明細を OCR して 行×セル に復元する。

pdftoppm (poppler-utils) で PDF を PNG 化し、tesseract (jpn) の TSV 出力から
単語の座標を使って行 (top) とセル (left の間隔) を組み立てる。
フロントの CSV/PDF 取込と同じ「2次元配列」を返し、列判定は共通処理に任せる。
"""

import glob
import os
import subprocess
import tempfile

MAX_PAGES = 3
DPI = 200


class OcrUnavailableError(Exception):
    """tesseract / poppler が未導入"""


def parse_tsv(tsv_text, gap_px):
    """tesseract の TSV 出力 → 行×セル"""
    words = []
    for line in tsv_text.splitlines()[1:]:
        parts = line.split("\t")
        if len(parts) < 12:
            continue
        text = parts[11].strip()
        if not text:
            continue
        try:
            left, top = int(parts[6]), int(parts[7])
            width, height = int(parts[8]), int(parts[9])
            conf = float(parts[10])
        except ValueError:
            continue
        if conf < 0:  # -1 は単語でない構造行
            continue
        words.append(
            {"left": left, "top": top, "width": width, "height": height, "text": text}
        )

    # 縦方向の重なりで行にクラスタリング (固定閾値だと僅かなベースラインずれで分裂する)
    def _overlaps(row, word):
        inter = min(row["bottom"], word["top"] + word["height"]) - max(
            row["top"], word["top"]
        )
        smaller = min(row["bottom"] - row["top"], word["height"]) or 1
        return inter > 0.5 * smaller

    rows = []
    for word in sorted(words, key=lambda w: w["top"]):
        row = next((r for r in rows if _overlaps(r, word)), None)
        if row is None:
            row = {"top": word["top"], "bottom": word["top"] + word["height"], "items": []}
            rows.append(row)
        else:
            row["top"] = min(row["top"], word["top"])
            row["bottom"] = max(row["bottom"], word["top"] + word["height"])
        row["items"].append(word)

    result = []
    for row in sorted(rows, key=lambda r: r["top"]):
        items = sorted(row["items"], key=lambda w: w["left"])
        cells = []
        prev_end = None
        for item in items:
            # 直前の単語との隙間が小さければ同じセルとして連結
            if prev_end is not None and item["left"] - prev_end < gap_px and cells:
                cells[-1] += item["text"]
            else:
                cells.append(item["text"])
            prev_end = item["left"] + item["width"]
        cells = [c.strip() for c in cells if c.strip()]
        if cells:
            result.append(cells)
    return result


def ocr_pdf(pdf_bytes):
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = os.path.join(tmpdir, "in.pdf")
        with open(pdf_path, "wb") as f:
            f.write(pdf_bytes)
        try:
            subprocess.run(
                [
                    "pdftoppm", "-r", str(DPI), "-png",
                    "-f", "1", "-l", str(MAX_PAGES),
                    pdf_path, os.path.join(tmpdir, "pg"),
                ],
                check=True,
                capture_output=True,
                timeout=120,
            )
        except FileNotFoundError:
            raise OcrUnavailableError("poppler-utils (pdftoppm) が未導入です")

        rows = []
        gap_px = int(DPI * 0.125)  # 200dpi で 25px ≒ 全角1文字強の隙間
        for png in sorted(glob.glob(os.path.join(tmpdir, "pg*.png"))):
            try:
                proc = subprocess.run(
                    ["tesseract", png, "stdout", "-l", "jpn+eng", "--psm", "6", "tsv"],
                    check=True,
                    capture_output=True,
                    timeout=180,
                )
            except FileNotFoundError:
                raise OcrUnavailableError("tesseract が未導入です")
            rows.extend(parse_tsv(proc.stdout.decode("utf-8", "replace"), gap_px))
        return rows
