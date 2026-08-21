from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APITestCase

from .models import Dividend, StockPrice, Trade, Watch
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

    def test_summary_all_time_and_foreign_currency(self):
        # 2025年: 売却益 5000円 + 配当 1000円 / 2026年: 配当 3000円 + 米ドル配当
        make_trade(self.user, trade_date=date(2025, 1, 10), price=Decimal("1000"))
        make_trade(
            self.user,
            trade_date=date(2025, 3, 5),
            side=Trade.Side.SELL,
            price=Decimal("1050"),
        )
        Dividend.objects.create(
            user=self.user,
            received_date=date(2025, 6, 1),
            code="7203",
            name="トヨタ",
            amount=1000,
        )
        Dividend.objects.create(
            user=self.user,
            received_date=date(2026, 6, 1),
            code="7203",
            name="トヨタ",
            amount=3000,
        )
        Dividend.objects.create(
            user=self.user,
            received_date=date(2026, 6, 16),
            code="PFE",
            name="PFIZER INC.",
            currency="USドル",
            amount=Decimal("0.39"),
            gross_amount=Decimal("0.43"),
        )
        res = self.client.get("/api/stocks/summary/", {"year": 2026})
        # 年間: 外貨は円の合計に混ざらず通貨別に返る
        self.assertEqual(res.data["dividends"], 3000)
        self.assertEqual(res.data["dividends_foreign"], {"USドル": 0.39})
        # 累計 (全期間)
        self.assertEqual(res.data["all_time"]["realized"], 5000)
        self.assertEqual(res.data["all_time"]["dividends"], 4000)
        self.assertEqual(res.data["all_time"]["total"], 9000)
        self.assertEqual(res.data["all_time"]["dividends_foreign"], {"USドル": 0.39})
        self.assertEqual(res.data["years"], [2025, 2026])

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

    def test_watch_reached(self):
        StockPrice.objects.create(user=self.user, code="7203", price=Decimal("2450"))
        res = self.client.post(
            "/api/stocks/watches/",
            {"code": "7203", "name": "トヨタ", "kind": "buy", "target_price": "2500"},
        )
        self.assertEqual(res.status_code, 201)
        res = self.client.get("/api/stocks/watches/")
        row = res.data[0]
        self.assertEqual(row["current_price"], 2450.0)
        self.assertTrue(row["reached"])  # 買い目標: 現在値 <= 目標
        # 売り目標: 現在値 >= 目標でないと未達成
        self.client.post(
            "/api/stocks/watches/",
            {"code": "7203", "name": "トヨタ", "kind": "sell", "target_price": "3000"},
        )
        res = self.client.get("/api/stocks/watches/")
        sell_row = next(r for r in res.data if r["kind"] == "sell")
        self.assertFalse(sell_row["reached"])

    def test_prices_refresh_updates_positions_and_watches(self):
        make_trade(self.user, code="7203")
        Watch.objects.create(
            user=self.user, code="9432", name="NTT", kind="buy", target_price=Decimal("140")
        )
        with patch("stocks.views.fetch_quotes") as mock_fetch:
            mock_fetch.return_value = ({"7203": Decimal("3132"), "9432": Decimal("150.5")}, [])
            res = self.client.post("/api/stocks/prices/refresh/", {}, format="json")
            mock_fetch.assert_called_once_with(["7203", "9432"])
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["prices"]["7203"], 3132.0)
        self.assertEqual(StockPrice.objects.filter(user=self.user).count(), 2)
        # 保有一覧に現在値が反映される
        res = self.client.get("/api/stocks/positions/")
        self.assertEqual(res.data["positions"][0]["current_price"], 3132.0)

    def test_stock_info_settlement_month(self):
        res = self.client.put("/api/stocks/info/7203/", {"settlement_month": 3}, format="json")
        self.assertEqual(res.status_code, 200)
        make_trade(self.user, code="7203")
        res = self.client.get("/api/stocks/positions/")
        self.assertEqual(res.data["positions"][0]["settlement_month"], 3)
        res = self.client.put("/api/stocks/info/7203/", {"settlement_month": 13}, format="json")
        self.assertEqual(res.status_code, 400)

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


class DividendApiTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("taro", password="pass12345")
        self.client.force_authenticate(self.user)

    def test_create_with_tax_breakdown_autocomputes_amount(self):
        res = self.client.post(
            "/api/stocks/dividends/",
            {
                "received_date": "2026-06-01",
                "code": "7203",
                "name": "トヨタ",
                "shares": 100,
                "gross_amount": 5000,
                "tax_national": 765,
                "tax_local": 250,
            },
            format="json",
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["amount"], 3985)  # 5000 - 765 - 250

    def test_create_amount_only_still_works(self):
        res = self.client.post(
            "/api/stocks/dividends/",
            {"received_date": "2026-06-01", "code": "7203", "name": "トヨタ", "amount": 3000},
            format="json",
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["amount"], 3000)

    def test_create_requires_amount_or_gross(self):
        res = self.client.post(
            "/api/stocks/dividends/",
            {"received_date": "2026-06-01", "code": "7203", "name": "トヨタ"},
            format="json",
        )
        self.assertEqual(res.status_code, 400)

    def test_withholding_over_gross_rejected(self):
        res = self.client.post(
            "/api/stocks/dividends/",
            {
                "received_date": "2026-06-01",
                "code": "7203",
                "name": "トヨタ",
                "gross_amount": 1000,
                "tax_national": 900,
                "tax_local": 200,
            },
            format="json",
        )
        self.assertEqual(res.status_code, 400)

    def test_import_is_idempotent(self):
        rows = [
            {
                "received_date": "2026-06-24",
                "code": "9201",
                "name": "日本航空",
                "shares": 39,
                "gross_amount": 1950,
                "tax_national": 0,
                "tax_local": 0,
                "amount": 1950,
                "memo": "NISA成長投資枠",
            },
            # 完全に同一内容の行が2つあるケース (両方とも別の受取として取り込む)
            {
                "received_date": "2026-06-26",
                "code": "9104",
                "name": "商船三井",
                "shares": 2,
                "gross_amount": 230,
                "tax_national": 0,
                "tax_local": 0,
                "amount": 230,
                "memo": "NISA成長投資枠",
            },
            {
                "received_date": "2026-06-26",
                "code": "9104",
                "name": "商船三井",
                "shares": 2,
                "gross_amount": 230,
                "tax_national": 0,
                "tax_local": 0,
                "amount": 230,
                "memo": "NISA成長投資枠",
            },
        ]
        res = self.client.post(
            "/api/stocks/import/dividends/", {"dividends": rows}, format="json"
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["imported"], 3)
        # 再取込 → 全件スキップ
        res = self.client.post(
            "/api/stocks/import/dividends/", {"dividends": rows}, format="json"
        )
        self.assertEqual(res.data["imported"], 0)
        self.assertEqual(res.data["skipped_imported"], 3)
        self.assertEqual(Dividend.objects.filter(user=self.user).count(), 3)

    def test_import_skips_manually_entered_duplicates(self):
        # 手入力済み (import_key=NULL、株数・税引前なし)。受取日+銘柄+税引後額で重複判定
        Dividend.objects.create(
            user=self.user,
            received_date=date(2026, 5, 26),
            code="7203",
            name="トヨタ自動車",
            amount=319,
        )
        rows = [
            {
                "received_date": "2026-05-26",
                "code": "7203",
                "name": "トヨタ自動車",
                "shares": 8,
                "gross_amount": 400,
                "tax_national": 61,
                "tax_local": 20,
                "amount": 319,
                "memo": "特定・一般",
            }
        ]
        res = self.client.post(
            "/api/stocks/import/dividends/", {"dividends": rows}, format="json"
        )
        self.assertEqual(res.data["imported"], 0)
        self.assertEqual(res.data["skipped_manual"], 1)
        self.assertEqual(Dividend.objects.filter(user=self.user).count(), 1)

    def test_import_foreign_currency(self):
        # 米国株: 外国源泉徴収があるため 税引前 - 税額 ≠ 受取額 でも取り込める
        rows = [
            {
                "received_date": "2026-06-16",
                "code": "PFE",
                "name": "PFIZER INC.",
                "currency": "USドル",
                "shares": 1,
                "gross_amount": 0.43,
                "amount": 0.39,
                "memo": "NISA成長投資枠",
            }
        ]
        res = self.client.post(
            "/api/stocks/import/dividends/", {"dividends": rows}, format="json"
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["imported"], 1)
        d = Dividend.objects.get(user=self.user, code="PFE")
        self.assertEqual(d.currency, "USドル")
        self.assertEqual(d.amount, Decimal("0.39"))
        # 再取込 → スキップ
        res = self.client.post(
            "/api/stocks/import/dividends/", {"dividends": rows}, format="json"
        )
        self.assertEqual(res.data["imported"], 0)
        self.assertEqual(res.data["skipped_imported"], 1)

    def test_partial_update(self):
        d = Dividend.objects.create(
            user=self.user,
            received_date=date(2026, 6, 1),
            code="7203",
            name="トヨタ",
            amount=3000,
        )
        res = self.client.patch(
            f"/api/stocks/dividends/{d.id}/",
            {"shares": 100, "gross_amount": 5000, "tax_national": 765, "tax_local": 250, "amount": 3985},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        d.refresh_from_db()
        self.assertEqual(d.shares, 100)
        self.assertEqual(d.gross_amount, 5000)
        self.assertEqual(d.amount, 3985)
