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


def _money_field(**kwargs):
    # 外貨の小数に対応しつつ JSON では数値のまま返す
    return serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=0, coerce_to_string=False, **kwargs
    )


class DividendSerializer(serializers.ModelSerializer):
    # 税引前が入っていれば税引後 (amount) は省略可 (源泉徴収を引いて自動計算)
    amount = _money_field(required=False)
    gross_amount = _money_field(required=False, allow_null=True)
    tax_national = _money_field(required=False, allow_null=True)
    tax_local = _money_field(required=False, allow_null=True)

    class Meta:
        model = Dividend
        fields = [
            "id",
            "received_date",
            "code",
            "name",
            "currency",
            "shares",
            "gross_amount",
            "tax_national",
            "tax_local",
            "amount",
            "memo",
        ]

    def validate_code(self, value):
        return value.strip().upper()

    def validate(self, attrs):
        # 部分更新では未指定フィールドを既存値で補って整合を見る
        def current(field):
            if field in attrs:
                return attrs[field]
            return getattr(self.instance, field, None) if self.instance else None

        gross = current("gross_amount")
        withheld = (current("tax_national") or 0) + (current("tax_local") or 0)
        if gross is not None and withheld > gross:
            raise serializers.ValidationError(
                {"gross_amount": "源泉徴収額の合計が税引前配当金を上回っています。"}
            )
        if current("amount") is None:
            if gross is None:
                raise serializers.ValidationError(
                    {"amount": "税引後の受取額か税引前の配当金を入力してください。"}
                )
            attrs["amount"] = gross - withheld
        return attrs


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
