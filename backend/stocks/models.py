from django.conf import settings
from django.db import models


class Trade(models.Model):
    """株式の売買1件。実現損益は保存せず、移動平均法でその都度計算する (services.py)。"""

    class Side(models.TextChoices):
        BUY = "buy", "買付"
        SELL = "sell", "売却"

    class AccountType(models.TextChoices):
        TOKUTEI = "tokutei", "特定"
        NISA_GROWTH = "nisa_growth", "NISA成長"
        NISA_TSUMITATE = "nisa_tsumitate", "NISAつみたて"
        IPPAN = "ippan", "一般"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="stock_trades"
    )
    trade_date = models.DateField("約定日")
    code = models.CharField("銘柄コード", max_length=10)
    name = models.CharField("銘柄名", max_length=100)
    side = models.CharField("売買", max_length=4, choices=Side.choices)
    quantity = models.PositiveIntegerField("株数")
    # 米国株や投信の基準価額も入れられるよう小数4桁まで
    price = models.DecimalField("単価", max_digits=14, decimal_places=4)
    fee = models.PositiveIntegerField("手数料 (円)", default=0)
    account_type = models.CharField(
        "口座区分",
        max_length=14,
        choices=AccountType.choices,
        default=AccountType.TOKUTEI,
    )
    broker = models.CharField("証券会社", max_length=50, blank=True, default="")
    memo = models.CharField("メモ", max_length=200, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-trade_date", "-id"]

    def __str__(self):
        return f"{self.trade_date} {self.get_side_display()} {self.code} {self.quantity}株"


class Dividend(models.Model):
    """配当金・分配金の受取1件。金額は税引後の受取額。"""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="stock_dividends"
    )
    received_date = models.DateField("受取日")
    code = models.CharField("銘柄コード", max_length=10)
    name = models.CharField("銘柄名", max_length=100)
    amount = models.PositiveIntegerField("受取額 (税引後・円)")
    memo = models.CharField("メモ", max_length=200, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-received_date", "-id"]

    def __str__(self):
        return f"{self.received_date} {self.code} ¥{self.amount}"


class StockPrice(models.Model):
    """保有銘柄の現在値 (手動入力)。保有一覧の評価損益に使う。"""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="stock_prices"
    )
    code = models.CharField("銘柄コード", max_length=10)
    price = models.DecimalField("現在値", max_digits=14, decimal_places=4)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "code"], name="uniq_user_stock_price")
        ]

    def __str__(self):
        return f"{self.code} ¥{self.price}"
