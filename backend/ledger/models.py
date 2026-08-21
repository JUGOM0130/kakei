from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Group(models.Model):
    """夫婦などの世帯グループ (2人まで)。招待コードで参加する。"""

    MAX_MEMBERS = 2

    name = models.CharField("名前", max_length=50)
    invite_code = models.CharField("招待コード", max_length=8, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class GroupMember(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="members")
    # 1ユーザーは1グループまで
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="group_member"
    )
    # 共有支払いを新規登録するときのデフォルト負担割合 (このユーザーが払う側のとき)
    share_percent = models.PositiveSmallIntegerField(
        "デフォルト負担割合", default=50, validators=[MaxValueValidator(100)]
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.group.name}:{self.user.username}"


class Category(models.Model):
    class Type(models.TextChoices):
        INCOME = "income", "収入"
        EXPENSE = "expense", "支出"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="categories"
    )
    name = models.CharField("名前", max_length=50)
    type = models.CharField("種別", max_length=7, choices=Type.choices)
    color = models.CharField("色", max_length=7, default="#9e9e9e")
    sort_order = models.PositiveSmallIntegerField("並び順", default=0)

    class Meta:
        ordering = ["type", "sort_order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "name", "type"], name="uniq_user_category_name_type"
            )
        ]

    def __str__(self):
        return f"{self.get_type_display()}:{self.name}"


class PaymentMethod(models.Model):
    """支払方法 (現金・カードA・カードB など)。カード別の月間合計に使う。"""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="payment_methods"
    )
    name = models.CharField("名前", max_length=50)
    sort_order = models.PositiveSmallIntegerField("並び順", default=0)

    class Meta:
        ordering = ["sort_order", "id"]
        constraints = [
            models.UniqueConstraint(fields=["user", "name"], name="uniq_user_payment_method")
        ]

    def __str__(self):
        return self.name


class RecurringPayment(models.Model):
    """定期支払(固定費)のテンプレート。実際の支払は pay アクションで Transaction を生成する。

    interval_months で「2ヶ月ごと(水道)」「4ヶ月ごと(固定資産税)」等に対応。
    interval_months > 1 のときは anchor_month (該当月のひとつ) が必須。
    """

    INTERVAL_CHOICES = [
        (1, "毎月"),
        (2, "2ヶ月ごと"),
        (3, "3ヶ月ごと"),
        (4, "4ヶ月ごと"),
        (6, "半年ごと"),
        (12, "毎年"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="recurring_payments"
    )
    name = models.CharField("名前", max_length=100)
    amount = models.PositiveIntegerField("金額")
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name="recurring_payments"
    )
    day_of_month = models.PositiveSmallIntegerField(
        "支払日", validators=[MinValueValidator(1), MaxValueValidator(31)]
    )
    payment_method = models.ForeignKey(
        PaymentMethod,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="recurring_payments",
    )
    interval_months = models.PositiveSmallIntegerField(
        "間隔", default=1, choices=INTERVAL_CHOICES
    )
    anchor_month = models.DateField("該当月", null=True, blank=True)  # 月初日で保持
    is_shared = models.BooleanField("共有", default=False)
    payer_share_percent = models.PositiveSmallIntegerField(
        "支払者の負担割合", default=50, validators=[MaxValueValidator(100)]
    )
    is_active = models.BooleanField("有効", default=True)
    memo = models.CharField("メモ", max_length=200, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["day_of_month", "id"]

    def __str__(self):
        return f"{self.name} ¥{self.amount} ({self.day_of_month}日)"

    def is_due_in(self, first_day):
        """first_day (その月の1日) に支払月が該当するか"""
        if self.anchor_month is None:
            return self.interval_months == 1
        diff = (first_day.year - self.anchor_month.year) * 12 + (
            first_day.month - self.anchor_month.month
        )
        return diff >= 0 and diff % self.interval_months == 0


class Transaction(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="transactions"
    )
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name="transactions"
    )
    amount = models.PositiveIntegerField("金額")  # 整数円。収支の別は category.type
    date = models.DateField("日付", db_index=True)
    memo = models.CharField("メモ", max_length=200, blank=True, default="")
    # カード請求などの内訳行: 親を持つ。集計では親の金額を1回だけ数え、
    # カテゴリ内訳・共有計算のときだけ内訳行を使う。孫は禁止 (serializer で検証)。
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="items"
    )
    payment_method = models.ForeignKey(
        PaymentMethod,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="transactions",
    )
    # 共有支払い: group が設定されていればグループ内で共有される。
    # payer_share_percent は「支払った人 (user) が負担する割合」。残りを相手が負担。
    group = models.ForeignKey(
        Group, null=True, blank=True, on_delete=models.SET_NULL, related_name="transactions"
    )
    payer_share_percent = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MaxValueValidator(100)]
    )
    recurring_payment = models.ForeignKey(
        RecurringPayment,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="transactions",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "-id"]
        indexes = [models.Index(fields=["user", "date"])]

    def __str__(self):
        return f"{self.date} {self.category.name} ¥{self.amount}"


class AccountBalance(models.Model):
    """基準となる口座残高。想定残高 = amount + as_of_date より後の収支累計 ± 精算。"""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="account_balance"
    )
    amount = models.PositiveIntegerField("残高")
    as_of_date = models.DateField("基準日")
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} ¥{self.amount} ({self.as_of_date})"


class Settlement(models.Model):
    """月ごとの精算記録 (from_user が to_user に amount を渡した)。"""

    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="settlements")
    month = models.DateField("対象月")  # 月初日で保持
    from_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="settlements_from"
    )
    to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="settlements_to"
    )
    amount = models.PositiveIntegerField("金額")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["group", "month"], name="uniq_group_month_settlement")
        ]

    def __str__(self):
        return f"{self.month} {self.from_user} → {self.to_user} ¥{self.amount}"
