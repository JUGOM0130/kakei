from rest_framework import serializers

from .models import Dividend, StockPrice, Trade


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


class StockPriceSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockPrice
        fields = ["code", "price", "updated_at"]
        read_only_fields = ["code", "updated_at"]
