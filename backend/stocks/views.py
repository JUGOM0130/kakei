from collections import defaultdict
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from rest_framework import viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Dividend, StockPrice, Trade
from .serializers import DividendSerializer, StockPriceSerializer, TradeSerializer
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


class PositionsView(APIView):
    """保有ポジション一覧 (移動平均法)。現在値が登録されていれば評価損益も返す。"""

    def get(self, request):
        positions = open_positions(Trade.objects.filter(user=request.user))
        prices = {p.code: p.price for p in StockPrice.objects.filter(user=request.user)}
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
            }
            price = prices.get(code)
            if price is not None:
                market_value = int((price * pos["qty"]).quantize(yen, rounding=ROUND_HALF_UP))
                row["current_price"] = float(price)
                row["market_value"] = market_value
                row["unrealized_pnl"] = market_value - cost
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
