from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


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


class RecurringPayment(models.Model):
    """定期支払(固定費)のテンプレート。実際の支払は pay アクションで Transaction を生成する。"""

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
    is_active = models.BooleanField("有効", default=True)
    memo = models.CharField("メモ", max_length=200, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["day_of_month", "id"]

    def __str__(self):
        return f"{self.name} ¥{self.amount} ({self.day_of_month}日)"


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
