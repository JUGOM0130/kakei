"""株価の取得 (Yahoo Finance 非公式チャート API、東証 = <code>.T)。

キー不要・無料。個人利用の数十銘柄程度を想定し、並列は控えめにする。
失敗した銘柄は failed で返し、画面側では手動入力にフォールバックできる。
"""

import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"


def fetch_quote(code):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{code}.T?range=1d&interval=1d"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=10) as res:
        meta = json.load(res)["chart"]["result"][0]["meta"]
    price = meta.get("regularMarketPrice")
    return Decimal(str(price)) if price is not None else None


def fetch_quotes(codes):
    """codes → ({code: Decimal}, [取得失敗 code])"""
    prices = {}
    failed = []

    def worker(code):
        try:
            price = fetch_quote(code)
        except Exception:
            price = None
        if price is None:
            failed.append(code)
        else:
            prices[code] = price

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(worker, codes))
    return prices, failed
