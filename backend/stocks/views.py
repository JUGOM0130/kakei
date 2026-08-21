import hashlib
from collections import Counter, defaultdict
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from rest_framework import viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Dividend, StockInfo, StockPrice, Trade, Watch
from .quotes import fetch_quotes
from .serializers import (
    DividendSerializer,
    StockPriceSerializer,
    TradeSerializer,
    WatchSerializer,
)
from .services import open_positions, scan_trades


def parse_year(request):
    raw = request.query_params.get("year")
    if not raw:
        return date.today().year
    try:
        return int(raw)
    except ValueError:
        raise ValidationError({"year": "西暦4桁で指定してください。"})


class TradeViewSet(viewsets.ModelViewSet):
    serializer_class = TradeSerializer

    def get_queryset(self):
        qs = Trade.objects.filter(user=self.request.user)
        year = self.request.query_params.get("year")
        if year:
            qs = qs.filter(trade_date__year=year)
        code = self.request.query_params.get("code")
        if code:
            qs = qs.filter(code=code.strip().upper())
        return qs

    def get_serializer_context(self):
        context = super().get_serializer_context()
        # 売却損益は全取引の時系列から決まるため、フィルタに関係なく全件で計算する
        if self.action in ("list", "retrieve"):
            realized, _ = scan_trades(Trade.objects.filter(user=self.request.user))
            context["realized"] = realized
        return context

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class DividendViewSet(viewsets.ModelViewSet):
    serializer_class = DividendSerializer

    def get_queryset(self):
        qs = Dividend.objects.filter(user=self.request.user)
        year = self.request.query_params.get("year")
        if year:
            qs = qs.filter(received_date__year=year)
        return qs

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


def _trade_content_tuple(data):
    """取引内容の正規化タプル。取込キーと手入力重複チェックの基準。"""
    # Decimal('2591.0') と Decimal('2591') を同一視する
    price = format(Decimal(data["price"]).normalize(), "f")
    return (
        str(data["trade_date"]),
        data["code"],
        data["side"],
        str(data["quantity"]),
        price,
        str(data.get("fee", 0)),
        data["account_type"],
    )


def make_import_key(content, occurrence):
    """同一内容の行がファイル内に複数あっても衝突しないよう出現順を付けてハッシュ化。"""
    raw = "|".join(content) + f"#{occurrence}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:64]


class ImportTradesView(APIView):
    """証券会社の取引履歴 CSV の一括取込 (冪等)。

    行内容のハッシュを import_key として保存し、既取込行はスキップする。
    手入力済みの同内容取引 (import_key=NULL) ともマッチさせて二重登録を防ぐ。
    """

    def post(self, request):
        rows = request.data.get("trades")
        if not isinstance(rows, list) or not rows:
            raise ValidationError({"trades": "取込対象の行がありません。"})
        serializer = TradeSerializer(data=rows, many=True)
        serializer.is_valid(raise_exception=True)

        existing_keys = set(
            Trade.objects.filter(user=request.user, import_key__isnull=False).values_list(
                "import_key", flat=True
            )
        )
        # 手入力取引の内容タプル別件数 (同内容の先頭 n 件は手入力済みとみなしてスキップ)
        manual_counts = Counter(
            _trade_content_tuple(
                {
                    "trade_date": t.trade_date,
                    "code": t.code,
                    "side": t.side,
                    "quantity": t.quantity,
                    "price": t.price,
                    "fee": t.fee,
                    "account_type": t.account_type,
                }
            )
            for t in Trade.objects.filter(user=request.user, import_key__isnull=True)
        )

        occurrences = Counter()
        to_create = []
        skipped_imported = 0
        skipped_manual = 0
        for data in serializer.validated_data:
            content = _trade_content_tuple(data)
            n = occurrences[content]
            occurrences[content] += 1
            key = make_import_key(content, n)
            if key in existing_keys:
                skipped_imported += 1
                continue
            if n < manual_counts[content]:
                skipped_manual += 1
                continue
            to_create.append(Trade(user=request.user, import_key=key, **data))

        with transaction.atomic():
            Trade.objects.bulk_create(to_create)

        return Response(
            {
                "imported": len(to_create),
                "skipped_imported": skipped_imported,
                "skipped_manual": skipped_manual,
            }
        )


def _dividend_content_tuple(data):
    """配当内容の正規化タプル。取込キーの基準。"""

    def s(field):
        v = data.get(field)
        return "" if v is None else str(v)

    return (
        str(data["received_date"]),
        data["code"],
        s("shares"),
        s("gross_amount"),
        s("tax_national"),
        s("tax_local"),
        str(data["amount"]),
    )


class ImportDividendsView(APIView):
    """証券会社の配当金・分配金一覧 CSV の一括取込 (冪等)。

    行内容のハッシュを import_key として保存し、既取込行はスキップする。
    手入力済みの配当 (import_key=NULL) は受取日・銘柄・税引後額の一致で
    重複とみなしてスキップする (手入力には株数や税引前がないことが多いため)。
    """

    def post(self, request):
        rows = request.data.get("dividends")
        if not isinstance(rows, list) or not rows:
            raise ValidationError({"dividends": "取込対象の行がありません。"})
        serializer = DividendSerializer(data=rows, many=True)
        serializer.is_valid(raise_exception=True)

        existing_keys = set(
            Dividend.objects.filter(user=request.user, import_key__isnull=False).values_list(
                "import_key", flat=True
            )
        )
        manual_counts = Counter(
            (str(d.received_date), d.code, str(d.amount))
            for d in Dividend.objects.filter(user=request.user, import_key__isnull=True)
        )

        occurrences = Counter()
        manual_occurrences = Counter()
        to_create = []
        skipped_imported = 0
        skipped_manual = 0
        for data in serializer.validated_data:
            content = _dividend_content_tuple(data)
            n = occurrences[content]
            occurrences[content] += 1
            key = make_import_key(content, n)
            if key in existing_keys:
                skipped_imported += 1
                continue
            manual_key = (str(data["received_date"]), data["code"], str(data["amount"]))
            m = manual_occurrences[manual_key]
            manual_occurrences[manual_key] += 1
            if m < manual_counts[manual_key]:
                skipped_manual += 1
                continue
            to_create.append(Dividend(user=request.user, import_key=key, **data))

        with transaction.atomic():
            Dividend.objects.bulk_create(to_create)

        return Response(
            {
                "imported": len(to_create),
                "skipped_imported": skipped_imported,
                "skipped_manual": skipped_manual,
            }
        )


class PositionsView(APIView):
    """保有ポジション一覧 (移動平均法)。現在値が登録されていれば評価損益も返す。"""

    def get(self, request):
        positions = open_positions(Trade.objects.filter(user=request.user))
        prices = {p.code: p for p in StockPrice.objects.filter(user=request.user)}
        infos = {
            i.code: i.settlement_month for i in StockInfo.objects.filter(user=request.user)
        }
        yen = Decimal("1")
        rows = []
        for (code, account_type), pos in positions.items():
            cost = int((pos["avg"] * pos["qty"]).quantize(yen, rounding=ROUND_HALF_UP))
            row = {
                "code": code,
                "name": pos["name"],
                "account_type": account_type,
                "quantity": pos["qty"],
                "avg_price": float(pos["avg"].quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
                "cost": cost,
                "current_price": None,
                "market_value": None,
                "unrealized_pnl": None,
                "price_updated_at": None,
                "settlement_month": infos.get(code),
            }
            price = prices.get(code)
            if price is not None:
                market_value = int(
                    (price.price * pos["qty"]).quantize(yen, rounding=ROUND_HALF_UP)
                )
                row["current_price"] = float(price.price)
                row["market_value"] = market_value
                row["unrealized_pnl"] = market_value - cost
                row["price_updated_at"] = price.updated_at.isoformat()
            rows.append(row)
        rows.sort(key=lambda r: r["cost"], reverse=True)
        totals = {
            "cost": sum(r["cost"] for r in rows),
            "market_value": sum(r["market_value"] for r in rows if r["market_value"] is not None),
            "unrealized_pnl": sum(
                r["unrealized_pnl"] for r in rows if r["unrealized_pnl"] is not None
            ),
        }
        return Response({"positions": rows, "totals": totals})


class WatchViewSet(viewsets.ModelViewSet):
    """目標価格 (この価格まで来たら買い/売り) のウォッチリスト。"""

    serializer_class = WatchSerializer

    def get_queryset(self):
        return Watch.objects.filter(user=self.request.user)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["prices"] = {
            p.code: p for p in StockPrice.objects.filter(user=self.request.user)
        }
        context["infos"] = {
            i.code: i.settlement_month
            for i in StockInfo.objects.filter(user=self.request.user)
        }
        return context

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class PricesRefreshView(APIView):
    """保有中 + ウォッチ中の銘柄の株価を取得して StockPrice を更新する。"""

    def post(self, request):
        codes = request.data.get("codes")
        if not codes:
            positions = open_positions(Trade.objects.filter(user=request.user))
            codes = {code for code, _ in positions}
            codes |= set(Watch.objects.filter(user=request.user).values_list("code", flat=True))
        codes = sorted({str(c).strip().upper() for c in codes if str(c).strip()})[:50]
        if not codes:
            return Response({"prices": {}, "failed": []})
        prices, failed = fetch_quotes(codes)
        for code, price in prices.items():
            StockPrice.objects.update_or_create(
                user=request.user, code=code, defaults={"price": price}
            )
        return Response(
            {"prices": {c: float(p) for c, p in prices.items()}, "failed": failed}
        )


class StockInfoView(APIView):
    """銘柄ごとの決算月を登録・変更する。"""

    def put(self, request, code):
        month = request.data.get("settlement_month")
        if month is not None:
            try:
                month = int(month)
            except (TypeError, ValueError):
                raise ValidationError({"settlement_month": "1〜12 で指定してください。"})
            if not 1 <= month <= 12:
                raise ValidationError({"settlement_month": "1〜12 で指定してください。"})
        StockInfo.objects.update_or_create(
            user=request.user,
            code=code.strip().upper(),
            defaults={"settlement_month": month},
        )
        return Response({"code": code.strip().upper(), "settlement_month": month})


class PriceView(APIView):
    """銘柄の現在値を手動登録・削除する。"""

    def put(self, request, code):
        serializer = StockPriceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        obj, _ = StockPrice.objects.update_or_create(
            user=request.user,
            code=code.strip().upper(),
            defaults={"price": serializer.validated_data["price"]},
        )
        return Response(StockPriceSerializer(obj).data)

    def delete(self, request, code):
        StockPrice.objects.filter(user=request.user, code=code.strip().upper()).delete()
        return Response({"detail": "ok"})


class SummaryView(APIView):
    """年間サマリー: 実現損益・配当の合計、月別推移、銘柄別内訳。"""

    def get(self, request):
        year = parse_year(request)
        trades = list(Trade.objects.filter(user=request.user))
        realized, _ = scan_trades(trades)
        dividends = Dividend.objects.filter(user=request.user, received_date__year=year)

        monthly = {f"{year}-{m:02d}": {"realized": 0, "dividends": 0} for m in range(1, 13)}
        by_code = defaultdict(lambda: {"name": "", "realized": 0, "dividends": 0})
        names = {}

        realized_total = 0
        for t in trades:
            names[t.code] = t.name or names.get(t.code, "")
            pnl = realized.get(t.id)
            if pnl is None or t.trade_date.year != year:
                continue
            realized_total += pnl
            monthly[t.trade_date.strftime("%Y-%m")]["realized"] += pnl
            by_code[t.code]["realized"] += pnl

        dividend_total = 0
        for d in dividends:
            names[d.code] = d.name or names.get(d.code, "")
            dividend_total += d.amount
            monthly[d.received_date.strftime("%Y-%m")]["dividends"] += d.amount
            by_code[d.code]["dividends"] += d.amount

        rows = []
        for code, row in by_code.items():
            rows.append(
                {
                    "code": code,
                    "name": names.get(code, ""),
                    "realized": row["realized"],
                    "dividends": row["dividends"],
                    "total": row["realized"] + row["dividends"],
                }
            )
        rows.sort(key=lambda r: r["total"], reverse=True)

        years = sorted(
            {t.trade_date.year for t in trades}
            | {d.year for d in Dividend.objects.filter(user=request.user).dates("received_date", "year")}
            | {date.today().year}
        )

        return Response(
            {
                "year": year,
                "years": years,
                "realized": realized_total,
                "dividends": dividend_total,
                "total": realized_total + dividend_total,
                "monthly": [
                    {"month": month, **vals} for month, vals in sorted(monthly.items())
                ],
                "by_code": rows,
            }
        )
