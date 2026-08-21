from rest_framework import serializers

from .models import Dividend, StockPrice, Trade, Watch


class TradeSerializer(serializers.ModelSerializer):
    # 一覧取得時のみ context["realized"] (trade_id → 円) から埋める
    realized_pnl = serializers.SerializerMethodField()

    class Meta:
        model = Trade
        fields = [
            "id",
            "trade_date",
            "code",
            "name",
            "side",
            "quantity",
            "price",
            "fee",
            "account_type",
            "broker",
            "memo",
            "realized_pnl",
        ]

    def get_realized_pnl(self, obj):
        return self.context.get("realized", {}).get(obj.id)

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("株数は1以上を指定してください。")
        return value

    def validate_code(self, value):
        return value.strip().upper()


class DividendSerializer(serializers.ModelSerializer):
    class Meta:
        model = Dividend
        fields = ["id", "received_date", "code", "name", "amount", "memo"]

    def validate_code(self, value):
        return value.strip().upper()


class WatchSerializer(serializers.ModelSerializer):
    # context["prices"] = {code: StockPrice}、context["infos"] = {code: 決算月}
    current_price = serializers.SerializerMethodField()
    price_updated_at = serializers.SerializerMethodField()
    reached = serializers.SerializerMethodField()
    settlement_month = serializers.SerializerMethodField()

    class Meta:
        model = Watch
        fields = [
            "id",
            "code",
            "name",
            "kind",
            "target_price",
            "memo",
            "current_price",
            "price_updated_at",
            "reached",
            "settlement_month",
        ]

    def validate_code(self, value):
        return value.strip().upper()

    def _price(self, obj):
        return self.context.get("prices", {}).get(obj.code)

    def get_current_price(self, obj):
        price = self._price(obj)
        return float(price.price) if price else None

    def get_price_updated_at(self, obj):
        price = self._price(obj)
        return price.updated_at.isoformat() if price else None

    def get_reached(self, obj):
        price = self._price(obj)
        if price is None:
            return False
        if obj.kind == Watch.Kind.BUY:
            return price.price <= obj.target_price
        return price.price >= obj.target_price

    def get_settlement_month(self, obj):
        return self.context.get("infos", {}).get(obj.code)


class StockPriceSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockPrice
        fields = ["code", "price", "updated_at"]
        read_only_fields = ["code", "updated_at"]
