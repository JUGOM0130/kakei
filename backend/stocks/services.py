"""移動平均法による実現損益・ポジション計算。

平均取得単価は買付手数料込み。売却損益 = (売却単価×株数 − 売却手数料) − 平均取得単価×株数。
ポジションは (銘柄コード, 口座区分) ごとに管理する (税制上は口座単位で取得単価が別)。
"""

from decimal import ROUND_HALF_UP, Decimal

from .models import Trade

YEN = Decimal("1")


def _to_yen(d):
    return int(Decimal(d).quantize(YEN, rounding=ROUND_HALF_UP))


def scan_trades(trades):
    """取引を時系列で舐めて (realized, positions) を返す。

    realized: {trade_id: 実現損益(円, int)} — 売却行のみ
    positions: {(code, account_type): {"qty": int, "avg": Decimal, "name": str}}
    """
    positions = {}
    realized = {}
    for t in sorted(trades, key=lambda t: (t.trade_date, t.id)):
        key = (t.code, t.account_type)
        pos = positions.setdefault(key, {"qty": 0, "avg": Decimal(0), "name": t.name})
        if t.name:
            pos["name"] = t.name
        if t.side == Trade.Side.BUY:
            cost = pos["avg"] * pos["qty"] + t.price * t.quantity + t.fee
            pos["qty"] += t.quantity
            pos["avg"] = cost / pos["qty"]
        else:
            proceeds = t.price * t.quantity - t.fee
            realized[t.id] = _to_yen(proceeds - pos["avg"] * t.quantity)
            pos["qty"] -= t.quantity
            # 保有以上の売却 (登録漏れ等) はポジションをゼロに戻す
            if pos["qty"] <= 0:
                pos["qty"] = 0
                pos["avg"] = Decimal(0)
    return realized, positions


def open_positions(trades):
    """保有中 (株数 > 0) のポジションのみを返す。"""
    _, positions = scan_trades(trades)
    return {key: pos for key, pos in positions.items() if pos["qty"] > 0}
