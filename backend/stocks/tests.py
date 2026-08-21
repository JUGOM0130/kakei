from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APITestCase

from .models import Dividend, Trade
from .services import open_positions, scan_trades


def make_trade(user, **kwargs):
    defaults = {
        "trade_date": date(2026, 1, 10),
        "code": "7203",
        "name": "トヨタ",
        "side": Trade.Side.BUY,
        "quantity": 100,
        "price": Decimal("1000"),
        "fee": 0,
    }
    defaults.update(kwargs)
    return Trade.objects.create(user=user, **defaults)


class MovingAverageTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("taro", password="pass12345")

    def test_realized_pnl_moving_average(self):
        # 100株@1000 (手数料100) + 100株@1200 (手数料100) → 平均 1101円
        make_trade(self.user, trade_date=date(2026, 1, 10), price=Decimal("1000"), fee=100)
        make_trade(self.user, trade_date=date(2026, 2, 10), price=Decimal("1200"), fee=100)
        # 100株@1300 売却 (手数料200) → (130000-200) - 110100 = 19700
        sell = make_trade(
            self.user,
            trade_date=date(2026, 3, 10),
            side=Trade.Side.SELL,
            price=Decimal("1300"),
            fee=200,
        )
        realized, positions = scan_trades(Trade.objects.filter(user=self.user))
        self.assertEqual(realized[sell.id], 19700)
        pos = positions[("7203", Trade.AccountType.TOKUTEI)]
        self.assertEqual(pos["qty"], 100)
        self.assertEqual(pos["avg"], Decimal("1101"))

    def test_positions_separated_by_account_type(self):
        make_trade(self.user, account_type=Trade.AccountType.TOKUTEI)
        make_trade(self.user, account_type=Trade.AccountType.NISA_GROWTH, price=Decimal("900"))
        positions = open_positions(Trade.objects.filter(user=self.user))
        self.assertEqual(len(positions), 2)

    def test_oversell_resets_position(self):
        make_trade(self.user, quantity=100)
        make_trade(self.user, trade_date=date(2026, 2, 1), side=Trade.Side.SELL, quantity=150)
        positions = open_positions(Trade.objects.filter(user=self.user))
        self.assertEqual(positions, {})


class SummaryApiTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("taro", password="pass12345")
        self.client.force_authenticate(self.user)

    def test_summary(self):
        make_trade(self.user, trade_date=date(2026, 1, 10), price=Decimal("1000"))
        make_trade(
            self.user,
            trade_date=date(2026, 3, 5),
            side=Trade.Side.SELL,
            price=Decimal("1100"),
        )
        Dividend.objects.create(
            user=self.user,
            received_date=date(2026, 6, 1),
            code="7203",
            name="トヨタ",
            amount=3000,
        )
        res = self.client.get("/api/stocks/summary/", {"year": 2026})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["realized"], 10000)
        self.assertEqual(res.data["dividends"], 3000)
        self.assertEqual(res.data["total"], 13000)
        march = next(m for m in res.data["monthly"] if m["month"] == "2026-03")
        self.assertEqual(march["realized"], 10000)
        self.assertEqual(res.data["by_code"][0]["code"], "7203")

    def test_other_users_data_invisible(self):
        other = get_user_model().objects.create_user("hanako", password="pass12345")
        make_trade(other)
        res = self.client.get("/api/stocks/trades/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 0)

    def test_trade_crud_and_realized_in_list(self):
        res = self.client.post(
            "/api/stocks/trades/",
            {
                "trade_date": "2026-01-10",
                "code": "9432",
                "name": "NTT",
                "side": "buy",
                "quantity": 100,
                "price": "150",
                "fee": 0,
                "account_type": "nisa_growth",
            },
        )
        self.assertEqual(res.status_code, 201)
        res = self.client.post(
            "/api/stocks/trades/",
            {
                "trade_date": "2026-02-10",
                "code": "9432",
                "name": "NTT",
                "side": "sell",
                "quantity": 100,
                "price": "160",
                "fee": 100,
                "account_type": "nisa_growth",
            },
        )
        self.assertEqual(res.status_code, 201)
        res = self.client.get("/api/stocks/trades/")
        sell_row = next(r for r in res.data if r["side"] == "sell")
        self.assertEqual(sell_row["realized_pnl"], 900)

    def test_import_is_idempotent(self):
        rows = [
            {
                "trade_date": "2026-01-10",
                "code": "7203",
                "name": "トヨタ自動車",
                "side": "buy",
                "quantity": 100,
                "price": "2591.0",
                "fee": 0,
                "account_type": "tokutei",
                "broker": "楽天証券",
            },
            # 完全に同一内容の行が2つあるケース (両方とも別取引として取り込む)
            {
                "trade_date": "2026-02-01",
                "code": "9432",
                "name": "NTT",
                "side": "buy",
                "quantity": 100,
                "price": "146.6",
                "fee": 0,
                "account_type": "nisa_growth",
                "broker": "楽天証券",
            },
            {
                "trade_date": "2026-02-01",
                "code": "9432",
                "name": "NTT",
                "side": "buy",
                "quantity": 100,
                "price": "146.6",
                "fee": 0,
                "account_type": "nisa_growth",
                "broker": "楽天証券",
            },
        ]
        res = self.client.post("/api/stocks/import/trades/", {"trades": rows}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["imported"], 3)
        # 再取込 → 全件スキップ
        res = self.client.post("/api/stocks/import/trades/", {"trades": rows}, format="json")
        self.assertEqual(res.data["imported"], 0)
        self.assertEqual(res.data["skipped_imported"], 3)
        self.assertEqual(Trade.objects.filter(user=self.user).count(), 3)

    def test_import_skips_manually_entered_duplicates(self):
        # 手入力済み (import_key=NULL)。単価は 2591.0000 で保存される
        make_trade(self.user, trade_date=date(2026, 1, 10), price=Decimal("2591"))
        rows = [
            {
                "trade_date": "2026-01-10",
                "code": "7203",
                "name": "トヨタ",
                "side": "buy",
                "quantity": 100,
                "price": "2591.0",
                "fee": 0,
                "account_type": "tokutei",
                "broker": "楽天証券",
            }
        ]
        res = self.client.post("/api/stocks/import/trades/", {"trades": rows}, format="json")
        self.assertEqual(res.data["imported"], 0)
        self.assertEqual(res.data["skipped_manual"], 1)
        self.assertEqual(Trade.objects.filter(user=self.user).count(), 1)

    def test_positions_with_price(self):
        make_trade(self.user, quantity=200, price=Decimal("1000"), fee=0)
        res = self.client.put("/api/stocks/prices/7203/", {"price": "1250"})
        self.assertEqual(res.status_code, 200)
        res = self.client.get("/api/stocks/positions/")
        row = res.data["positions"][0]
        self.assertEqual(row["quantity"], 200)
        self.assertEqual(row["cost"], 200000)
        self.assertEqual(row["market_value"], 250000)
        self.assertEqual(row["unrealized_pnl"], 50000)
