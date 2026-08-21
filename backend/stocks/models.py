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
    # CSV 取込行の内容ハッシュ (同一ファイル再取込の冪等性用)。手入力は NULL
    import_key = models.CharField("取込キー", max_length=64, null=True, blank=True, default=None)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-trade_date", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "import_key"],
                name="uniq_user_trade_import_key",
                condition=models.Q(import_key__isnull=False),
            )
        ]

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


class Watch(models.Model):
    """「この価格まで来たら買い/売り」の目標価格メモ。"""

    class Kind(models.TextChoices):
        BUY = "buy", "買い目標"  # 現在値が目標以下になったら達成
        SELL = "sell", "売り目標"  # 現在値が目標以上になったら達成

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="stock_watches"
    )
    code = models.CharField("銘柄コード", max_length=10)
    name = models.CharField("銘柄名", max_length=100)
    kind = models.CharField("種別", max_length=4, choices=Kind.choices, default=Kind.BUY)
    target_price = models.DecimalField("目標価格", max_digits=14, decimal_places=4)
    memo = models.CharField("メモ", max_length=200, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-id"]

    def __str__(self):
        return f"{self.code} {self.get_kind_display()} {self.target_price}"


class StockInfo(models.Model):
    """銘柄ごとのユーザーメモ情報 (決算月など)。"""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="stock_infos"
    )
    code = models.CharField("銘柄コード", max_length=10)
    settlement_month = models.PositiveSmallIntegerField("決算月", null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "code"], name="uniq_user_stock_info")
        ]

    def __str__(self):
        return f"{self.code} 決算{self.settlement_month}月"


class StockPrice(models.Model):
    """保有銘柄の現在値 (株価取得 API または手動入力)。保有一覧の評価損益に使う。"""

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
